"""Stratified random reference sample (SRS 7.3; Olofsson et al. 2014)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from rasterio.warp import transform

from daiff.grid import Grid

STRATA = {1: "stable_forest", 2: "stable_non_forest", 3: "loss"}


def allocate(
    pixel_counts: dict[int, int], n_total: int = 600, min_per_stratum: int = 150
) -> dict[int, int]:
    """Proportional allocation, each stratum raised to at least `min_per_stratum`."""
    total = sum(pixel_counts.values())
    return {
        s: min(c, max(min_per_stratum, round(n_total * c / total)))
        for s, c in pixel_counts.items()
        if c > 0
    }


def strata_map(forest_t0: np.ndarray, forest_t: np.ndarray, loss10m: np.ndarray) -> np.ndarray:
    """1 stable forest, 2 stable non-forest, 3 loss (MMU-filtered), 0 other/nodata."""
    out = np.zeros(forest_t0.shape, dtype=np.uint8)
    out[(forest_t0 == 1) & (forest_t == 1)] = 1
    out[(forest_t0 == 0) & (forest_t == 0)] = 2
    out[loss10m == 1] = 3
    return out


def stratified_sample(
    strata: np.ndarray,
    grid: Grid,
    n_total: int = 600,
    min_per_stratum: int = 150,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    counts = {s: int((strata == s).sum()) for s in STRATA}
    alloc = allocate(counts, n_total, min_per_stratum)
    rows = []
    for s, n in sorted(alloc.items()):
        idx = np.sort(rng.choice(np.flatnonzero(strata.ravel() == s), size=n, replace=False))
        r, c = np.divmod(idx, grid.width)
        for rr, cc in zip(r, c, strict=True):
            rows.append({"row": int(rr), "col": int(cc), "stratum": s})
    df = pd.DataFrame(rows)
    df["x"] = grid.transform.c + (df["col"] + 0.5) * grid.res
    df["y"] = grid.transform.f - (df["row"] + 0.5) * grid.res
    lon, lat = transform(grid.crs, "EPSG:4326", df["x"].tolist(), df["y"].tolist())
    df["lon"], df["lat"] = np.round(lon, 7), np.round(lat, 7)
    df.insert(0, "point_id", [f"P{i:04d}" for i in range(1, len(df) + 1)])
    return df[["point_id", "row", "col", "x", "y", "lon", "lat", "stratum"]]


def stratum_weights(strata: np.ndarray) -> dict[int, float]:
    counts = {s: int((strata == s).sum()) for s in STRATA}
    total = sum(counts.values())
    return {s: c / total for s, c in counts.items() if c > 0}
