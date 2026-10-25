"""Sentinel-1 flood mapping per event: VV decrease + Otsu threshold (SRS 7.4)."""

from __future__ import annotations

import numpy as np


def otsu_threshold(counts: np.ndarray, edges: np.ndarray) -> float:
    """Threshold maximising between-class variance of a histogram (Otsu 1979)."""
    counts = np.asarray(counts, dtype=float)
    centers = (np.asarray(edges[:-1]) + np.asarray(edges[1:])) / 2
    w0 = np.cumsum(counts)
    w1 = counts.sum() - w0
    m0 = np.cumsum(counts * centers) / np.maximum(w0, 1e-12)
    m1 = (np.sum(counts * centers) - np.cumsum(counts * centers)) / np.maximum(w1, 1e-12)
    between = w0 * w1 * (m0 - m1) ** 2
    return float(centers[int(np.argmax(between[:-1]))])


def vv_difference(ee, aoi, pre: tuple[str, str], event: tuple[str, str]):
    """Event-minimum VV minus pre-event median VV (dB), 50 m focal mean speckle smoothing."""
    col = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select("VV")
    )
    before = col.filterDate(*pre).median()
    during = col.filterDate(*event).min()
    return during.subtract(before).focalMean(50, "circle", "meters").clip(aoi)


def flood_mask(ee, aoi, pre, event, jrc_id: str, dem_id: str, scale: float = 30.0):
    """Binary flood mask: Otsu on the VV difference; no permanent water, no slopes > 5°."""
    diff = vv_difference(ee, aoi, pre, event)
    hist = (
        diff.reduceRegion(ee.Reducer.histogram(255), aoi, scale, maxPixels=1e10, bestEffort=True)
        .get("VV")
        .getInfo()
    )
    thr = otsu_threshold(
        np.array(hist["histogram"]), np.array(hist["bucketMeans"] + [hist["bucketMeans"][-1]])
    )
    permanent = ee.Image(jrc_id).select("occurrence").gt(90)
    steep = ee.Terrain.slope(ee.Image(dem_id)).gt(5)
    return diff.lt(thr).And(permanent.Not()).And(steep.Not()).rename("flood").toByte(), thr


def scenes_in_window(ee, aoi, window: tuple[str, str]) -> int:
    col = ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(aoi).filterDate(*window)
    return int(col.size().getInfo())
