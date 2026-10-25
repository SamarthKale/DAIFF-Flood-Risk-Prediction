"""Slope, TWI, streams, HAND and distance to river; the static feature stack (spec §6.7)."""

from __future__ import annotations

from dataclasses import dataclass

import numba
import numpy as np
from scipy import ndimage

from daiff.grid import Grid
from daiff.store.cog import read_raster
from daiff.store.raw_layout import RawLayout
from daiff.terrain.flow import (
    accumulate,
    d8_directions,
    downstream_index,
    fill_depressions,
    topological_order,
)

STATIC_BANDS = ("elevation", "slope", "twi", "hand", "dist_river", "hsg")


def _pad_linear(z: np.ndarray) -> np.ndarray:
    """Pad by one cell with linear extrapolation so edge slopes equal interior slopes."""
    p = np.pad(z, 1, mode="edge").astype(np.float64)
    p[0, 1:-1] = 2 * z[0] - z[1] if z.shape[0] > 1 else z[0]
    p[-1, 1:-1] = 2 * z[-1] - z[-2] if z.shape[0] > 1 else z[-1]
    p[:, 0] = 2 * p[:, 1] - p[:, 2] if z.shape[1] > 1 else p[:, 1]
    p[:, -1] = 2 * p[:, -2] - p[:, -3] if z.shape[1] > 1 else p[:, -2]
    return p


def slope_degrees(dem: np.ndarray, res: float) -> np.ndarray:
    """Horn (1981) slope in degrees."""
    p = _pad_linear(np.asarray(dem, dtype=np.float64))
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * res)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * res)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


def twi(acc_cells: np.ndarray, slope_deg: np.ndarray, res: float) -> np.ndarray:
    """Topographic wetness index ln(a / tan β), a = specific catchment area (m)."""
    a = acc_cells * res
    tan_b = np.maximum(np.tan(np.radians(slope_deg)), 0.001)
    return np.log(a / tan_b)


def streams(acc_cells: np.ndarray, cell_area_m2: float, threshold_km2: float) -> np.ndarray:
    return acc_cells * cell_area_m2 / 1e6 > threshold_km2


@numba.njit(cache=True)
def _hand_ref(z: np.ndarray, recv: np.ndarray, order: np.ndarray, stream: np.ndarray):
    ref = np.full(z.size, np.nan)
    for k in range(order.size - 1, -1, -1):  # downstream first
        i = order[k]
        if stream[i]:
            ref[i] = z[i]
        elif recv[i] >= 0:
            ref[i] = ref[recv[i]]
    return ref


def hand(
    dem: np.ndarray, dirs: np.ndarray, stream_mask: np.ndarray, order: np.ndarray
) -> np.ndarray:
    """Height above nearest drainage along D8 paths; NaN where no stream lies downstream."""
    z = np.asarray(dem, dtype=np.float64).ravel()
    recv = downstream_index(dirs)
    ref = _hand_ref(z, recv, order, np.asarray(stream_mask, bool).ravel())
    return np.clip(z - ref, 0, None).reshape(dem.shape)


def distance_to_stream(stream_mask: np.ndarray, res: float) -> np.ndarray:
    return ndimage.distance_transform_edt(~np.asarray(stream_mask, bool)) * res


@dataclass
class Terrain:
    bands: dict[str, np.ndarray]
    dirs: np.ndarray
    order: np.ndarray
    streams: np.ndarray


def build_static_features(
    raw: RawLayout, grid: Grid, stream_threshold_km2: float, routing: str = "srtm"
) -> Terrain:
    """Static features. `routing="merit"` routes flow on the MERIT Hydro conditioned surface
    (raw/dem_merit_hydro.tif) while elevation and slope stay SRTM (D-30)."""
    dem = read_raster(raw.dem, grid).astype(np.float64)
    hsg = read_raster(raw.hsg, grid).astype(np.float64)
    hsg[hsg == 255] = np.nan
    route = dem
    if routing == "merit":
        route = read_raster(raw.dem_hydro, grid).astype(np.float64)
        route[np.isnan(dem)] = np.nan
    filled = fill_depressions(route)
    dirs = d8_directions(filled, grid.res)
    order = topological_order(dirs)
    acc = accumulate(dirs, np.where(np.isnan(route), np.nan, 1.0), order)
    mask = streams(acc, grid.cell_area_m2, stream_threshold_km2)
    slope = slope_degrees(fill_depressions(dem), grid.res)
    bands = {
        "elevation": dem,
        "slope": slope,
        "twi": twi(acc, slope, grid.res),
        "hand": hand(route, dirs, mask, order),
        "dist_river": distance_to_stream(mask, grid.res),
        "hsg": hsg,
    }
    return Terrain(bands=bands, dirs=dirs, order=order, streams=mask)
