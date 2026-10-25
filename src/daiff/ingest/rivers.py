"""OSM river network for the FR-D4 stream-network check."""

from __future__ import annotations

import numpy as np
from scipy import ndimage

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    """bbox = (south, west, north, east) in degrees."""
    s, w, n, e = bbox
    return f'[out:json][timeout:180];way["waterway"~"river|canal"]({s},{w},{n},{e});out geom;'


def stream_agreement(
    derived: np.ndarray, osm: np.ndarray, res: float, tol_m: float = 60.0
) -> float:
    """FR-D4: share of derived stream cells lying within `tol_m` of a mapped river cell."""
    derived = np.asarray(derived, bool)
    if not derived.any():
        return float("nan")
    dist = ndimage.distance_transform_edt(~np.asarray(osm, bool)) * res
    return float((dist[derived] <= tol_m).mean())
