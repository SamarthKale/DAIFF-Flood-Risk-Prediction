import numpy as np
import pandas as pd

from daiff.forest.change import (
    block_fraction,
    forest_fraction,
    hansen_comparison,
    loss_hectares_by_subbasin,
    loss_mask,
    regrowth_mask,
)


def test_forest_fraction_ignores_nodata():
    a = np.array([[1, 1, 1], [0, 0, 0], [255, 255, 255]], dtype="uint8")
    b = np.full((3, 3), 255, dtype="uint8")
    f = forest_fraction(np.hstack([a, b]))
    assert f.shape == (1, 2)
    assert f[0, 0] == 0.5 and np.isnan(f[0, 1])


def test_fr_f4_loss_patches_below_mmu_removed():
    y1 = np.ones((30, 30), dtype="uint8")
    y2 = y1.copy()
    y2[0:8, 0:8] = 0  # 64 px, kept
    y2[15:22, 15:22] = 0  # 49 px, removed
    y2[22, 22] = 0  # touches the 49 px patch diagonally -> 50 px, kept
    m = loss_mask(y1, y2, mmu_px=50)
    assert m[0:8, 0:8].all() and m[15:22, 15:22].all() and m[22, 22] == 1
    y2b = y1.copy()
    y2b[15:22, 15:22] = 0
    assert loss_mask(y1, y2b, mmu_px=50).sum() == 0


def test_loss_mask_nodata_is_255():
    y1 = np.array([[1, 255]], dtype="uint8")
    y2 = np.array([[0, 0]], dtype="uint8")
    assert loss_mask(y1, y2, mmu_px=1).tolist() == [[1, 255]]


def test_regrowth_mask():
    y1 = np.array([[0, 1, 0]], dtype="uint8")
    y2 = np.array([[1, 1, 0]], dtype="uint8")
    assert regrowth_mask(y1, y2).tolist() == [[1, 0, 0]]


def test_block_fraction_matches_forest_fraction():
    m = np.zeros((3, 6), dtype="uint8")
    m[:, :3] = 1
    assert block_fraction(m).tolist() == [[1.0, 0.0]]


def test_fr_f3_hectares_equal_loss_pixel_sum():
    rng = np.random.default_rng(0)
    loss = (rng.random((60, 60)) < 0.2).astype("uint8")
    zones = np.repeat(np.repeat(np.array([[1, 2], [3, 0]], dtype="int32"), 10, 0), 10, 1)
    ha = loss_hectares_by_subbasin(loss, zones)
    inside = loss.reshape(20, 3, 20, 3).sum(axis=(1, 3))[zones > 0].sum()
    assert abs(ha.sum() - inside * 0.01) <= 0.005 * inside * 0.01
    assert list(ha.index) == [1, 2, 3]


def test_hansen_comparison():
    assert hansen_comparison(120.0, 100.0) == {"diff_pct": 20.0, "within_25pct": True}
    assert hansen_comparison(130.0, 100.0)["within_25pct"] is False
    assert isinstance(pd.Series([1.0]), pd.Series)
