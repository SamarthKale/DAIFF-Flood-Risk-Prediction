"""Sub-basin rasterisation and zonal statistics."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from rasterio.features import rasterize
from rasterio.warp import transform_geom

from daiff.grid import Grid


def rasterize_subbasins(geojson_path: Path, grid: Grid) -> tuple[np.ndarray, pd.DataFrame]:
    """Sub-basin id per cell (0 = outside) and a frame of ids and names."""
    fc = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    shapes, rows = [], []
    for feat in fc["features"]:
        props = feat["properties"]
        sid = int(props["subbasin_id"])
        geom = transform_geom("EPSG:4326", grid.crs, feat["geometry"])
        shapes.append((geom, sid))
        rows.append({"subbasin_id": sid, "name": props.get("name", str(sid))})
    zones = rasterize(shapes, out_shape=grid.shape, transform=grid.transform, fill=0, dtype="int32")
    names = pd.DataFrame(rows).sort_values("subbasin_id").reset_index(drop=True)
    return zones, names


def zonal_sum(values: np.ndarray, zones: np.ndarray, ids: Sequence[int]) -> pd.Series:
    v = np.nan_to_num(np.asarray(values, dtype=float), nan=0.0)
    out = {i: float(v[zones == i].sum()) for i in ids}
    return pd.Series(out, dtype=float)


def zonal_mean(values: np.ndarray, zones: np.ndarray, ids: Sequence[int]) -> pd.Series:
    v = np.asarray(values, dtype=float)
    out = {}
    for i in ids:
        sel = v[(zones == i) & ~np.isnan(v)]
        out[i] = float(sel.mean()) if sel.size else np.nan
    return pd.Series(out, dtype=float)
