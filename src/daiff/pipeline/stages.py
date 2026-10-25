"""The DAIFF stage graph and `run_pipeline` (spec §6.4, §9).

terrain → forest → coupling → train → predict → tables, then run metadata and publish.
Every raster is written with provenance tags (NFR-4); the coupling stage is the only path
from forest outputs into the flood model (SRS 3.1).
"""

from __future__ import annotations

import json
import platform
import shutil
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from daiff.config import DaiffConfig, config_hash
from daiff.coupling.compute import forest_for_year, mmu_pixels, rain_rasters
from daiff.coupling.features import coupling_features
from daiff.flood.dataset import FEATURES, build_dataset
from daiff.flood.evaluate import evaluate
from daiff.flood.model import load_model, save_model, train_model
from daiff.flood.predict import delta_s, predict_grid, risk_classes
from daiff.flood.tables import subbasin_table, write_table
from daiff.forest.change import loss_hectares_by_subbasin
from daiff.grid import Grid
from daiff.pipeline.runner import Runner, Stage, StageContext
from daiff.store.cog import read_raster, read_tags, write_cog
from daiff.store.provenance import build_tags, code_commit, compute_run_id, sha256_file
from daiff.store.raw_layout import NESTED_FACTOR, RawLayout
from daiff.store.run_store import RunStore, publish, write_run_metadata
from daiff.terrain.derive import STATIC_BANDS, build_static_features
from daiff.terrain.flow import topological_order
from daiff.zones import rasterize_subbasins

REPO_ROOT = Path(__file__).resolve().parents[3]
STAGE_ORDER = ("terrain", "forest", "coupling", "train", "predict", "tables")
RAIN_BANDS = ("rain_mean_annual", "rain_p10y_1d")
COUPLING_BANDS = ("f", "dF", "U", "Q")


@dataclass
class RunPlan:
    cfg: DaiffConfig
    raw: RawLayout
    grid: Grid
    store: RunStore
    years: tuple[int, ...]
    config_hash: str
    commit: str
    data_versions: dict[str, str]
    model_id: str | None = None
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def t0(self) -> int:
        return self.cfg.years.t0

    @property
    def fine(self) -> Grid:
        return self.grid.nested(NESTED_FACTOR)

    def tags(self, inputs: list[Path], year: int | None, model_id: str = "n/a") -> dict:
        return build_tags(
            run_id=self.store.run_id,
            config_hash=self.config_hash,
            code_commit=self.commit,
            model_id=model_id,
            inputs=inputs,
            data_root=self.cfg.data_root,
            data_versions=self.data_versions,
            year=year,
            t0=self.t0,
        )

    # interim per-run files
    @property
    def d8(self) -> Path:
        return self.store.run_dir / "d8.tif"

    @property
    def rain(self) -> Path:
        return self.store.run_dir / "rain_features.tif"

    @property
    def zones(self) -> Path:
        return self.store.run_dir / "zones.tif"

    @property
    def models_dir(self) -> Path:
        return self.cfg.data_root / "models"


def raw_inputs(raw: RawLayout, years) -> list[Path]:
    paths = [raw.grid_json, raw.subbasins, raw.chirps_daily_csv, *raw.layers_30m(years)]
    paths += raw.layers_10m(years)
    if raw.flood_events_csv.exists():
        paths.append(raw.flood_events_csv)
        for eid in pd.read_csv(raw.flood_events_csv)["event_id"]:
            if raw.flood_fraction(eid).exists():
                paths.append(raw.flood_fraction(eid))
    return [p for p in paths if p.exists()]


# ---------------------------------------------------------------- stage bodies


def _terrain(p: RunPlan) -> None:
    terrain = build_static_features(
        p.raw, p.grid, p.cfg.terrain.stream_threshold_km2, p.cfg.terrain.routing_dem
    )
    ins = [p.raw.dem, p.raw.hsg]
    stack = np.stack([terrain.bands[b] for b in STATIC_BANDS]).astype(np.float32)
    write_cog(
        p.store.static_features,
        stack,
        p.grid,
        nodata=np.nan,
        tags=p.tags(ins, None),
        band_names=list(STATIC_BANDS),
    )
    write_cog(p.d8, terrain.dirs, p.grid, nodata=255, tags=p.tags(ins, None))
    zones, names = rasterize_subbasins(p.raw.subbasins, p.grid)
    write_cog(p.zones, zones, p.grid, nodata=-1, tags=p.tags([p.raw.subbasins], None))
    rain = rain_rasters(
        p.raw, zones, list(names["subbasin_id"]), p.cfg.coupling.return_period_years
    )
    write_cog(
        p.rain,
        np.stack([rain[b] for b in RAIN_BANDS]).astype(np.float32),
        p.grid,
        nodata=np.nan,
        tags=p.tags([p.raw.chirps_daily_csv, p.raw.subbasins], None),
        band_names=list(RAIN_BANDS),
    )
    shutil.copyfile(p.raw.subbasins, p.store.subbasins_geojson)


