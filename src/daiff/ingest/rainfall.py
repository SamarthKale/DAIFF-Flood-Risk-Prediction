"""Daily rainfall ingestion (FR-D3): NOAA CPC Global Unified and CHIRPS, gap detection."""

from __future__ import annotations

import numpy as np
import pandas as pd
from rasterio.warp import transform

from daiff.grid import Grid

CPC_URL = "https://downloads.psl.noaa.gov/Datasets/cpc_global_precip/precip.{year}.nc"


def cpc_url(year: int) -> str:
    return CPC_URL.format(year=year)


def find_gaps(daily: pd.DataFrame, max_gap_days: int = 3) -> pd.DataFrame:
    """Runs of missing days longer than `max_gap_days`, per sub-basin."""
    rows = []
    for sid, g in daily.groupby("subbasin_id"):
        have = pd.DatetimeIndex(pd.to_datetime(g["date"])).sort_values()
        full = pd.date_range(have.min(), have.max(), freq="D")
        missing = full.difference(have)
        if missing.empty:
            continue
        run_id = (missing.to_series().diff() != pd.Timedelta(days=1)).cumsum()
        for _, run in missing.to_series().groupby(run_id.values):
            if len(run) > max_gap_days:
                rows.append(
                    {
                        "subbasin_id": int(sid),
                        "start": run.iloc[0].strftime("%Y-%m-%d"),
                        "end": run.iloc[-1].strftime("%Y-%m-%d"),
                        "days": int(len(run)),
                    }
                )
    return pd.DataFrame(rows, columns=["subbasin_id", "start", "end", "days"])


def cell_index_map(lat: np.ndarray, lon: np.ndarray, grid: Grid) -> tuple[np.ndarray, np.ndarray]:
    """Index of the coarse (lat, lon) cell containing each grid cell centre (nearest centre)."""
    rows, cols = np.mgrid[0 : grid.height, 0 : grid.width]
    x = grid.transform.c + (cols + 0.5) * grid.res
    y = grid.transform.f - (rows + 0.5) * grid.res
    lons, lats = transform(grid.crs, "EPSG:4326", x.ravel().tolist(), y.ravel().tolist())
    lons = np.mod(np.asarray(lons), 360) if lon.max() > 180 else np.asarray(lons)
    iy = np.abs(np.asarray(lats)[:, None] - lat[None, :]).argmin(axis=1)
    ix = np.abs(lons[:, None] - lon[None, :]).argmin(axis=1)
    return iy.reshape(grid.shape), ix.reshape(grid.shape)


def gridded_to_subbasin_daily(
    values: np.ndarray, dates, iy: np.ndarray, ix: np.ndarray, zones: np.ndarray, ids
) -> pd.DataFrame:
    """Area-weighted daily means per sub-basin: each 30 m cell takes its coarse cell's value."""
    frames = []
    for sid in ids:
        sel = zones == sid
        if not sel.any():
            continue
        pairs, counts = np.unique(np.stack([iy[sel], ix[sel]]), axis=1, return_counts=True)
        w = counts / counts.sum()
        series = (values[:, pairs[0], pairs[1]] * w).sum(axis=1)
        frames.append(
            pd.DataFrame(
                {
                    "date": pd.to_datetime(dates).strftime("%Y-%m-%d"),
                    "subbasin_id": sid,
                    "precip_mm": np.round(series, 2),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)
