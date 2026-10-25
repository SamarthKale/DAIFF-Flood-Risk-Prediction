"""Reference layers clipped to the grid: SRTM, HYSOGs, JRC, Hansen, Dynamic World (spec §6.5)."""

from __future__ import annotations

import numpy as np

# HYSOGs250m codes: 1-4 = A-D; 11-14 = A/D, B/D, C/D, D/D -> D (D-23)
HSG_REMAP = {1: 1, 2: 2, 3: 3, 4: 4, 11: 4, 12: 4, 13: 4, 14: 4}

DATASETS = {
    "dem": "USGS/SRTMGL1_003",
    "jrc": "JRC/GSW1_4/GlobalSurfaceWater",
    "hansen": "UMD/hansen/global_forest_change_2024_v1_12",
    "dynamic_world": "GOOGLE/DYNAMICWORLD/V1",
    "worldcover": "ESA/WorldCover/v200",
    "chirps": "UCSB-CHG/CHIRPS/DAILY",
    "hysogs": "projects/sat-io/open-datasets/HYSOGs250m",  # verify on first live run (P3)
}


def remap_hsg(codes: np.ndarray) -> np.ndarray:
    out = np.full(np.shape(codes), 255, dtype=np.uint8)
    for src, dst in HSG_REMAP.items():
        out[np.asarray(codes) == src] = dst
    return out


def dem_image(ee):
    return ee.Image(DATASETS["dem"]).select("elevation").resample("bilinear").toFloat()


def hsg_image(ee):
    img = ee.Image(DATASETS["hysogs"])
    return img.remap(list(HSG_REMAP), list(HSG_REMAP.values()), 255).toByte()


def jrc_image(ee):
    return ee.Image(DATASETS["jrc"]).select("occurrence").unmask(0).toByte()


def hansen_images(ee):
    gfc = ee.Image(DATASETS["hansen"])
    return gfc.select("treecover2000").toByte(), gfc.select("lossyear").toByte()


def dw_mode_image(ee, year: int):
    from daiff.gee.s2 import season_window

    start, end = season_window(year)
    col = ee.ImageCollection(DATASETS["dynamic_world"]).filterDate(start, end).select("label")
    return col.mode().unmask(255).toByte()
