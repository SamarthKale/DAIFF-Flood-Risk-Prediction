import numpy as np
import pandas as pd

from daiff.alerts.flags import flags
from daiff.flood.predict import risk_classes
from daiff.flood.tables import TABLE_COLUMNS, subbasin_table

BREAKS = [0.2, 0.4, 0.6, 0.8]


def _inputs():
    zones = np.array([[1, 1, 2, 2], [1, 1, 2, 2], [3, 3, 0, 0]], dtype="int32")
    names = pd.DataFrame({"subbasin_id": [1, 2, 3, 4], "name": ["Āmchang", "B", "C", "Empty"]})
    S = np.array([[0.9, 0.85, 0.1, 0.3], [0.7, 0.95, 0.1, 0.1], [np.nan, np.nan, 0.5, 0.5]])
    S0 = np.array([[0.5, 0.85, 0.1, 0.1], [0.7, 0.95, 0.1, 0.1], [np.nan, np.nan, 0.5, 0.5]])
    f = np.full(S.shape, 0.5)
    loss = pd.Series({1: 12.5, 2: 0.0, 3: 1.0})
    return zones, names, loss, f, S, S0


def _table():
    zones, names, loss, f, S, S0 = _inputs()
    return subbasin_table(
        zones,
        names,
        loss,
        f,
        S,
        S - S0,
        risk_classes(S, BREAKS),
        risk_classes(S0, BREAKS),
        BREAKS,
        900.0,
    )


def test_table_has_table25_columns_and_one_row_per_subbasin():
    t = _table()
    assert list(t.columns) == TABLE_COLUMNS
    assert list(t["subbasin_id"]) == [1, 2, 3, 4]
    assert t.loc[0, "name"] == "Āmchang" and t.loc[0, "forest_loss_ha"] == 12.5


def test_area_classes_sum_to_area():
    t = _table()
    classes = t[[f"area_class_{i}" for i in range(1, 6)]].sum(axis=1)
    valid_area = np.array([4, 4, 0, 0]) * 900 / 1e6
    assert np.allclose(classes, valid_area)
    assert np.allclose(t["area_km2"], np.array([4, 4, 2, 0]) * 900 / 1e6)
    assert t.loc[0, "area_moved_up_km2"] == 900 / 1e6


def test_empty_subbasin_row_is_nan_and_not_flagged():
    t = _table()
    for sid in (3, 4):
        row = t[t["subbasin_id"] == sid].iloc[0]
        assert np.isnan(row["mean_s"]) and row["risk_flag"] == "no" and row["risk_class"] == 255


def test_fr_a1_flags_match_risk_map():
    t = _table()
    expected = [int(r.subbasin_id) for r in t.itertuples() if r.risk_class in (4, 5)]
    assert flags(t) == expected == [1]
    assert list(t["risk_flag"]) == ["yes", "no", "no", "no"]
