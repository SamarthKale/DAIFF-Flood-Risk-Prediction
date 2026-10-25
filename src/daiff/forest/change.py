"""Forest fraction, MMU-filtered loss, regrowth and loss statistics (spec §6.8, D-20)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import ndimage

NODATA = 255
FACTOR = 3  # 10 m pixels per 30 m cell side
PIXEL_HA = 0.01  # one 10 m pixel


def _blocks(a: np.ndarray) -> np.ndarray:
    h, w = a.shape
    return a.reshape(h // FACTOR, FACTOR, w // FACTOR, FACTOR)


def block_fraction(mask10m: np.ndarray) -> np.ndarray:
    """Share of valid (≠255) pixels equal to 1 in each 3×3 block; NaN if none valid."""
    b = _blocks(np.asarray(mask10m))
    valid = (b != NODATA).sum(axis=(1, 3))
    ones = (b == 1).sum(axis=(1, 3))
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(valid > 0, ones / np.maximum(valid, 1), np.nan)
    return out.astype(np.float32)


def forest_fraction(forest10m: np.ndarray) -> np.ndarray:
    """f(c, t): share of forest pixels in each 30 m cell."""
    return block_fraction(forest10m)


def loss_mask(f_y1: np.ndarray, f_y2: np.ndarray, mmu_px: int) -> np.ndarray:
    """Forest at y1 and non-forest at y2, 8-connected patches smaller than the MMU removed."""
    valid = (f_y1 != NODATA) & (f_y2 != NODATA)
    loss = valid & (f_y1 == 1) & (f_y2 == 0)
    labels, n = ndimage.label(loss, structure=np.ones((3, 3), dtype=bool))
    if n:
        sizes = np.bincount(labels.ravel())
        keep = sizes >= mmu_px
        keep[0] = False
        loss = keep[labels]
    out = loss.astype(np.uint8)
    out[~valid] = NODATA
    return out


def regrowth_mask(f_y1: np.ndarray, f_y2: np.ndarray) -> np.ndarray:
    valid = (f_y1 != NODATA) & (f_y2 != NODATA)
    out = (valid & (f_y1 == 0) & (f_y2 == 1)).astype(np.uint8)
    out[~valid] = NODATA
    return out


def loss_hectares_by_subbasin(loss10m: np.ndarray, zones30: np.ndarray) -> pd.Series:
    """Loss area (ha) per sub-basin id (> 0); exactly loss-pixel count × 0.01 (FR-F3)."""
    counts = _blocks(np.asarray(loss10m) == 1).sum(axis=(1, 3))
    ids = np.unique(zones30[zones30 > 0])
    sums = ndimage.sum(counts, labels=zones30, index=ids)
    return pd.Series(np.asarray(sums, dtype=float) * PIXEL_HA, index=ids, name="forest_loss_ha")


def hansen_comparison(ours_ha: float, hansen_ha: float) -> dict:
    diff = 100.0 * (ours_ha - hansen_ha) / hansen_ha if hansen_ha else float("inf")
    return {"diff_pct": round(diff, 6), "within_25pct": bool(abs(diff) <= 25.0)}
