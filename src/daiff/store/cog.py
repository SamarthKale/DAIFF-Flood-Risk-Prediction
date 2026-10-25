"""Cloud-optimised GeoTIFF writing and grid-checked reading (spec §5)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import rasterio
import rasterio.shutil
from rasterio.io import MemoryFile

from daiff.grid import Grid, check_alignment

BAND_NAMES_TAG = "DAIFF_BAND_NAMES"


class GridMismatchError(ValueError):
    """A raster is not on the expected project grid."""


def write_cog(
    path: Path,
    array: np.ndarray,
    grid: Grid,
    *,
    nodata: float | int,
    tags: Mapping[str, str],
    band_names: Sequence[str] | None = None,
) -> Path:
    path = Path(path)
    data = array[np.newaxis] if array.ndim == 2 else array
    if data.ndim != 3 or data.shape[1:] != grid.shape:
        raise ValueError(f"array shape {array.shape} does not match grid shape {grid.shape}")
    if band_names is not None and len(band_names) != data.shape[0]:
        raise ValueError("band_names length must equal the number of bands")
    is_int = np.issubdtype(data.dtype, np.integer)
    all_tags = dict(tags)
    if band_names is not None:
        all_tags[BAND_NAMES_TAG] = json.dumps(list(band_names))
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "width": grid.width,
        "height": grid.height,
        "count": data.shape[0],
        "dtype": data.dtype.name,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": nodata,
    }
    with MemoryFile() as mem:
        with mem.open(**profile) as dst:
            dst.write(data)
            dst.update_tags(**all_tags)
            if band_names is not None:
                for i, name in enumerate(band_names, start=1):
                    dst.set_band_description(i, name)
        with mem.open() as src:
            rasterio.shutil.copy(
                src,
                str(path),
                driver="COG",
                COMPRESS="DEFLATE",
                PREDICTOR="YES",
                BLOCKSIZE="512",
                OVERVIEWS="AUTO",
                RESAMPLING="NEAREST" if is_int else "AVERAGE",
                NUM_THREADS="1",
            )
    return path


def read_raster(path: Path, grid: Grid) -> np.ndarray:
    report = check_alignment([Path(path)], grid)
    if not report.ok:
        p = report.problems[0]
        raise GridMismatchError(f"{path}: {p.field} expected {p.expected}, got {p.actual}")
    with rasterio.open(path) as src:
        data = src.read()
    return data[0] if data.shape[0] == 1 else data


def read_tags(path: Path) -> dict[str, str]:
    with rasterio.open(path) as src:
        return dict(src.tags())


def read_band_names(path: Path) -> list[str]:
    tags = read_tags(path)
    if BAND_NAMES_TAG in tags:
        return json.loads(tags[BAND_NAMES_TAG])
    with rasterio.open(path) as src:
        return [d or "" for d in src.descriptions]
