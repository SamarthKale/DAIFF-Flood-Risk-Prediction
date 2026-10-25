"""Earth Engine helpers that can be verified without an Earth Engine login."""

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from daiff.cli import app
from daiff.config import load_config
from daiff.gee.auth import GeeAuthError, init_ee
from daiff.gee.export import asset_id, download_asset, tile_windows
from daiff.gee.forest_rf import auto_label
from daiff.gee.refdata import HSG_REMAP, remap_hsg
from daiff.gee.s1_flood import otsu_threshold
from daiff.gee.s2 import SCL_MASK_CLASSES, season_window
from daiff.grid import Grid
from daiff.ingest.rainfall import cell_index_map, find_gaps
from daiff.ingest.rivers import overpass_query, stream_agreement
from daiff.store.cog import read_raster, read_tags
from tests.conftest import REPO, SYN_CONFIG

KOP = REPO / "configs" / "kopili.yaml"


class FakeEE:
    def __init__(self, fail=None):
        self.fail, self.inits = fail, []

    def Initialize(self, project):  # noqa: N802 - mirrors the ee API
        if self.fail:
            raise self.fail
        self.inits.append(project)


def test_init_ee_requires_project():
    with pytest.raises(GeeAuthError, match="DAIFF_GEE_PROJECT"):
        init_ee(load_config(KOP, env={}), ee_module=FakeEE())


def test_init_ee_wraps_login_failure_with_guidance():
    cfg = load_config(KOP, env={"DAIFF_GEE_PROJECT": "daiff-x"})
    with pytest.raises(GeeAuthError, match="docs/setup/gee.md"):
        init_ee(cfg, ee_module=FakeEE(fail=Exception("not registered")))
    fake = FakeEE()
    init_ee(cfg, ee_module=fake)
    assert fake.inits == ["daiff-x"]


def test_gee_check_cli_exits_3_without_project(tmp_path):
    r = CliRunner().invoke(
        app,
        ["gee", "check", "-c", str(KOP)],
        env={"DAIFF_DATA_ROOT": str(tmp_path), "DAIFF_GEE_PROJECT": ""},
    )
    assert r.exit_code == 3 and "docs/setup/gee.md" in r.stdout


def test_asset_id_defaults_to_project_assets():
    cfg = load_config(KOP, env={"DAIFF_GEE_PROJECT": "daiff-x"})
    assert asset_id(cfg, "forest10m_2020") == "projects/daiff-x/assets/daiff/kopili/forest10m_2020"


def test_tile_windows_cover_grid_exactly():
    g = Grid.from_bounds("EPSG:32646", (300000, 2900010, 301500, 2900910), res=30)  # 50 x 30
    wins = tile_windows(g, tile=16)
    cover = np.zeros(g.shape, int)
    for w in wins:
        cover[w.row_off : w.row_off + w.height, w.col_off : w.col_off + w.width] += 1
    assert (cover == 1).all()


def test_download_asset_mosaics_edge_tiles_and_is_idempotent(tmp_path):
    g = Grid.from_bounds("EPSG:32646", (300000, 2900010, 301500, 2900910), res=30)
    truth = np.arange(g.width * g.height, dtype="float32").reshape(g.shape)
    calls = []

    def fetch(asset, window, grid):
        calls.append(window)
        r, c = window.row_off, window.col_off
        return truth[r : r + window.height, c : c + window.width][np.newaxis]

    out = tmp_path / "x.tif"
    download_asset("projects/p/assets/x", g, out, fetch=fetch, tile=16, nodata=np.nan)
    assert np.array_equal(read_raster(out, g), truth)
    assert read_tags(out)["DAIFF_ASSET"] == "projects/p/assets/x"
    n = len(calls)
    download_asset("projects/p/assets/x", g, out, fetch=fetch, tile=16, nodata=np.nan)
    assert len(calls) == n  # second call skipped


