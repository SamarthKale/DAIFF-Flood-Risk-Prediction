"""Sentinel-2 L2A dry-season composites (FR-D1, FR-D2; D-18)."""

from __future__ import annotations

SCL_MASK_CLASSES = (0, 1, 3, 8, 9, 10)  # no data, saturated, cloud shadow, cloud med/high, cirrus
BANDS = ("B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12")
COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
MAX_SCENE_CLOUD = 40  # skip mostly-cloudy scenes: fewer images per median, lower EECU cost
MAX_SCENES_PER_TILE = 12  # least-cloudy scenes kept per MGRS tile per season (D-29)


def season_window(year: int, start_month: int = 11, end_month: int = 3) -> tuple[str, str]:
    """Forest map `year` = dry season 1 Nov (year−1) to 31 Mar (year); end is exclusive."""
    return f"{year - 1}-{start_month:02d}-01", f"{year}-{end_month + 1:02d}-01"


def masked_collection(ee, aoi, year: int):
    start, end = season_window(year)

    def mask(img):
        scl = img.select("SCL")
        bad = ee.Image(0)
        for c in SCL_MASK_CLASSES:
            bad = bad.Or(scl.eq(c))
        return img.updateMask(bad.Not()).select(list(BANDS)).divide(10000)

    base = (
        ee.ImageCollection(COLLECTION)
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", MAX_SCENE_CLOUD))
    )
    tiles = base.aggregate_array("MGRS_TILE").distinct()

    def best(tile):
        return (
            base.filter(ee.Filter.eq("MGRS_TILE", tile))
            .sort("CLOUDY_PIXEL_PERCENTAGE")
            .limit(MAX_SCENES_PER_TILE)
        )

    kept = ee.ImageCollection(ee.FeatureCollection(tiles.map(best)).flatten())
    return kept.map(mask)


def composite(ee, aoi, year: int):
    """Median composite + NDVI and NBR (float reflectance)."""
    med = masked_collection(ee, aoi, year).median()
    ndvi = med.normalizedDifference(["B8", "B4"]).rename("NDVI")
    nbr = med.normalizedDifference(["B8", "B12"]).rename("NBR")
    return med.addBands([ndvi, nbr]).clip(aoi)


def inventory(ee, aoi, year: int) -> list[dict]:
    """FR-D1: scenes used for a season (id, MGRS tile, date, cloud %)."""
    start, end = season_window(year)
    col = ee.ImageCollection(COLLECTION).filterBounds(aoi).filterDate(start, end)
    info = (
        col.reduceColumns(
            ee.Reducer.toList(4),
            ["system:index", "MGRS_TILE", "GENERATION_TIME", "CLOUDY_PIXEL_PERCENTAGE"],
        )
        .get("list")
        .getInfo()
    )
    return [
        {"scene": a, "mgrs_tile": b, "generation_time": c, "cloud_pct": d} for a, b, c, d in info
    ]


def coverage_fraction(ee, aoi, year: int, scale: float = 300.0) -> float:
    """Share of the AOI with at least one clear observation in the season (OI-2, FR-D2)."""
    valid = masked_collection(ee, aoi, year).select("B4").count().gt(0).unmask(0)
    return float(
        valid.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e10).get("B4").getInfo()
    )
