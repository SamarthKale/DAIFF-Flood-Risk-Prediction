import hashlib
from datetime import date

import numpy as np
import pandas as pd
import pytest

from daiff.config import load_config
from daiff.grid import Grid, check_alignment
from daiff.store.cog import read_raster
from daiff.synthetic import make_basin
from tests.conftest import SYN_CONFIG


@pytest.fixture(scope="module")
def basin(tmp_path_factory):
    root = tmp_path_factory.mktemp("syn")
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(root)})
    return cfg, make_basin(cfg)


def test_writes_every_raw_layer(basin):
    cfg, raw = basin
    years = cfg.years.years
    paths = [raw.grid_json, raw.chirps_daily_csv, raw.subbasins]
    for p in [*paths, *raw.layers_30m(years), *raw.layers_10m(years)]:
        assert p.exists(), p


def test_fr_d5_synthetic_layers_are_aligned(basin):
    cfg, raw = basin
    grid = raw.read_grid()
    assert grid == Grid.from_config(cfg)
    assert check_alignment(raw.layers_30m(cfg.years.years), grid).ok
    assert check_alignment(raw.layers_10m(cfg.years.years), grid.nested(3)).ok


def test_is_deterministic_for_a_seed(basin, tmp_path):
    cfg, raw = basin
    raw2 = make_basin(load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)}))
    years = cfg.years.years
    for a, b in zip(raw.layers_30m(years), raw2.layers_30m(years), strict=True):
        assert hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def test_forest_declines_after_t0(basin):
    cfg, raw = basin
    fine = raw.read_grid().nested(3)

    def share(year):
        a = read_raster(raw.forest10m(year), fine)
        return a[a != 255].mean()

    assert share(cfg.years.years[-1]) <= share(cfg.years.t0) - 0.02


def test_dem_drains_to_south_outlet(basin):
    _, raw = basin
    dem = read_raster(raw.dem, raw.read_grid())
    n = dem.shape[1]
    assert dem[-1, n // 2] == dem.min()


def test_rainfall_is_gap_free_from_2000(basin):
    cfg, raw = basin
    df = pd.read_csv(raw.chirps_daily_csv, parse_dates=["date"])
    end = date(cfg.years.years[-1], 3, 31)
    expected_days = (end - date(2000, 1, 1)).days + 1
    assert df["date"].min().date() == date(2000, 1, 1) and df["date"].max().date() == end
    assert (df.groupby("subbasin_id").size() == expected_days).all()
    assert df["subbasin_id"].nunique() == cfg.synthetic.subbasin_split**2
    assert (df["precip_mm"] >= 0).all() and np.isfinite(df["precip_mm"]).all()
