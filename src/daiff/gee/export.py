"""Batch export to Earth Engine assets and tiled download onto the project grid (D-10)."""

from __future__ import annotations

import io
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
from rasterio.windows import Window

from daiff.config import DaiffConfig
from daiff.grid import Grid
from daiff.store.cog import read_tags, write_cog

Fetch = Callable[[str, Window, Grid], np.ndarray]  # -> (bands, h, w)


def asset_root(cfg: DaiffConfig) -> str:
    return cfg.gee.asset_root or f"projects/{cfg.gee.project}/assets/daiff/{cfg.project.name}"


def asset_id(cfg: DaiffConfig, name: str) -> str:
    return f"{asset_root(cfg)}/{name}"


def tile_windows(grid: Grid, tile: int = 2048) -> list[Window]:
    return [
        Window(c, r, min(tile, grid.width - c), min(tile, grid.height - r))
        for r in range(0, grid.height, tile)
        for c in range(0, grid.width, tile)
    ]


def getpixels_fetch(ee, bands: Sequence[str] | None = None) -> Fetch:
    """A Fetch that reads one window of an exported asset with ee.data.getPixels (NPY)."""

    def fetch(asset: str, window: Window, grid: Grid) -> np.ndarray:
        t = grid.transform
        x0 = t.c + window.col_off * t.a
        y0 = t.f + window.row_off * t.e
        request = {
            "assetId": asset,
            "fileFormat": "NPY",
            "grid": {
                "dimensions": {"width": int(window.width), "height": int(window.height)},
                "affineTransform": {
                    "scaleX": t.a,
                    "shearX": 0,
                    "translateX": x0,
                    "shearY": 0,
                    "scaleY": t.e,
                    "translateY": y0,
                },
                "crsCode": grid.crs,
            },
        }
        if bands:
            request["bandIds"] = list(bands)
        raw = ee.data.getPixels(request)
        arr = np.load(io.BytesIO(raw)) if isinstance(raw, bytes | bytearray) else raw
        names = arr.dtype.names or ()
        return np.stack([arr[n] for n in names]) if names else arr[np.newaxis]

    return fetch


def compute_fetch(ee, image) -> Fetch:
    """A Fetch that computes `image` directly for each window (no asset; ee.data.computePixels)."""

    def fetch(_asset: str, window: Window, grid: Grid) -> np.ndarray:
        t = grid.transform
        request = {
            "expression": image,
            "fileFormat": "NUMPY_NDARRAY",
            "grid": {
                "dimensions": {"width": int(window.width), "height": int(window.height)},
                "affineTransform": {
                    "scaleX": t.a,
                    "shearX": 0,
                    "translateX": t.c + window.col_off * t.a,
                    "shearY": 0,
                    "scaleY": t.e,
                    "translateY": t.f + window.row_off * t.e,
                },
                "crsCode": grid.crs,
            },
        }
        for attempt in range(4):
            try:
                arr = ee.data.computePixels(request)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        names = arr.dtype.names or ()
        return np.stack([arr[n] for n in names]) if names else arr[np.newaxis]

    return fetch


def download_asset(
    asset: str,
    grid: Grid,
    path: Path,
    *,
    fetch: Fetch,
    tile: int = 2048,
    nodata: float | int,
    tags: dict[str, str] | None = None,
    band_names: Sequence[str] | None = None,
) -> Path:
    """Mosaic an asset onto `grid` tile by tile; skip if `path` already holds this asset."""
    path = Path(path)
    if path.exists() and read_tags(path).get("DAIFF_ASSET") == asset:
        return path
    out = None
    for w in tile_windows(grid, tile):
        block = fetch(asset, w, grid)
        if out is None:
            out = np.full((block.shape[0], *grid.shape), nodata, dtype=block.dtype)
        out[:, w.row_off : w.row_off + w.height, w.col_off : w.col_off + w.width] = block
    data = out[0] if out.shape[0] == 1 else out
    all_tags = {**(tags or {}), "DAIFF_ASSET": asset}
    return write_cog(path, data, grid, nodata=nodata, tags=all_tags, band_names=band_names)


def asset_exists(ee, asset: str) -> bool:
    try:
        ee.data.getAsset(asset)
        return True
    except Exception:
        return False


def submit_asset_export(ee, image, asset: str, grid: Grid, description: str) -> str | None:
    """Start a batch export of `image` on `grid` to `asset`; None if it already exists."""
    if asset_exists(ee, asset):
        return None
    t = grid.transform
    task = ee.batch.Export.image.toAsset(
        image=image,
        description=description[:100],
        assetId=asset,
        crs=grid.crs,
        crsTransform=[t.a, t.b, t.c, t.d, t.e, t.f],
        dimensions=f"{grid.width}x{grid.height}",
        maxPixels=1e13,
    )
    task.start()
    return task.id


def wait_for_tasks(ee, task_ids: Sequence[str], poll_s: float = 30.0) -> None:
    pending = [t for t in task_ids if t]
    while pending:
        states = {s["id"]: s for s in ee.data.getTaskList() if s["id"] in pending}
        for tid, s in states.items():
            if s["state"] in ("FAILED", "CANCELLED"):
                raise RuntimeError(
                    f"Earth Engine task {tid} {s['state']}: {s.get('error_message')}"
                )
        pending = [t for t in pending if states.get(t, {}).get("state") != "COMPLETED"]
        if pending:
            time.sleep(poll_s)
