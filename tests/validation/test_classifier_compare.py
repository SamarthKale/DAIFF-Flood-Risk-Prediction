import numpy as np
import pandas as pd
import pytest

from daiff.validation.forest_accuracy import stratified_binary_report
from daiff.validation.run import compare_with_unet


def test_fr_f1_stratified_binary_report_weights_strata_by_area():
    # stratum 1 (90 % of area): map says forest; stratum 2 (10 %): map says non-forest.
    strata = np.array([1] * 10 + [2] * 10)
    map_forest = np.array([True] * 10 + [False] * 10)
    ref_forest = np.array([True] * 9 + [False] + [False] * 8 + [True] * 2)
    r = stratified_binary_report(strata, map_forest, ref_forest, {1: 0.9, 2: 0.1})
    assert r["overall_accuracy"] == pytest.approx(0.9 * 0.9 + 0.1 * 0.8)
    # forest F1 from area-weighted confusion: tp=.81 fp=.09 fn=.02
    assert r["forest_f1"] == pytest.approx(2 * 0.81 / (2 * 0.81 + 0.09 + 0.02))


def test_fr_f1_compare_with_unet_picks_higher_forest_f1():
    pts = pd.DataFrame(
        {"stratum": [1, 1, 2, 2], "p_rf_forest": [True, True, False, False]},
        index=pd.Index(["P1", "P2", "P3", "P4"], name="point_id"),
    )
    ref = pd.Series([True, True, False, False], index=pts.index)  # RF perfect
    unet = pd.Series([0.9, 0.2, 0.1, 0.1], index=pts.index)  # U-Net misses P2
    out = compare_with_unet(pts, ref, unet, {1: 0.5, 2: 0.5})
    assert out["selected"] == "random_forest"
    assert out["random_forest"]["forest_f1"] > out["unet"]["forest_f1"]
