import numpy as np

from daiff.config import load_config
from daiff.grid import Grid
from daiff.synthetic import make_basin
from daiff.zones import rasterize_subbasins, zonal_mean, zonal_sum
from tests.conftest import SYN_CONFIG


def test_rasterize_subbasins_synthetic_quadrants(tmp_path):
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)})
    raw = make_basin(cfg)
    zones, names = rasterize_subbasins(raw.subbasins, Grid.from_config(cfg))
    assert sorted(names["subbasin_id"]) == [1000, 1001, 1002, 1003]
    counts = {int(k): int(v) for k, v in zip(*np.unique(zones, return_counts=True), strict=True)}
    assert counts == {1000: 10000, 1001: 10000, 1002: 10000, 1003: 10000}


def test_zonal_mean_keeps_empty_zone_as_nan():
    zones = np.array([[1, 1, 2]], dtype="int32")
    vals = np.array([[1.0, 3.0, np.nan]])
    m = zonal_mean(vals, zones, ids=[1, 2, 3])
    assert m.loc[1] == 2.0 and np.isnan(m.loc[2]) and np.isnan(m.loc[3])
    s = zonal_sum(vals, zones, ids=[1, 2, 3])
    assert s.loc[1] == 4.0 and s.loc[2] == 0.0 and s.loc[3] == 0.0