def _forest(p: RunPlan) -> None:
    mmu = mmu_pixels(p.cfg.forest.mmu_ha)
    for y in p.years:
        ins = [p.raw.forest10m(p.t0), p.raw.forest10m(y)]
        yf = forest_for_year(p.raw, p.grid, p.t0, y, mmu)
        tags = p.tags(ins, y, model_id=read_tags(p.raw.forest10m(y)).get("DAIFF_SOURCE", "n/a"))
        write_cog(p.store.forest(y), yf.f, p.grid, nodata=np.nan, tags=tags)
        write_cog(p.store.loss(p.t0, y), yf.dF, p.grid, nodata=np.nan, tags=tags)
        write_cog(p.store.loss10m(p.t0, y), yf.loss10m, p.fine, nodata=255, tags=tags)
        write_cog(p.store.regrowth(p.t0, y), yf.regrowth10m, p.fine, nodata=255, tags=tags)
        cur = read_raster(p.raw.forest10m(y), p.fine)
        write_cog(p.store.forest10m(y), cur, p.fine, nodata=255, tags=tags)


def _static(p: RunPlan) -> dict[str, np.ndarray]:
    stack = read_raster(p.store.static_features, p.grid)
    return {b: stack[i].astype(np.float64) for i, b in enumerate(STATIC_BANDS)}


def _rain(p: RunPlan) -> dict[str, np.ndarray]:
    stack = read_raster(p.rain, p.grid)
    return {b: stack[i].astype(np.float64) for i, b in enumerate(RAIN_BANDS)}


def _coupling(p: RunPlan) -> None:
    dirs = read_raster(p.d8, p.grid)
    order = topological_order(dirs)
    hsg = np.nan_to_num(_static(p)["hsg"], nan=0).astype(np.uint8)
    pmm = _rain(p)["rain_p10y_1d"]
    for y in p.years:
        f = read_raster(p.store.forest(y), p.grid)
        dF = read_raster(p.store.loss(p.t0, y), p.grid)
        dw = read_raster(p.raw.dw_class(y), p.grid)
        cf = coupling_features(f, None, dF, dw, hsg, dirs, order, pmm, p.grid.cell_area_m2)
        ins = [p.store.forest(y), p.store.loss(p.t0, y), p.raw.dw_class(y), p.d8, p.rain]
        tags = p.tags(ins, y)
        stack = np.stack([cf[b] for b in COUPLING_BANDS]).astype(np.float32)
        write_cog(
            p.store.coupling(y),
            stack,
            p.grid,
            nodata=np.nan,
            tags=tags,
            band_names=list(COUPLING_BANDS),
        )
        write_cog(p.store.cn(y), cf["CN"].astype(np.float32), p.grid, nodata=np.nan, tags=tags)


def features_for(p: RunPlan, year: int) -> dict[str, np.ndarray]:
    coup = read_raster(p.store.coupling(year), p.grid)
    feats = {**_static(p), **_rain(p)}
    feats.update({b: coup[i].astype(np.float64) for i, b in enumerate(COUPLING_BANDS)})
    feats["CN"] = read_raster(p.store.cn(year), p.grid).astype(np.float64)
    return {f: feats[f] for f in FEATURES}


def _train(p: RunPlan) -> None:
    p.store.metrics_dir.mkdir(parents=True, exist_ok=True)
    if p.model_id is None:
        events = pd.read_csv(p.raw.flood_events_csv)
        events = events[events["year"].isin(p.years)]
        df = build_dataset(
            events,
            lambda y: features_for(p, y),
            lambda eid: read_raster(p.raw.flood_fraction(eid), p.grid),
            p.grid,
            p.cfg,
        )
        train, test = df[df["split"] == "train"], df[df["split"] == "test"]
        model = train_model(train, FEATURES, p.cfg)
        metrics = evaluate(model, test, FEATURES, p.cfg) if test["label"].nunique() == 2 else {}
        metrics.update({"n_train": int(len(train)), "events": list(events["event_id"])})
        p.model_id = save_model(model, FEATURES, metrics, p.cfg, p.models_dir)
    src = p.models_dir / p.model_id / "metrics.json"
    shutil.copyfile(src, p.store.metrics_dir / "flood_train.json")
    p.store.model_id_file.write_text(p.model_id, encoding="utf-8")


