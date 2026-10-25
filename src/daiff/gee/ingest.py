"""`daiff gee ingest`: Earth Engine exports + downloads into the raw layout (P3).

Every image is exported as an asset on the exact project grid (batch task, idempotent), then
downloaded tile by tile. Steps can be run one at a time (`--steps static,forest,...`).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from daiff.config import DaiffConfig
from daiff.gee import refdata, s2
from daiff.gee.aoi import basin_fc
from daiff.gee.export import (
    asset_exists,
    asset_id,
    asset_root,
    compute_fetch,
    download_asset,
    getpixels_fetch,
    submit_asset_export,
    wait_for_tasks,
)
from daiff.grid import Grid
from daiff.store.raw_layout import NESTED_FACTOR, RawLayout

Log = Callable[[str], None]


@dataclass
class Ctx:
    ee: object
    cfg: DaiffConfig
    grid: Grid
    raw: RawLayout
    aoi: object  # ee.Geometry
    log: Log
    only_years: list[int] | None = None

    @property
    def years(self) -> list[int]:
        return self.only_years or self.cfg.years.years

    @property
    def fine(self) -> Grid:
        return self.grid.nested(NESTED_FACTOR)


def make_ctx(ee, cfg: DaiffConfig, log: Log = print, years: list[int] | None = None) -> Ctx:
    p = cfg.project
    aoi = basin_fc(ee, p.aoi_hybas_id, p.aoi_hybas_level).geometry()
    return Ctx(ee, cfg, Grid.from_config(cfg), RawLayout(cfg.data_root), aoi, log, years)


def ensure_folders(ee, root: str) -> None:
    parts = root.split("/")
    # projects/<p>/assets/<a>/<b>...: create every folder below `assets`
    for i in range(4, len(parts) + 1):
        path = "/".join(parts[:i])
        if not asset_exists(ee, path):
            ee.data.createAsset({"type": "FOLDER"}, path)


def _assets_available(ctx: Ctx) -> bool:
    try:
        ensure_folders(ctx.ee, asset_root(ctx.cfg))
        return True
    except Exception as exc:
        ctx.log(f"asset storage unavailable ({exc}); computing tiles directly")
        return False


FLOAT_FILL = -9999.0


def _filled(image, aoi, nodata):
    """Clip to the AOI, then fill everything masked with nodata (a sentinel for float NaN)."""
    return image.clip(aoi).unmask(FLOAT_FILL if nodata != nodata else nodata, sameFootprint=False)


def _nan_fetch(fetch):
    def wrapped(asset, window, grid):
        block = fetch(asset, window, grid).astype("float32")
        block[(block <= FLOAT_FILL + 1) | ~np.isfinite(block)] = np.nan
        return block

    return wrapped


def _direct_download(ctx: Ctx, items: list[tuple], tile: int = 1024) -> None:
    for name, image, grid, path, nodata, tags in items:
        fetch = compute_fetch(ctx.ee, _filled(image, ctx.aoi, nodata))
        if nodata != nodata:  # NaN
            fetch = _nan_fetch(fetch)
        download_asset(
            f"direct:{name}:v2",
            grid,
            path,
            fetch=fetch,
            tile=tile,
            nodata=nodata,
            tags={"DAIFF_SOURCE": tags},
        )
        ctx.log(f"downloaded {path}")


def _export_and_download(ctx: Ctx, items: list[tuple]) -> None:
    """items: (name, image, grid, local_path, nodata, tags)."""
    if not _assets_available(ctx):
        _direct_download(ctx, items)
        return
    tasks = []
    for name, image, grid, _, nodata, _ in items:
        img = image.unmask(nodata) if nodata == nodata else image  # NaN stays masked
        tid = submit_asset_export(ctx.ee, img.clip(ctx.aoi), asset_id(ctx.cfg, name), grid, name)
        ctx.log(f"export {name}: {'submitted ' + tid if tid else 'asset exists'}")
        tasks.append(tid)
    wait_for_tasks(ctx.ee, tasks)
    for name, _, grid, path, nodata, tags in items:
        download_asset(
            asset_id(ctx.cfg, name),
            grid,
            path,
            fetch=getpixels_fetch(ctx.ee),
            nodata=nodata,
            tags={"DAIFF_SOURCE": tags},
        )
        ctx.log(f"downloaded {path}")


def step_static(ctx: Ctx) -> None:
    ee, r = ctx.ee, ctx.raw
    tc, lossyear = refdata.hansen_images(ee)
    _export_and_download(
        ctx,
        [
            ("dem", refdata.dem_image(ee), ctx.grid, r.dem, np.nan, refdata.DATASETS["dem"]),
            (
                "dem_merit_hydro",
                refdata.merit_elv_image(ee),
                ctx.grid,
                r.dem_hydro,
                np.nan,
                refdata.DATASETS["merit_hydro"],
            ),
            (
                "hsg",
                refdata.hsg_image(ee),
                ctx.grid,
                r.hsg,
                255,
                refdata.DATASETS["soilgrids_clay"],
            ),
            (
                "jrc",
                refdata.jrc_image(ee),
                ctx.grid,
                r.jrc_occurrence,
                255,
                refdata.DATASETS["jrc"],
            ),
            (
                "hansen_tc2000",
                tc,
                ctx.grid,
                r.root / "hansen_treecover2000.tif",
                255,
                refdata.DATASETS["hansen"],
            ),
            (
                "hansen_lossyear",
                lossyear,
                ctx.grid,
                r.root / "hansen_lossyear.tif",
                255,
                refdata.DATASETS["hansen"],
            ),
        ],
    )


def step_coverage(ctx: Ctx, years=(2017, 2018, 2019)) -> dict[int, float]:
    out = {y: s2.coverage_fraction(ctx.ee, ctx.aoi, y) for y in years}
    (ctx.raw.root / "s2_coverage.json").write_text(json.dumps(out, indent=2), "utf-8")
    ctx.log(f"S2 L2A clear-observation coverage by season: {out}")
    return out


def step_dw(ctx: Ctx) -> None:
    items = [
        (
            f"dw_class_{y}",
            refdata.dw_mode_image(ctx.ee, y),
            ctx.grid,
            ctx.raw.dw_class(y),
            255,
            refdata.DATASETS["dynamic_world"],
        )
        for y in ctx.years
    ]
    _export_and_download(ctx, items)


def step_inventory(ctx: Ctx) -> None:
    for y in ctx.years:
        rows = s2.inventory(ctx.ee, ctx.aoi, y)
        pd.DataFrame(rows).to_csv(ctx.raw.root / f"s2_inventory_{y}.csv", index=False)
        ctx.log(f"S2 {y}: {len(rows)} scenes, {len({r['mgrs_tile'] for r in rows})} MGRS tiles")


def step_chirps(ctx: Ctx, start_year: int = 2000) -> None:
    """Daily CHIRPS mean per sub-basin: one year of days stacked as bands, one reduceRegions."""
    ee = ctx.ee
    subs = ee.FeatureCollection(json.loads(ctx.raw.subbasins.read_text("utf-8"))).select(
        ["subbasin_id"]
    )
    frames = []
    last = max(ctx.cfg.years.years)
    for y in range(start_year, last + 1):
        col = ee.ImageCollection(refdata.DATASETS["chirps"]).filterDate(
            f"{y}-01-01", f"{y + 1}-01-01"
        )
        stack = col.select("precipitation").toBands()  # bands "YYYYMMDD_precipitation"
        # 1 km sampling so even the smallest (1.5 km2) sub-basins get a value
        rows = stack.reduceRegions(subs, ee.Reducer.mean(), scale=1000).getInfo()["features"]
        long = []
        for row in rows:
            props = row["properties"]
            sid = props.pop("subbasin_id")
            for band, v in props.items():
                d = band.split("_")[0]
                long.append(
                    {"date": f"{d[:4]}-{d[4:6]}-{d[6:8]}", "subbasin_id": sid, "precip_mm": v}
                )
        frames.append(pd.DataFrame(long))
        ctx.log(f"CHIRPS {y}: {len(long)} sub-basin-days")
    df = pd.concat(frames, ignore_index=True).sort_values(["subbasin_id", "date"])
    df["precip_mm"] = df["precip_mm"].astype(float).round(2)
    ctx.raw.chirps_daily_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ctx.raw.chirps_daily_csv, index=False, lineterminator="\n")


def fill_gaps_from_previous(
    cur: np.ndarray, prev: np.ndarray | None, footprint: np.ndarray | None = None
) -> tuple[np.ndarray, float]:
    """Cloud gaps (255) take the previous year's class; returns the map and the residual gap
    share inside `footprint` (the basin; FR-D2 ≤ 5 %)."""
    out = cur.copy()
    if prev is not None:
        gap = (out == 255) & (prev != 255)
        out[gap] = prev[gap]
    if footprint is None:
        footprint = np.ones(out.shape, bool)
    share = float(((out == 255) & footprint).sum() / max(footprint.sum(), 1))
    return out, share


def step_cpc(ctx: Ctx, start_year: int = 2000) -> None:
    """NOAA CPC daily rainfall per sub-basin (FR-D3); downloads from NOAA PSL, not Earth Engine."""
    from daiff.gee.aoi import lonlat_bounds
    from daiff.ingest import cpc
    from daiff.ingest.rainfall import find_gaps
    from daiff.zones import rasterize_subbasins

    p = ctx.cfg.project
    zones, names = rasterize_subbasins(ctx.raw.subbasins, ctx.grid)
    bounds = lonlat_bounds(ctx.ee, p.aoi_hybas_id, p.aoi_hybas_level)
    years = range(start_year, max(ctx.cfg.years.years) + 1)
    df = cpc.ingest(
        ctx.grid, zones, names["subbasin_id"], years, ctx.raw.root / "cpc", bounds, ctx.log
    )
    out = ctx.raw.chirps_daily_csv.parent / "cpc_subbasin_daily.csv"
    df.to_csv(out, index=False, lineterminator="\n")
    gaps = find_gaps(df, max_gap_days=3)
    gaps.to_csv(out.parent / "gaps_cpc.csv", index=False, lineterminator="\n")
    ctx.log(f"CPC: {len(df)} sub-basin-days, {len(gaps)} gaps > 3 days -> {out}")


def event_windows(start: str, end: str) -> tuple[tuple[str, str], tuple[str, str]]:
    """Pre-event reference window (60–20 days before) and the event window."""
    s = pd.Timestamp(start)
    pre = (
        (s - pd.Timedelta(days=60)).strftime("%Y-%m-%d"),
        (s - pd.Timedelta(days=20)).strftime("%Y-%m-%d"),
    )
    event = (start, (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    return pre, event


def step_floods(ctx: Ctx) -> None:
    """Sentinel-1 flooded fraction (30 m) per candidate event; writes raw/flood_events.csv."""
    from daiff.gee import s1_flood
    from daiff.pipeline.stages import REPO_ROOT
    from daiff.store.cog import read_raster

    ee, cfg = ctx.ee, ctx.cfg
    ref = pd.read_csv(REPO_ROOT / "reference" / f"flood_events_{cfg.project.name}.csv")
    rows, items = [], []
    for ev in ref.itertuples():
        pre, event = event_windows(ev.start, ev.end)
        n_pre = s1_flood.scenes_in_window(ee, ctx.aoi, pre)
        n_ev = s1_flood.scenes_in_window(ee, ctx.aoi, event)
        row = ev._asdict()
        row.pop("Index")
        row.update({"s1_pre_scenes": n_pre, "s1_event_scenes": n_ev, "otsu_db": None})
        if ev.year not in cfg.years.years:
            row.update(usable=False, status="no forest map for this year")
        elif n_pre == 0 or n_ev == 0:
            row.update(usable=False, status="no Sentinel-1 coverage")
        else:
            mask, thr = s1_flood.flood_mask(
                ee, ctx.aoi, pre, event, refdata.DATASETS["jrc"], refdata.DATASETS["dem"]
            )
            frac = mask.toFloat().reduceResolution(ee.Reducer.mean(), maxPixels=64)
            items.append(
                (
                    f"flood_{ev.event_id}",
                    frac,
                    ctx.grid,
                    ctx.raw.flood_fraction(ev.event_id),
                    np.nan,
                    "COPERNICUS/S1_GRD",
                )
            )
            row.update(otsu_db=round(thr, 3), status="mapped")
        rows.append(row)
        ctx.log(f"{ev.event_id}: S1 pre {n_pre}, event {n_ev} -> {row['status']}")
    if items:
        if _assets_available(ctx):
            tasks = [
                submit_asset_export(
                    ee, _filled(img, ctx.aoi, -9999.0), asset_id(cfg, name), grid, name
                )
                for name, img, grid, *_ in items
            ]
            wait_for_tasks(ee, tasks)
            for name, _, grid, path, nodata, tags in items:
                download_asset(
                    asset_id(cfg, name),
                    grid,
                    path,
                    fetch=_nan_fetch(getpixels_fetch(ee)),
                    nodata=nodata,
                    tags={"DAIFF_SOURCE": tags},
                )
        else:
            _direct_download(ctx, items)
    jrc = read_raster(ctx.raw.jrc_occurrence, ctx.grid)
    for row in rows:
        if row["status"] != "mapped":
            continue
        f = read_raster(ctx.raw.flood_fraction(row["event_id"]), ctx.grid)
        f[jrc > 90] = np.nan
        share = float(np.nanmean(f >= cfg.flood.flooded_fraction_threshold))
        row["flooded_share"] = round(share, 5)
        row["usable"] = 0.0005 <= share <= 0.5  # implausible extents are not training labels
        if not row["usable"]:
            row["status"] = f"implausible flooded share {share:.4f}"
    out = pd.DataFrame(rows)
    out["split"] = np.where(out["year"] <= cfg.flood.train_until, "train", "test")
    out.to_csv(ctx.raw.flood_events_csv, index=False, lineterminator="\n")
    ctx.log(
        f"flood events: {int(out['usable'].sum())} usable of {len(out)} "
        f"-> {ctx.raw.flood_events_csv}"
    )


def step_rivers(ctx: Ctx) -> None:
    """OSM river/canal network for the FR-D4 check (Overpass API, not Earth Engine)."""
    from daiff.gee.aoi import lonlat_bounds
    from daiff.ingest.rivers import fetch_osm_rivers

    p = ctx.cfg.project
    w, s, e, n = lonlat_bounds(ctx.ee, p.aoi_hybas_id, p.aoi_hybas_level)
    fc = fetch_osm_rivers((s, w, n, e))
    out = ctx.raw.root / "osm_rivers.geojson"
    out.write_text(json.dumps(fc), "utf-8")
    ctx.log(f"OSM rivers: {len(fc['features'])} ways -> {out}")


def step_forest(ctx: Ctx) -> None:
    """Random-forest forest / non-forest at 10 m for every year (D-14)."""
    from daiff.gee import forest_rf
    from daiff.store.cog import read_raster, write_cog

    ee, cfg = ctx.ee, ctx.cfg
    years = ctx.years
    all_years = cfg.years.years  # training pools every year
    hansen = refdata.DATASETS["hansen"]
    # Training samples are fetched per year to a local CSV (cached), then sent inline with the
    # classification jobs. A batch table export of the same samples failed after ~65 EECU-h.
    cache = ctx.raw.root.parent / "interim" / "forest_training_points.csv"
    have = pd.read_csv(cache) if cache.exists() else pd.DataFrame()
    for y in all_years:
        if not have.empty and (have["year"] == y).any():
            continue
        pts = forest_rf.training_points(ee, ctx.aoi, [y], s2.composite, hansen, cfg.runtime.seed)
        rows = [f["properties"] for f in pts.getInfo()["features"]]
        df = pd.DataFrame(rows).assign(year=y)
        have = pd.concat([have, df], ignore_index=True)
        cache.parent.mkdir(parents=True, exist_ok=True)
        have.to_csv(cache, index=False, lineterminator="\n")
        ctx.log(f"training points {y}: {len(df)} ({df['label'].value_counts().to_dict()})")
    cols = [*forest_rf.FEATURES, "label"]
    points = ee.FeatureCollection(
        [
            ee.Feature(None, {k: float(r[k]) for k in cols})
            for r in have[cols].dropna().to_dict("records")
        ]
    )
    use_assets = _assets_available(ctx)
    items = []
    for y in years:
        img = forest_rf.classify(ee, s2.composite(ee, ctx.aoi, y), points, cfg.runtime.seed)
        items.append(
            (
                f"forest10m_{y}_raw",
                img,
                ctx.fine,
                ctx.raw.forest10m(y),
                255,
                f"forest:gee-rf-{forest_rf.N_TREES}t-seed{cfg.runtime.seed}",
            )
        )
    if use_assets:
        tasks = []
        for name, image, grid, *_ in items:
            tasks.append(
                submit_asset_export(
                    ee, _filled(image, ctx.aoi, 255), asset_id(cfg, name), grid, name
                )
            )
        wait_for_tasks(ee, tasks)
        for name, _, grid, path, nodata, tags in items:
            download_asset(
                asset_id(cfg, name),
                grid,
                path,
                fetch=getpixels_fetch(ee),
                nodata=nodata,
                tags={"DAIFF_SOURCE": tags},
            )
    else:
        _direct_download(ctx, items, tile=1024)
    dem = read_raster(ctx.raw.dem, ctx.grid)
    basin = np.repeat(np.repeat(~np.isnan(dem), 3, axis=0), 3, axis=1)  # 10 m footprint
    prev, report = None, {}
    for y in years:
        cur = read_raster(ctx.raw.forest10m(y), ctx.fine)
        filled, share = fill_gaps_from_previous(cur, prev, basin)
        if prev is not None:
            write_cog(
                ctx.raw.forest10m(y),
                filled,
                ctx.fine,
                nodata=255,
                tags={"DAIFF_SOURCE": items[0][5], "DAIFF_GAPFILL": "previous-year"},
            )
        report[y] = share
        prev = filled
        ctx.log(f"forest {y}: residual gap share {share:.2%}")
    (ctx.raw.root / "fr_d2_gap_share.json").write_text(json.dumps(report, indent=2), "utf-8")


STEPS = {
    "static": step_static,
    "coverage": step_coverage,
    "inventory": step_inventory,
    "dw": step_dw,
    "chirps": step_chirps,
    "cpc": step_cpc,
    "floods": step_floods,
    "rivers": step_rivers,
    "forest": step_forest,
}
