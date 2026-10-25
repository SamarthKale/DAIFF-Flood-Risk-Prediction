import numpy as np
import pandas as pd
import pytest

from daiff.coupling.features import coupling_features, curve_number, scs_runoff, upstream_loss
from daiff.coupling.rainfall import (
    design_rainfall_by_subbasin,
    gumbel_design_rainfall,
    mean_annual_rainfall,
)

CELL = 900.0


def east_dirs(h, w):
    d = np.ones((h, w), dtype="uint8")
    d[:, -1] = 0
    return d


def test_fr_c1_upstream_loss_matches_hand_computed():
    dF = np.zeros((10, 10))
    dF[0] = [0.0, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    U = upstream_loss(dF, east_dirs(10, 10), CELL)
    expected = [
        0,
        0.5,
        0.5,
        0.375,
        0.3,
        0.25,
        0.2142857142857143,
        0.1875,
        0.16666666666666666,
        0.25,
    ]
    assert U[0] == pytest.approx(expected, abs=1e-9)
    assert (U[1:] == 0).all()


def test_fr_c1_nan_loss_excluded():
    U = upstream_loss(np.array([[np.nan, 1.0, 0.0]]), east_dirs(1, 3), CELL)
    assert np.isnan(U[0, 0])
    assert U[0, 1:].tolist() == [1.0, 0.5]


def test_fr_c1_curve_number_and_runoff_hand_computed():
    f = np.array([[1.0, 0.0, 0.5, 0.0]])
    dw = np.array([[1, 4, 4, 0]], dtype="uint8")  # trees, crops, crops, water
    hsg = np.full((1, 4), 2, dtype="uint8")  # group B
    cn = curve_number(f, dw, hsg)
    assert cn[0, :3].tolist() == [55.0, 78.0, 66.5] and np.isnan(cn[0, 3])
    q = scs_runoff(cn, 100.0)
    assert q[0, :3] == pytest.approx([12.8253, 46.657, 27.360], abs=1e-3)
    assert scs_runoff(np.array([30.0]), 10.0)[0] == 0.0


def test_gumbel_design_rainfall_k10():
    x = np.array([80.0, 120.0])
    x = 100 + (x - x.mean()) / x.std(ddof=1) * 20  # mean 100, sample std 20
    assert gumbel_design_rainfall(x, 10) == pytest.approx(126.09, abs=0.01)


def test_design_and_mean_rainfall_by_subbasin():
    dates = pd.date_range("2000-01-01", "2001-12-31", freq="D")
    df = pd.DataFrame({"date": dates, "subbasin_id": 1, "precip_mm": 1.0})
    df.loc[df.date == "2000-07-01", "precip_mm"] = 80.0
    df.loc[df.date == "2001-07-01", "precip_mm"] = 120.0
    p = design_rainfall_by_subbasin(df, 10)
    assert p.loc[1] > 120.0
    m = mean_annual_rainfall(df)
    assert m.loc[1] == pytest.approx((365 + 80 + 364 + 120) / 2)


def test_coupling_monotone_in_loss():
    h, w = 1, 5
    dirs = east_dirs(h, w)
    f0 = np.full((h, w), 0.9)
    dw = np.full((h, w), 4, dtype="uint8")  # crops, so CN depends on f
    hsg = np.full((h, w), 3, dtype="uint8")
    p = np.full((h, w), 150.0)
    base = coupling_features(f0, f0, np.zeros((h, w)), dw, hsg, dirs, None, p, CELL)
    loss = np.zeros((h, w))
    loss[0, 1] = 0.6
    more = coupling_features(f0 - loss, f0, loss, dw, hsg, dirs, None, p, CELL)
    for k in ("dF", "U", "CN", "Q"):
        assert (more[k] >= base[k] - 1e-12).all(), k
    assert (more["f"] <= base["f"]).all()
