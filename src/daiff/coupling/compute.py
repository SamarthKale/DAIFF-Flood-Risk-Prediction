"""Compute coupling features for a year straight from the raw layout (shared by stages and the
synthetic flood generator)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from daiff.coupling.features import coupling_features
from daiff.coupling.rainfall import design_rainfall_by_subbasin, mean_annual_rainfall
from daiff.forest.change import block_fraction, forest_fraction, loss_mask, regrowth_mask
from daiff.grid import Grid
from daiff.store.cog import read_raster
from daiff.store.raw_layout import NESTED_FACTOR, RawLayout
from daiff.terrain.derive import Terrain


def mmu_pixels(mmu_ha: float) -> int:
    return int(round(mmu_ha / 0.01))


def rain_rasters(
    raw: RawLayout, zones: np.ndarray, ids: list[int], return_period: int
) -> dict[str, np.ndarray]:
    """Per-cell design rainfall (mm) and mean annual rainfall from the sub-basin daily series."""
    daily = pd.read_csv(raw.chirps_daily_csv)
    p = design_rainfall_by_subbasin(daily, return_period)
    m = mean_annual_rainfall(daily)
    p_r = np.full(zones.shape, np.nan)
    m_r = np.full(zones.shape, np.nan)
    for sid in ids:
        sel = zones == sid
        p_r[sel] = p.get(sid, np.nan)
        m_r[sel] = m.get(sid, np.nan)
    return {"rain_p10y_1d": p_r, "rain_mean_annual": m_r}


@dataclass
class YearForest:
    f: np.ndarray  # forest fraction 30 m
    loss10m: np.ndarray  # MMU-filtered loss since t0 (uint8, 255 nodata)
    regrowth10m: np.ndarray | None
    dF: np.ndarray  # loss fraction 30 m


def forest_for_year(
    raw: RawLayout, grid: Grid, t0: int, year: int, mmu_px: int, forest10m=None
) -> YearForest:
    fine = grid.nested(NESTED_FACTOR)
    base = read_raster(raw.forest10m(t0), fine)
    cur = read_raster(raw.forest10m(year), fine) if forest10m is None else forest10m
    loss = loss_mask(base, cur, mmu_px)
    return YearForest(
        f=forest_fraction(cur),
        loss10m=loss,
        regrowth10m=regrowth_mask(base, cur),
        dF=block_fraction(loss),
    )


def coupling_for_year(
    raw: RawLayout,
    grid: Grid,
    terrain: Terrain,
    p_mm: np.ndarray,
    yf: YearForest,
    year: int,
    dw_class: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    dw = read_raster(raw.dw_class(year), grid) if dw_class is None else dw_class
    hsg = np.nan_to_num(terrain.bands["hsg"], nan=0).astype(np.uint8)
    return coupling_features(
        yf.f, None, yf.dF, dw, hsg, terrain.dirs, terrain.order, p_mm, grid.cell_area_m2
    )
