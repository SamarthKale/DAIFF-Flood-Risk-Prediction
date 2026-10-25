"""Coupling features C1–C3 — the only path from forest change to the flood model (SRS ch. 3)."""

from __future__ import annotations

import numpy as np

from daiff.terrain.flow import accumulate

# SRS Appendix B (TR-55 Table 2-2, ARC II): hydrologic soil groups A, B, C, D
CN_TABLE: dict[str, tuple[int, int, int, int]] = {
    "woods": (30, 55, 70, 77),
    "pasture": (39, 61, 74, 80),
    "row_crops": (67, 78, 85, 89),
    "fallow": (77, 86, 91, 94),
    "impervious": (98, 98, 98, 98),
}

# Dynamic World label -> TR-55 cover type (None = excluded, e.g. water)
DW_TO_TR55: dict[int, str | None] = {
    0: None,  # water
    1: "woods",  # trees
    2: "pasture",  # grass
    3: "pasture",  # flooded_vegetation
    4: "row_crops",  # crops
    5: "pasture",  # shrub_and_scrub
    6: "impervious",  # built
    7: "fallow",  # bare
    8: "fallow",  # snow_and_ice
}


def upstream_loss(
    dF: np.ndarray, dirs: np.ndarray, cell_area: float, order: np.ndarray | None = None
) -> np.ndarray:
    """C2: area-weighted share of the contributing area (including the cell) lost since t0."""
    dF = np.asarray(dF, dtype=np.float64)
    valid = ~np.isnan(dF)
    num = accumulate(dirs, np.where(valid, cell_area * dF, 0.0), order)
    den = accumulate(dirs, np.where(valid, cell_area, 0.0), order)
    with np.errstate(invalid="ignore", divide="ignore"):
        u = np.where(den > 0, num / den, np.nan)
    u[~valid] = np.nan
    return u


def _cn_lookup(cover: str | None, hsg: np.ndarray) -> np.ndarray:
    if cover is None:
        return np.full(hsg.shape, np.nan)
    table = np.array([np.nan, *CN_TABLE[cover]], dtype=np.float64)
    idx = np.where((hsg >= 1) & (hsg <= 4), hsg, 0).astype(np.int64)
    return table[idx]


def curve_number(f: np.ndarray, dw_class: np.ndarray, hsg: np.ndarray) -> np.ndarray:
    """C3 curve number, area-weighted by forest fraction (D-22); water/nodata -> NaN."""
    hsg = np.asarray(hsg)
    woods = _cn_lookup("woods", hsg)
    nonforest = np.full(hsg.shape, np.nan)
    for label, cover in DW_TO_TR55.items():
        sel = dw_class == label
        if sel.any():
            nonforest[sel] = _cn_lookup(cover, hsg)[sel]
    f = np.asarray(f, dtype=np.float64)
    return f * woods + (1.0 - f) * nonforest


def scs_runoff(cn: np.ndarray, p_mm: np.ndarray | float) -> np.ndarray:
    """SCS runoff depth Q (mm), Eqs. (2) and (3)."""
    cn = np.asarray(cn, dtype=np.float64)
    p = np.broadcast_to(np.asarray(p_mm, dtype=np.float64), cn.shape)
    with np.errstate(invalid="ignore", divide="ignore"):
        s = 25400.0 / cn - 254.0
        q = np.where(p > 0.2 * s, (p - 0.2 * s) ** 2 / (p + 0.8 * s), 0.0)
    q[np.isnan(cn)] = np.nan
    return q


def coupling_features(
    f: np.ndarray,
    f_t0: np.ndarray,
    loss_frac: np.ndarray,
    dw_class: np.ndarray,
    hsg: np.ndarray,
    dirs: np.ndarray,
    order: np.ndarray | None,
    p_mm: np.ndarray,
    cell_area: float,
) -> dict[str, np.ndarray]:
    """C1 (f, dF), C2 (U), C3 (CN, Q) for one year. `f_t0` is kept for symmetry with ΔS runs."""
    del f_t0  # ΔF comes from the MMU-filtered loss map (D-20)
    cn = curve_number(f, dw_class, hsg)
    return {
        "f": np.asarray(f, dtype=np.float64),
        "dF": np.asarray(loss_frac, dtype=np.float64),
        "U": upstream_loss(loss_frac, dirs, cell_area, order),
        "CN": cn,
        "Q": scs_runoff(cn, p_mm),
    }