def _predict(p: RunPlan) -> None:
    model_id = p.store.model_id_file.read_text(encoding="utf-8").strip()
    model, feats = load_model(p.models_dir / model_id)
    breaks = p.cfg.flood.class_breaks
    s0 = predict_grid(model, features_for(p, p.t0), feats, p.grid.shape)
    for y in p.years:
        s = s0 if y == p.t0 else predict_grid(model, features_for(p, y), feats, p.grid.shape)
        ins = [p.store.coupling(y), p.store.cn(y), p.store.static_features, p.rain]
        tags = p.tags(ins, y, model_id=model_id)
        write_cog(p.store.susceptibility(y), s, p.grid, nodata=np.nan, tags=tags)
        write_cog(p.store.riskclass(y), risk_classes(s, breaks), p.grid, nodata=255, tags=tags)
        write_cog(p.store.delta_s(y), delta_s(s, s0), p.grid, nodata=np.nan, tags=tags)


def _tables(p: RunPlan) -> None:
    zones = read_raster(p.zones, p.grid)
    _, names = rasterize_subbasins(p.store.subbasins_geojson, p.grid)
    breaks = p.cfg.flood.class_breaks
    cls0 = read_raster(p.store.riskclass(p.t0), p.grid)
    for y in p.years:
        loss_ha = loss_hectares_by_subbasin(read_raster(p.store.loss10m(p.t0, y), p.fine), zones)
        table = subbasin_table(
            zones,
            names,
            loss_ha,
            read_raster(p.store.forest(y), p.grid),
            read_raster(p.store.susceptibility(y), p.grid),
            read_raster(p.store.delta_s(y), p.grid),
            read_raster(p.store.riskclass(y), p.grid),
            cls0,
            breaks,
            p.grid.cell_area_m2,
        )
        write_table(table, p.store.subbasin_csv(y))


# ---------------------------------------------------------------- graph


def build_stages(p: RunPlan) -> list[Stage]:
    s, ys, t0 = p.store, p.years, p.t0

    def per_year(*fns):
        return lambda _c: [fn(y) for y in ys for fn in fns]

    raw_flood = []
    if p.raw.flood_events_csv.exists():
        ev = pd.read_csv(p.raw.flood_events_csv)
        usable = ev[ev["usable"].astype(bool) & ev["year"].isin(p.years)]
        raw_flood = [p.raw.flood_events_csv] + [p.raw.flood_fraction(e) for e in usable["event_id"]]
    return [
        Stage(
            "terrain",
            lambda _c: _terrain(p),
            lambda _c: (
                [p.raw.dem, p.raw.hsg, p.raw.subbasins, p.raw.chirps_daily_csv]
                + ([p.raw.dem_hydro] if p.cfg.terrain.routing_dem == "merit" else [])
            ),
            lambda _c: [s.static_features, p.d8, p.zones, p.rain, s.subbasins_geojson],
            ("terrain", "coupling"),
        ),
        Stage(
            "forest",
            lambda _c: _forest(p),
            lambda _c: [p.raw.forest10m(y) for y in sorted({t0, *ys})],
            per_year(s.forest, lambda y: s.loss(t0, y), lambda y: s.loss10m(t0, y)),
            ("forest", "years"),
        ),
        Stage(
            "coupling",
            lambda _c: _coupling(p),
            lambda _c: (
                [s.static_features, p.d8, p.rain]
                + [f(y) for y in ys for f in (s.forest, lambda y: s.loss(t0, y), p.raw.dw_class)]
            ),
            per_year(s.coupling, s.cn),
            ("coupling",),
            deps=("terrain", "forest"),
        ),
        Stage(
            "train",
            lambda _c: _train(p),
            lambda _c: (
                [s.static_features, p.rain, *raw_flood]
                + [f(y) for y in ys for f in (s.coupling, s.cn)]
            ),
            lambda _c: [s.model_id_file],
            ("flood", "runtime"),
            deps=("coupling",),
            version=f"model={p.model_id or 'train'}",
        ),
        Stage(
            "predict",
            lambda _c: _predict(p),
            lambda _c: (
                [s.model_id_file, s.static_features, p.rain]
                + [f(y) for y in ys for f in (s.coupling, s.cn)]
            ),
            per_year(s.susceptibility, s.riskclass, s.delta_s),
            ("flood",),
            deps=("train",),
        ),
        Stage(
            "tables",
            lambda _c: _tables(p),
            lambda _c: (
                [p.zones, s.subbasins_geojson]
                + [f(y) for y in ys for f in (s.forest, s.susceptibility, s.riskclass, s.delta_s)]
                + [s.loss10m(t0, y) for y in ys]
            ),
            per_year(s.subbasin_csv),
            ("flood",),
            deps=("predict",),
        ),
    ]


