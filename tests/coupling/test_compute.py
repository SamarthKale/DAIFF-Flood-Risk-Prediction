import numpy as np
import pytest

from daiff.config import load_config
from daiff.coupling.compute import (
    coupling_for_year,
    forest_for_year,
    mmu_pixels,
    rain_rasters,
)
from daiff.synthetic import make_basin
from daiff.terrain.derive import build_static_features
from daiff.zones import rasterize_subbasins
from tests.conftest import SYN_CONFIG


@pytest.fixture(scope="module")
def syn(tmp_path_factory):
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path_factory.mktemp("cc"))})
    raw = make_basin(cfg)
    grid = raw.read_grid()
    return cfg, raw, grid


def test_mmu_pixels():
    assert mmu_pixels(0.5) == 50


def test_rain_rasters_fill_each_subbasin(syn):
    cfg, raw, grid = syn
    zones, names = rasterize_subbasins(raw.subbasins, grid)
    r = rain_rasters(raw, zones, list(names["subbasin_id"]), 10)
    for band in ("rain_p10y_1d", "rain_mean_annual"):
        assert np.isfinite(r[band][zones > 0]).all()
        assert len(np.unique(r[band][zones > 0])) == 4


def test_forest_for_t0_has_no_loss_and_later_year_has_some(syn):
    cfg, raw, grid = syn
    same = forest_for_year(raw, grid, 2019, 2019, 50)
    assert np.nansum(same.dF) == 0
    later = forest_for_year(raw, grid, 2019, 2024, 50)
    assert np.nansum(later.dF) > 0
    assert later.f.shape == grid.shape and later.loss10m.shape == grid.nested(3).shape


def test_coupling_for_year_returns_all_features(syn):
    cfg, raw, grid = syn
    terrain = build_static_features(raw, grid, 1.0)
    yf = forest_for_year(raw, grid, 2019, 2023, 50)
    cf = coupling_for_year(raw, grid, terrain, np.full(grid.shape, 120.0), yf, 2023)
    assert set(cf) == {"f", "dF", "U", "CN", "Q"}
    land = ~np.isnan(cf["CN"])
    assert land.mean() > 0.9 and (cf["Q"][land] >= 0).all()
