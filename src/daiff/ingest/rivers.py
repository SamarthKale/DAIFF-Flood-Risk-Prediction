"""OSM river network for the FR-D4 stream-network check."""

from __future__ import annotations

import numpy as np
from scipy import ndimage

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    """bbox = (south, west, north, east) in degrees."""
    s, w, n, e = bbox
    return f'[out:json][timeout:180];way["waterway"~"river|canal"]({s},{w},{n},{e});out geom;'


def fetch_osm_rivers(bbox: tuple[float, float, float, float], timeout: float = 300) -> dict:
    """GeoJSON FeatureCollection of OSM river/canal ways (EPSG:4326) from Overpass."""
    import httpx

    headers = {
        "User-Agent": "DAIFF research prototype "
        "(github.com/SamarthKale/DAIFF-Flood-Risk-Prediction)",
        "Accept": "application/json",
    }
    r = httpx.post(
        OVERPASS_URL, data={"data": overpass_query(bbox)}, headers=headers, timeout=timeout
    )
    r.raise_for_status()
    feats = []
    for el in r.json().get("elements", []):
        if el.get("type") == "way" and el.get("geometry"):
            coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
            feats.append(
                {
                    "type": "Feature",
                    "properties": {"osm_id": el["id"], "name": el.get("tags", {}).get("name", "")},
                    "geometry": {"type": "LineString", "coordinates": coords},
                }
            )
    return {"type": "FeatureCollection", "features": feats}


def rasterize_lines(fc: dict, grid) -> np.ndarray:
    from rasterio.features import rasterize
    from rasterio.warp import transform_geom

    shapes = [(transform_geom("EPSG:4326", grid.crs, f["geometry"]), 1) for f in fc["features"]]
    if not shapes:
        return np.zeros(grid.shape, bool)
    out = rasterize(
        shapes,
        out_shape=grid.shape,
        transform=grid.transform,
        fill=0,
        all_touched=True,
        dtype="uint8",
    )
    return out.astype(bool)


def stream_agreement(
    derived: np.ndarray, osm: np.ndarray, res: float, tol_m: float = 60.0
) -> float:
    """FR-D4: share of derived stream cells lying within `tol_m` of a mapped river cell."""
    derived = np.asarray(derived, bool)
    if not derived.any():
        return float("nan")
    dist = ndimage.distance_transform_edt(~np.asarray(osm, bool)) * res
    return float((dist[derived] <= tol_m).mean())