def plan_run(cfg: DaiffConfig, years=None, model_id: str | None = None) -> RunPlan:
    raw = RawLayout(cfg.data_root)
    grid = Grid.from_config(cfg) if cfg.grid.bounds is not None else raw.read_grid()
    ys = tuple(sorted(set(years or cfg.years.years) | {cfg.years.t0}))
    chash = config_hash(cfg)
    commit = code_commit(REPO_ROOT)
    inputs = raw_inputs(raw, ys)
    run_id = compute_run_id(
        chash, commit, [sha256_file(x) for x in inputs] + [str(ys), model_id or ""]
    )
    dem_tags = read_tags(raw.dem)
    versions = {
        k: v for k, v in dem_tags.items() if k.startswith("DAIFF_") and k != "DAIFF_BAND_NAMES"
    }
    return RunPlan(
        cfg, raw, grid, RunStore(cfg.data_root, run_id), ys, chash, commit, versions, model_id
    )


def _log_perf(p: RunPlan) -> Path:
    out = REPO_ROOT / "docs" / "perf" / f"{date.today().isoformat()}-{platform.node()}.md"
    if not out.exists():
        out.write_text(
            "| machine | cores | RAM GB | workers | stage | seconds | run_id | commit |\n"
            "|---|---|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    import os

    with out.open("a", encoding="utf-8") as f:
        for stage, sec in p.timings.items():
            f.write(
                f"| {platform.node()} | {os.cpu_count()} | – | {p.cfg.runtime.n_workers} | "
                f"{stage} | {sec:.1f} | {p.store.run_id} | {p.commit[:12]} |\n"
            )
    return out


def run_pipeline(
    cfg: DaiffConfig,
    *,
    stages=None,
    years=None,
    force: bool = False,
    model_id: str | None = None,
    log_perf: bool = False,
) -> str:
    """Run the stage graph for `years` (default: config years), write metadata, publish."""
    p = plan_run(cfg, years, model_id)
    p.store.run_dir.mkdir(parents=True, exist_ok=True)
    if model_id is None and p.store.model_id_file.exists():
        p.model_id = p.store.model_id_file.read_text(encoding="utf-8").strip()
    runner = Runner(build_stages(p), cfg.data_root / "state" / p.store.run_id)
    ctx = StageContext(cfg=cfg, data_root=cfg.data_root, years=p.years)
    t = time.perf_counter()
    results = runner.run(ctx, only=set(stages) if stages else None, force=force)
    p.timings = {r.name: round(r.seconds, 3) for r in results}
    p.timings["total"] = round(time.perf_counter() - t, 3)
    model = p.store.model_id_file.read_text().strip() if p.store.model_id_file.exists() else None
    write_run_metadata(
        p.store,
        {
            "run_id": p.store.run_id,
            "config": cfg.model_dump(
                mode="json", exclude={"paths": True, "gee": {"project", "asset_root"}}
            ),
            "config_hash": p.config_hash,
            "code_commit": p.commit,
            "data_versions": p.data_versions,
            "inputs": [
                {"path": x.relative_to(cfg.data_root).as_posix(), "sha256": sha256_file(x)}
                for x in raw_inputs(p.raw, p.years)
            ],
            "timings": p.timings,
            "years": list(p.years),
            "t0": p.t0,
            "model_id": model,
        },
    )
    if stages is None or "tables" in stages:
        publish(cfg.data_root, p.store.run_id)
    if log_perf:
        _log_perf(p)
    return p.store.run_id


def plan_for_run(cfg: DaiffConfig, run_id: str) -> RunPlan:
    """A RunPlan bound to an existing (e.g. published) run, for validation and the API."""
    raw = RawLayout(cfg.data_root)
    store = RunStore(cfg.data_root, run_id)
    meta = json.loads(store.run_metadata.read_text(encoding="utf-8"))
    grid = Grid.from_config(cfg) if cfg.grid.bounds is not None else raw.read_grid()
    return RunPlan(
        cfg,
        raw,
        grid,
        store,
        tuple(meta["years"]),
        meta["config_hash"],
        meta["code_commit"],
        meta["data_versions"],
        meta.get("model_id"),
    )


def published_years(cfg: DaiffConfig, run_id: str) -> list[int]:
    meta = json.loads(RunStore(cfg.data_root, run_id).run_metadata.read_text(encoding="utf-8"))
    return list(meta.get("years", []))
