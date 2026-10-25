"""Grid prediction, risk classes and change in susceptibility (FR-R2, FR-C3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

NODATA_CLASS = 255


def assemble_features(
    feats: Mapping[str, np.ndarray], features: Sequence[str]
) -> tuple[np.ndarray, np.ndarray]:
    """(n_cells, n_features) matrix in model order and the mask of fully valid rows."""
    stack = np.stack([np.asarray(feats[f], dtype=np.float64).ravel() for f in features], axis=1)
    return stack, np.isfinite(stack).all(axis=1)


def predict_grid(
    model,
    feats: Mapping[str, np.ndarray],
    features: Sequence[str],
    shape: tuple[int, int],
    tile_rows: int = 256,
) -> np.ndarray:
    """Susceptibility S per cell (float32, NaN where any feature is missing), in row tiles."""
    stack, valid = assemble_features(feats, features)
    out = np.full(stack.shape[0], np.nan, dtype=np.float32)
    step = max(1, tile_rows) * shape[1]
    for start in range(0, stack.shape[0], step):
        sl = slice(start, start + step)
        v = valid[sl]
        if v.any():
            block = out[sl]
            block[v] = model.predict_proba(stack[sl][v])[:, 1]
            out[sl] = block
    return out.reshape(shape)


def risk_classes(S: np.ndarray, breaks: Sequence[float]) -> np.ndarray:
    """Classes 1 (very low) … 5 (very high); 255 where S is NaN."""
    S = np.asarray(S, dtype=np.float64)
    cls = (np.digitize(np.nan_to_num(S, nan=0.0), breaks) + 1).astype(np.uint8)
    cls[np.isnan(S)] = NODATA_CLASS
    return cls


def delta_s(S_t: np.ndarray, S_t0: np.ndarray) -> np.ndarray:
    return (np.asarray(S_t, np.float64) - np.asarray(S_t0, np.float64)).astype(np.float32)