def test_fill_gaps_from_previous_year():
    from daiff.gee.ingest import fill_gaps_from_previous

    prev = np.array([[1, 0, 255]], dtype="uint8")
    cur = np.array([[255, 1, 255]], dtype="uint8")
    out, share = fill_gaps_from_previous(cur, prev)
    assert out.tolist() == [[1, 1, 255]] and share == 0.0
    out0, share0 = fill_gaps_from_previous(cur, None)
    assert out0.tolist() == cur.tolist() and share0 == pytest.approx(2 / 3)


def test_event_windows():
    from daiff.gee.ingest import event_windows

    pre, ev = event_windows("2022-06-12", "2022-06-28")
    assert pre == ("2022-04-13", "2022-05-23") and ev == ("2022-06-12", "2022-06-29")


def test_season_window_and_scl_classes():
    assert season_window(2020) == ("2019-11-01", "2020-04-01")
    assert SCL_MASK_CLASSES == (0, 1, 3, 8, 9, 10)


def test_auto_label_rules():
    tc = np.array([80, 80, 5, 5, 50, 20])
    lost = np.array([False, True, False, False, False, False])
    dw = np.array([0.8, 0.1, 0.1, 0.5, 0.4, 0.1])
    assert auto_label(tc, lost, dw).tolist() == [1, 0, 0, 255, 255, 255]


def test_otsu_threshold_splits_bimodal_histogram():
    rng = np.random.default_rng(0)
    x = np.r_[rng.normal(-6, 1, 5000), rng.normal(1, 1, 5000)]
    counts, edges = np.histogram(x, bins=200)
    assert -4 < otsu_threshold(counts, edges) < -1


def test_hsg_from_texture_rules():
    from daiff.gee.refdata import hsg_from_texture

    sand = np.array([95, 70, 30, 20, 40, 60])
    clay = np.array([5, 15, 30, 50, 10, 25])
    # A sandy; B loamy; C clay loam; D clay; B silt loam; C sandy clay loam
    assert hsg_from_texture(sand, clay).tolist() == [1, 2, 3, 4, 2, 3]


def test_hsg_remap_treats_dual_groups_as_d():
    assert HSG_REMAP == {1: 1, 2: 2, 3: 3, 4: 4, 11: 4, 12: 4, 13: 4, 14: 4}
    assert remap_hsg(np.array([1, 12, 4, 0])).tolist() == [1, 4, 4, 255]


def test_find_gaps_flags_runs_longer_than_three_days():
    dates = pd.date_range("2020-01-01", "2020-01-20")
    keep = [d for i, d in enumerate(dates) if not 5 <= i <= 9 and i != 15]
    df = pd.DataFrame({"date": keep, "subbasin_id": 1, "precip_mm": 0.0})
    gaps = find_gaps(df, max_gap_days=3)
    assert gaps.to_dict(orient="records") == [
        {"subbasin_id": 1, "start": "2020-01-06", "end": "2020-01-10", "days": 5}
    ]


def test_cell_index_map_assigns_nearest_coarse_cell():
    g = Grid.from_bounds("EPSG:4326", (90.0, 26.0, 91.0, 27.0), res=0.25)  # 4 x 4 fine cells
    lat = np.array([26.75, 26.25])
    lon = np.array([90.25, 90.75])
    iy, ix = cell_index_map(lat, lon, g)
    assert iy[0, 0] == 0 and ix[0, 0] == 0 and iy[-1, -1] == 1 and ix[-1, -1] == 1


def test_overpass_query_and_stream_agreement():
    q = overpass_query((26.0, 92.0, 26.5, 92.5))
    assert 'waterway"~"river|canal' in q and "(26.0,92.0,26.5,92.5)" in q
    derived = np.zeros((10, 10), bool)
    derived[:, 4] = True
    osm = np.zeros((10, 10), bool)
    osm[:, 5] = True  # 30 m away -> within 60 m
    assert stream_agreement(derived, osm, res=30.0, tol_m=60.0) == 1.0
    osm2 = np.zeros((10, 10), bool)
    osm2[:, 9] = True  # 150 m away
    assert stream_agreement(derived, osm2, res=30.0, tol_m=60.0) == 0.0


def test_synthetic_config_unaffected(tmp_path):
    assert load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)}).gee.project is None
