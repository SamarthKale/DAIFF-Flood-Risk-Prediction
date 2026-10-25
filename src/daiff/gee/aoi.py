"""AOI and sub-basins from HydroBASINS (OI-1, D-02, D-25).

The Kopili basin is HydroBASINS level-6 basin 4060884570 (19,706 km²); its level-8 children
(41 sub-basins) are the reporting units. Children are found by Pfafstetter code prefix.
"""

from __future__ import annotations

import json
from pathlib import Path

from rasterio.warp import transform

HYBAS = "WWF/HydroSHEDS/v1/Basins/hybas_{level}"


def pfaf_range(pfaf: int, parent_level: int, child_level: int) -> tuple[int, int]:
    k = 10 ** (child_level - parent_level)
    return pfaf * k, (pfaf + 1) * k


def utm_bounds(lonlat: tuple[float, float, float, float], crs: str) -> tuple[float, ...]:
    w, s, e, n = lonlat
    xs, ys = transform("EPSG:4326", crs, [w, e, w, e], [s, s, n, n])
    return min(xs), min(ys), max(xs), max(ys)


def basin_fc(ee, hybas_id: int, level: int):
    return ee.FeatureCollection(HYBAS.format(level=level)).filter(
        ee.Filter.eq("HYBAS_ID", hybas_id)
    )


def subbasins_fc(ee, hybas_id: int, level: int, child_level: int):
    pfaf = basin_fc(ee, hybas_id, level).first().get("PFAF_ID").getInfo()
    lo, hi = pfaf_range(int(pfaf), level, child_level)
    return (
        ee.FeatureCollection(HYBAS.format(level=child_level))
        .filter(ee.Filter.gte("PFAF_ID", lo))
        .filter(ee.Filter.lt("PFAF_ID", hi))
    )


def write_subbasins(ee, hybas_id: int, level: int, child_level: int, out: Path) -> dict:
    """Write RFC 7946 GeoJSON with `subbasin_id` (= HYBAS_ID), `name`, `area_km2`, `pfaf_id`."""
    fc = subbasins_fc(ee, hybas_id, level, child_level).getInfo()
    features = []
    for f in sorted(fc["features"], key=lambda f: f["properties"]["PFAF_ID"]):
        p = f["properties"]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "subbasin_id": int(p["HYBAS_ID"]),
                    "name": f"Kopili sub-basin {p['PFAF_ID']}",
                    "pfaf_id": int(p["PFAF_ID"]),
                    "area_km2": float(p["SUB_AREA"]),
                },
                "geometry": f["geometry"],
            }
        )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}), "utf-8")
    return {"count": len(features), "area_km2": sum(f["properties"]["area_km2"] for f in features)}


def lonlat_bounds(ee, hybas_id: int, level: int) -> tuple[float, float, float, float]:
    ring = basin_fc(ee, hybas_id, level).geometry().bounds().getInfo()["coordinates"][0]
    lons, lats = [p[0] for p in ring], [p[1] for p in ring]
    return min(lons), min(lats), max(lons), max(lats)
