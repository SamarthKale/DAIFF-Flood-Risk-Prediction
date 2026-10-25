"""NOAA CPC Global Unified daily precipitation (0.5°) per sub-basin (FR-D3, D-16)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from daiff.grid import Grid
from daiff.ingest.rainfall import cell_index_map, cpc_url, gridded_to_subbasin_daily

DECIMATE = 10  # sample every 10th 30 m cell (300 m) for area weights of 0.5° cells


def download(year: int, folder: Path, log: Callable[[str], None] = print) -> Path:
    out = Path(folder) / f"precip.{year}.nc"
    if out.exists() and out.stat().st_size > 1_000_000:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    with httpx.stream("GET", cpc_url(year), timeout=600, follow_redirects=True) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.replace(out)
    log(f"downloaded {out.name} ({out.stat().st_size / 1e6:.0f} MB)")
    return out


def read_subset(path: Path, lonlat_bounds: tuple[float, float, float, float]):
    """Daily precip (mm) for the bbox: returns values (t, ny, nx), dates, lat, lon (0-360)."""
    from netCDF4 import Dataset, num2date

    w, s, e, n = lonlat_bounds
    with Dataset(path) as ds:
        lat = ds["lat"][:].data
        lon = ds["lon"][:].data
        iy = np.where((lat >= s - 0.5) & (lat <= n + 0.5))[0]
        ix = np.where((lon >= (w % 360) - 0.5) & (lon <= (e % 360) + 0.5))[0]
        var = ds["precip"]
        vals = var[:, iy.min() : iy.max() + 1, ix.min() : ix.max() + 1]
        vals = np.ma.filled(vals.astype(float), np.nan)
        t = ds["time"]
        dates = pd.to_datetime([str(d)[:10] for d in num2date(t[:], t.units)])
    return vals, dates, lat[iy.min() : iy.max() + 1], lon[ix.min() : ix.max() + 1]


def ingest(
    grid: Grid,
    zones: np.ndarray,
    ids: Iterable[int],
    years: Iterable[int],
    folder: Path,
    lonlat_bounds: tuple[float, float, float, float],
    log: Callable[[str], None] = print,
) -> pd.DataFrame:
    coarse = Grid(
        grid.crs,
        grid.transform * grid.transform.scale(DECIMATE),
        grid.width // DECIMATE,
        grid.height // DECIMATE,
    )
    z = zones[: coarse.height * DECIMATE : DECIMATE, : coarse.width * DECIMATE : DECIMATE]
    frames, index = [], None
    for y in years:
        vals, dates, lat, lon = read_subset(download(y, folder, log), lonlat_bounds)
        if index is None:
            index = cell_index_map(lat, lon, coarse)
        frames.append(gridded_to_subbasin_daily(vals, dates, *index, z, list(ids)))
        log(f"CPC {y}: {len(dates)} days")
    return pd.concat(frames, ignore_index=True).sort_values(["subbasin_id", "date"])
