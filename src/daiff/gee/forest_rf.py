"""Random-forest forest/non-forest classification in Earth Engine (D-14, FR-F1 inputs).

Training labels are automatic and high-confidence (spec §6.5); they are never used for
validation, which relies on the independent hand-labelled sample (SRS 7.3).
"""

from __future__ import annotations

import numpy as np

FOREST_TC, NONFOREST_TC = 30, 10  # Hansen treecover2000 (%)
DW_FOREST, DW_NONFOREST = 0.6, 0.2  # Dynamic World mean `trees` probability
N_TREES = 300
SAMPLES_PER_CLASS = 5000
FEATURES = ("B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12", "NDVI", "NBR")


def auto_label(treecover2000, lost_by_t, dw_trees) -> np.ndarray:
    """1 forest, 0 non-forest, 255 ambiguous (not used for training)."""
    tc, lost, dw = map(np.asarray, (treecover2000, lost_by_t, dw_trees))
    out = np.full(tc.shape, 255, dtype=np.uint8)
    out[((tc < NONFOREST_TC) | lost) & (dw < DW_NONFOREST)] = 0
    out[(tc >= FOREST_TC) & ~lost & (dw >= DW_FOREST)] = 1
    return out


def label_image(ee, year: int, hansen_id: str):
    """Earth Engine version of `auto_label` for season `year`."""
    from daiff.gee.s2 import season_window

    start, end = season_window(year)
    gfc = ee.Image(hansen_id)
    tc = gfc.select("treecover2000")
    lossyear = gfc.select("lossyear")  # 1..N = 2001..2000+N
    lost = lossyear.gt(0).And(lossyear.lte(year - 2000))
    dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterDate(start, end).select("trees").mean()
    forest = tc.gte(FOREST_TC).And(lost.Not()).And(dw.gte(DW_FOREST))
    nonforest = tc.lt(NONFOREST_TC).Or(lost).And(dw.lt(DW_NONFOREST))
    return ee.Image(255).where(nonforest, 0).where(forest, 1).rename("label").toByte()


N_RANDOM_POINTS = 30000  # per year; ~3-5 % get a confident auto label (D-29)


def training_points(ee, aoi, years, composite_fn, hansen_id: str, seed: int):
    """Composite features + auto labels at random points, pooled across years.

    `stratifiedSample` over the whole basin scans every pixel and cost ~350 EECU-hours for
    9 years; sampling at fixed random points only evaluates the composites there.
    """
    pts = None
    for y in years:
        img = (
            composite_fn(ee, aoi, y).select(list(FEATURES)).addBands(label_image(ee, y, hansen_id))
        )
        where = ee.FeatureCollection.randomPoints(aoi, N_RANDOM_POINTS, seed + y)
        s = img.sampleRegions(collection=where, scale=10, geometries=False)
        s = s.filter(ee.Filter.neq("label", 255))
        pts = s if pts is None else pts.merge(s)
    return pts


def classify(ee, composite_img, points, seed: int):
    clf = ee.Classifier.smileRandomForest(numberOfTrees=N_TREES, seed=seed).train(
        points, "label", list(FEATURES)
    )
    return composite_img.select(list(FEATURES)).classify(clf).rename("forest").toByte()
