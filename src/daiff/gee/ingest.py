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


def _export_and_download(ctx: Ctx, items: list[tuple]) -> None:
    """items: (name, image, grid, local_path, nodata, tags)."""
    ensure_folders(ctx.ee, asset_root(ctx.cfg))
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
            ("hsg", refdata.hsg_image(ee), ctx.grid, r.hsg, 255, refdata.DATASETS["hysogs"]),
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
    """Daily CHIRPS mean per sub-basin, one reduceRegions call per year."""
    ee = ctx.ee
    subs = ee.FeatureCollection(json.loads(ctx.raw.subbasins.read_text("utf-8")))
    frames = []
    last = max(ctx.cfg.years.years)
    for y in range(start_year, last + 1):
        col = ee.ImageCollection(refdata.DATASETS["chirps"]).filterDate(
            f"{y}-01-01", f"{y + 1}-01-01"
        )

        def per_day(img):
            fc = img.reduceRegions(subs, ee.Reducer.mean(), scale=5566)
            date = img.date().format("YYYY-MM-dd")
            return fc.map(
                lambda feat: ee.Feature(
                    None,
                    {
                        "date": date,
                        "subbasin_id": feat.get("subbasin_id"),
                        "precip_mm": feat.get("mean"),
                    },
                )
            )

        rows = col.map(per_day).flatten().getInfo()["features"]
        frames.append(pd.DataFrame([row["properties"] for row in rows]))
        ctx.log(f"CHIRPS {y}: {len(rows)} sub-basin-days")
    df = pd.concat(frames, ignore_index=True).sort_values(["subbasin_id", "date"])
    df["precip_mm"] = df["precip_mm"].astype(float).round(2)
    ctx.raw.chirps_daily_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ctx.raw.chirps_daily_csv, index=False, lineterminator="\n")


STEPS = {
    "static": step_static,
    "coverage": step_coverage,
    "inventory": step_inventory,
    "dw": step_dw,
    "chirps": step_chirps,
}
