import hashlib

import numpy as np
import pandas as pd
import pytest

from daiff.config import load_config
from daiff.store.cog import read_raster
from daiff.synthetic import make_basin
from daiff.terrain.derive import build_static_features
from tests.conftest import SYN_CONFIG


@pytest.fixture(scope="module")
def basin(tmp_path_factory):
    root = tmp_path_factory.mktemp("synf")
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(root)})
    return cfg, make_basin(cfg)


def test_five_events_with_train_test_split(basin):
    _, raw = basin
    ev = pd.read_csv(raw.flood_events_csv)
    assert list(ev["event_id"]) == [f"syn_{y}" for y in (2020, 2021, 2022, 2023, 2024)]
    assert list(ev["split"]) == ["train", "train", "test", "test", "test"]
    assert ev["usable"].all()


def test_masks_have_both_classes_and_favour_low_hand(basin):
    cfg, raw = basin
    grid = raw.read_grid()
    hand = build_static_features(raw, grid, cfg.terrain.stream_threshold_km2).bands["hand"]
    for eid in pd.read_csv(raw.flood_events_csv)["event_id"]:
        m = read_raster(raw.flood_fraction(eid), grid)
        valid = ~np.isnan(m)
        assert 0.01 <= m[valid].mean() <= 0.99
        low = valid & (hand < 5)
        high = valid & (hand >= 5)
        assert m[low].mean() > m[high].mean()


def test_flood_masks_are_deterministic(basin, tmp_path):
    cfg, raw = basin
    raw2 = make_basin(load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)}))
    a = raw.flood_fraction("syn_2022").read_bytes()
    b = raw2.flood_fraction("syn_2022").read_bytes()
    assert hashlib.sha256(a).digest() == hashlib.sha256(b).digest()
