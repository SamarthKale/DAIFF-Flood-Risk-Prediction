import numpy as np
import pytest
import rasterio
from affine import Affine

from daiff.config import load_config
from daiff.grid import Grid, check_alignment
from tests.conftest import REPO

B = (300010.0, 2900020.0, 300095.0, 2900100.0)


def _write(path, grid, crs=None, transform=None, shape=None):
    h, w = shape or grid.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=w,
        height=h,
        count=1,
        dtype="float32",
        crs=crs or grid.crs,
        transform=transform or grid.transform,
    ) as dst:
        dst.write(np.zeros((h, w), "float32"), 1)
    return path


def test_from_bounds_snaps_outward_to_resolution():
    g = Grid.from_bounds("EPSG:32646", B, res=30)
    assert g.transform == Affine(30, 0, 300000, 0, -30, 2900100)
    assert (g.width, g.height) == (4, 3)


def test_from_bounds_applies_buffer_before_snapping():
    g = Grid.from_bounds("EPSG:32646", B, res=30, buffer_m=60)
    assert g.transform.c == 299940 and g.width == 8


def test_nested_grid_shares_origin_and_is_three_times_finer():
    n = Grid.from_bounds("EPSG:32646", B, res=30).nested(3)
    assert n.transform == Affine(10, 0, 300000, 0, -10, 2900100)
    assert (n.width, n.height) == (12, 9)


def test_cell_area_and_xy_to_rowcol():
    g = Grid.from_bounds("EPSG:32646", B, res=30)
    assert g.cell_area_m2 == 900.0
    assert g.xy_to_rowcol(300001.0, 2900099.0) == (0, 0)
    assert g.xy_to_rowcol(300119.0, 2900011.0) == (2, 3)
    with pytest.raises(ValueError):
        g.xy_to_rowcol(299999.0, 2900050.0)


def test_dict_roundtrip():
    g = Grid.from_bounds("EPSG:32646", B, res=30)
    assert Grid.from_dict({**g.to_dict(), "nested_factor": 3}) == g


def test_from_config_uses_bounds_and_requires_them(synthetic_cfg, tmp_path):
    assert Grid.from_config(synthetic_cfg).shape == (200, 200)
    cfg_path = tmp_path / "configs" / "nobounds.yaml"
    cfg_path.parent.mkdir()
    cfg_path.write_text(
        "project: {name: nb, basin: x}\nyears: {t0: 2019, years: [2019]}\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="grid.bounds"):
        Grid.from_config(load_config(cfg_path, env={}))
    assert Grid.from_config(load_config(REPO / "configs" / "kopili.yaml", env={})).shape == (
        5671,
        7155,
    )


def test_fr_d5_aligned_layers_pass(tmp_path, small_grid):
    report = check_alignment([_write(tmp_path / "a.tif", small_grid)], small_grid)
    assert report.ok and report.problems == []


def test_fr_d5_detects_crs_mismatch(tmp_path, small_grid):
    report = check_alignment([_write(tmp_path / "a.tif", small_grid, crs="EPSG:32645")], small_grid)
    assert not report.ok and report.problems[0].field == "crs"


def test_fr_d5_detects_shape_mismatch(tmp_path, small_grid):
    report = check_alignment([_write(tmp_path / "a.tif", small_grid, shape=(3, 5))], small_grid)
    assert [p.field for p in report.problems] == ["shape"]


def test_fr_d5_detects_half_cell_shift(tmp_path, small_grid):
    shifted = small_grid.transform @ Affine.translation(0.5, 0)
    report = check_alignment(
        [_write(tmp_path / "a.tif", small_grid, transform=shifted)], small_grid
    )
    assert [p.field for p in report.problems] == ["transform"]


def test_fr_d5_tolerates_float_noise(tmp_path, small_grid):
    t = small_grid.transform
    noisy = Affine(t.a, t.b, t.c + 1e-7, t.d, t.e, t.f)
    assert check_alignment([_write(tmp_path / "a.tif", small_grid, transform=noisy)], small_grid).ok


def test_fr_d5_reports_missing_file(tmp_path, small_grid):
    report = check_alignment([tmp_path / "nope.tif"], small_grid)
    assert [p.field for p in report.problems] == ["missing"]
