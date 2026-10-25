"""Deterministic synthetic basin (spec §6.16).

Writes raw inputs in exactly the `RawLayout` the Earth Engine stage produces, so every local
stage, the API and the dashboard can be developed and tested without Earth Engine.
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
from rasterio.warp import transform_geom

from daiff.config import DaiffConfig
from daiff.grid import Grid
from daiff.store.cog import write_cog
from daiff.store.raw_layout import NESTED_FACTOR, RawLayout

# Dynamic World labels
DW_WATER, DW_TREES, DW_GRASS, DW_CROPS = 0, 1, 2, 4


def _dem(n: int, rng: np.random.Generator) -> np.ndarray:
    r, c = np.mgrid[0:n, 0:n]
    x = c / (n - 1) - 0.5
    y = r / (n - 1)
    z = 400 - 250 * y + 120 * np.abs(x) ** 1.2 + rng.normal(0, 0.5, (n, n))
    mid = n // 2
    channel = z[:, mid] - 5
    for i in range(1, n):  # strictly decreasing southward
        channel[i] = min(channel[i], channel[i - 1] - 0.01)
    z[:, mid] = channel
    z[-1, mid] = min(z.min(), z[-1, mid]) - 0.01
    return z.astype("float32")


def _forest_maps(n: int, years: list[int], t0: int, rng: np.random.Generator) -> dict:
    m = n * NESTED_FACTOR
    r, c = np.mgrid[0:m, 0:m]
    x = c / (m - 1) - 0.5
    y = r / (m - 1)
    base = np.ones((m, m), dtype="uint8")
    base[np.abs(x) < 0.03] = 0
    base[y > 0.7] = 0
    north = int(0.6 * m)
    cleared = np.zeros((m, m), dtype=bool)
    maps = {}
    for idx, year in enumerate(years):
        k = year - t0
        if k > 0:
            for _ in range(k):  # 60 x 60 px = 3.6 ha patches
                i, j = rng.integers(0, north - 60), rng.integers(0, m - 60)
                cleared[i : i + 60, j : j + 60] = True
            for _ in range(3):  # 4 x 4 px = 0.16 ha, below the MMU
                i, j = rng.integers(0, north - 4), rng.integers(0, m - 4)
                cleared[i : i + 4, j : j + 4] = True
        f = base.copy()
        f[cleared] = 0
        if idx == 2:  # one cloud gap
            f[30:60, 30:60] = 255
        maps[year] = f
    return maps


def _dw_class(forest10m: np.ndarray, n: int) -> np.ndarray:
    blocks = (forest10m == 1).reshape(n, NESTED_FACTOR, n, NESTED_FACTOR).sum(axis=(1, 3))
    r, c = np.mgrid[0:n, 0:n]
    y = r / (n - 1)
    out = np.full((n, n), DW_GRASS, dtype="uint8")
    out[y > 0.7] = DW_CROPS
    out[blocks >= 5] = DW_TREES
    out[:, n // 2] = DW_WATER
    return out


def _hsg(n: int) -> np.ndarray:
    r, c = np.mgrid[0:n, 0:n]
    q = max(n // 4, 1)
    hsg = (1 + ((r // q) + (c // q)) % 4).astype("uint8")
    x = c / (n - 1) - 0.5
    hsg[np.abs(x) < 0.05] = 4
    return hsg


def _jrc(n: int) -> np.ndarray:
    c = np.mgrid[0:n, 0:n][1]
    x = c / (n - 1) - 0.5
    out = np.zeros((n, n), dtype="uint8")
    out[np.abs(x) < 0.05] = 40
    out[:, n // 2] = 95
    return out


def _subbasins(grid: Grid, split: int) -> dict:
    xmin, ymin, xmax, ymax = grid.bounds
    dx, dy = (xmax - xmin) / split, (ymax - ymin) / split
    features = []
    for i in range(split * split):
        row, col = divmod(i, split)
        x0, y1 = xmin + col * dx, ymax - row * dy
        ring = [[x0, y1], [x0 + dx, y1], [x0 + dx, y1 - dy], [x0, y1 - dy], [x0, y1]]
        geom = transform_geom(grid.crs, "EPSG:4326", {"type": "Polygon", "coordinates": [ring]})
        features.append(
            {
                "type": "Feature",
                "properties": {"subbasin_id": 1000 + i, "name": f"Synthetic sub-basin {i + 1}"},
                "geometry": geom,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _rainfall(ids: list[int], end: date, rng: np.random.Generator) -> pd.DataFrame:
    dates = pd.date_range(date(2000, 1, 1), end, freq="D")
    monsoon = dates.month.isin([6, 7, 8, 9]).astype(float)
    frames = []
    for sid in ids:
        wet = rng.random(len(dates)) < 0.15 + 0.6 * monsoon
        amount = rng.gamma(0.8, 12 + 25 * monsoon)
        precip = np.round(np.where(wet, amount, 0.0), 1)
        frames.append(
            pd.DataFrame(
                {"date": dates.strftime("%Y-%m-%d"), "subbasin_id": sid, "precip_mm": precip}
            )
        )
    return pd.concat(frames, ignore_index=True)


def make_basin(cfg: DaiffConfig) -> RawLayout:
    if cfg.synthetic is None:
        raise ValueError("config has no 'synthetic' section")
    n = cfg.synthetic.size
    seed = cfg.runtime.seed
    rng = np.random.default_rng(seed)
    grid = Grid.from_config(cfg)
    if grid.shape != (n, n):
        raise ValueError(f"grid shape {grid.shape} does not match synthetic.size {n}")
    fine = grid.nested(NESTED_FACTOR)
    raw = RawLayout(cfg.data_root)
    raw.write_grid(grid)
    tags = {"DAIFF_SOURCE": "synthetic", "DAIFF_SEED": str(seed)}
    years = cfg.years.years

    write_cog(raw.dem, _dem(n, rng), grid, nodata=np.nan, tags=tags)
    write_cog(raw.hsg, _hsg(n), grid, nodata=255, tags=tags)
    write_cog(raw.jrc_occurrence, _jrc(n), grid, nodata=255, tags=tags)
    forest = _forest_maps(n, years, cfg.years.t0, rng)
    for year in years:
        write_cog(raw.forest10m(year), forest[year], fine, nodata=255, tags=tags)
        write_cog(raw.dw_class(year), _dw_class(forest[year], n), grid, nodata=255, tags=tags)

    fc = _subbasins(grid, cfg.synthetic.subbasin_split)
    raw.subbasins.write_text(json.dumps(fc), encoding="utf-8")
    ids = [f["properties"]["subbasin_id"] for f in fc["features"]]
    raw.chirps_daily_csv.parent.mkdir(parents=True, exist_ok=True)
    rain = _rainfall(ids, date(years[-1], 3, 31), rng)
    rain.to_csv(raw.chirps_daily_csv, index=False, lineterminator="\n")
    return raw
