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
    "merit_hydro": "MERIT/Hydro/v1_0_1",
    "soilgrids_sand": "projects/soilgrids-isric/sand_mean",
    "soilgrids_clay": "projects/soilgrids-isric/clay_mean",
}
TOPSOIL = (("0-5cm", 5), ("5-15cm", 10), ("15-30cm", 15))  # depth-weighted 0-30 cm


def hsg_from_texture(sand_pct, clay_pct) -> np.ndarray:
    """Hydrologic soil group from topsoil texture (TR-55 texture classes; D-28).

    D: clay > 40 %; C: clay 20-40 %; A: sand >= 90 % and clay < 10 %; otherwise B.
    """
    sand, clay = np.asarray(sand_pct, float), np.asarray(clay_pct, float)
    out = np.full(sand.shape, 2, dtype=np.uint8)
    out[(sand >= 90) & (clay < 10)] = 1
    out[clay >= 20] = 3
    out[clay > 40] = 4
    return out


def remap_hsg(codes: np.ndarray) -> np.ndarray:
    out = np.full(np.shape(codes), 255, dtype=np.uint8)
    for src, dst in HSG_REMAP.items():
        out[np.asarray(codes) == src] = dst
    return out


def dem_image(ee):
    return ee.Image(DATASETS["dem"]).select("elevation").resample("bilinear").toFloat()


def _topsoil(ee, asset: str, var: str):
    img = ee.Image(asset)
    total = sum(w for _, w in TOPSOIL)
    acc = None
    for depth, w in TOPSOIL:
        band = img.select(f"{var}_{depth}_mean").multiply(w / total)
        acc = band if acc is None else acc.add(band)
    return acc.divide(10)  # g/kg -> %


def hsg_image(ee):
    """SoilGrids topsoil texture -> HSG 1-4 (same rule as `hsg_from_texture`)."""
    sand = _topsoil(ee, DATASETS["soilgrids_sand"], "sand")
    clay = _topsoil(ee, DATASETS["soilgrids_clay"], "clay")
    hsg = (
        ee.Image(2)
        .where(sand.gte(90).And(clay.lt(10)), 1)
        .where(clay.gte(20), 3)
        .where(clay.gt(40), 4)
    )
    return hsg.updateMask(sand.mask()).toByte()


def merit_elv_image(ee):
    """MERIT Hydro hydrologically adjusted elevation, for flow routing only (D-30)."""
    return ee.Image(DATASETS["merit_hydro"]).select("elv").resample("bilinear").toFloat()


def jrc_image(ee):
    return ee.Image(DATASETS["jrc"]).select("occurrence").unmask(0).toByte()


def hansen_images(ee):
    gfc = ee.Image(DATASETS["hansen"])
    # lossyear: 0 = no loss, 1..24 = 2001..2024 (unmask so "no loss" is 0, not nodata)
    return gfc.select("treecover2000").toByte(), gfc.select("lossyear").unmask(0).toByte()


def dw_mode_image(ee, year: int):
    from daiff.gee.s2 import season_window

    start, end = season_window(year)
    col = ee.ImageCollection(DATASETS["dynamic_world"]).filterDate(start, end).select("label")
    return col.mode().unmask(255).toByte()
