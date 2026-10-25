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

    @property
    def fine(self) -> Grid:
        return self.grid.nested(NESTED_FACTOR)


def make_ctx(ee, cfg: DaiffConfig, log: Log = print) -> Ctx:
    p = cfg.project
    aoi = basin_fc(ee, p.aoi_hybas_id, p.aoi_hybas_level).geometry()
    return Ctx(ee, cfg, Grid.from_config(cfg), RawLayout(cfg.data_root), aoi, log)


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
        for y in ctx.cfg.years.years
    ]
    _export_and_download(ctx, items)


def step_inventory(ctx: Ctx) -> None:
    for y in ctx.cfg.years.years:
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


def fill_gaps_from_previous(cur: np.ndarray, prev: np.ndarray | None) -> tuple[np.ndarray, float]:
    """Cloud gaps (255) take the previous year's class; returns map and residual gap share
    inside the valid footprint (FR-D2 ≤ 5 %)."""
    out = cur.copy()
    if prev is not None:
        gap = (out == 255) & (prev != 255)
        out[gap] = prev[gap]
    footprint = prev != 255 if prev is not None else np.ones(out.shape, bool)
    share = float(((out == 255) & footprint).sum() / max(footprint.sum(), 1))
    return out, share


def step_forest(ctx: Ctx) -> None:
    """Random-forest forest / non-forest at 10 m for every year (D-14)."""
    from daiff.gee import forest_rf
    from daiff.store.cog import read_raster, write_cog

    ee, cfg = ctx.ee, ctx.cfg
    years = cfg.years.years
    hansen = refdata.DATASETS["hansen"]
    points = forest_rf.training_points(ee, ctx.aoi, years, s2.composite, hansen, cfg.runtime.seed)
    use_assets = _assets_available(ctx)
    if use_assets:
        table = asset_id(cfg, "forest_training_points")
        if not asset_exists(ee, table):
            task = ee.batch.Export.table.toAsset(points, "forest_training_points", table)
            task.start()
            ctx.log("exporting training points")
            wait_for_tasks(ee, [task.id])
        points = ee.FeatureCollection(table)
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
    prev, report = None, {}
    for y in years:
        cur = read_raster(ctx.raw.forest10m(y), ctx.fine)
        filled, share = fill_gaps_from_previous(cur, prev)
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
    "forest": step_forest,
}
