from daiff.store.check import check_metadata
from tests.conftest import make_good_run


def test_nfr_4_check_passes_on_complete_run(tmp_path, small_grid):
    assert check_metadata(make_good_run(tmp_path, small_grid).run_dir) == []


def test_nfr_4_flags_missing_tag(tmp_path, small_grid):
    store = make_good_run(tmp_path, small_grid, drop_tag="DAIFF_CODE_COMMIT")
    problems = check_metadata(store.run_dir)
    assert len(problems) == 1
    assert problems[0].path.name == "forest_2020.tif"
    assert "DAIFF_CODE_COMMIT" in problems[0].problem


def test_nfr_4_flags_missing_run_metadata_key(tmp_path, small_grid):
    problems = check_metadata(make_good_run(tmp_path, small_grid, drop_key="timings").run_dir)
    assert [p.path.name for p in problems] == ["run_metadata.json"]
    assert "timings" in problems[0].problem


def test_nfr_4_flags_missing_run_metadata_file(tmp_path, small_grid):
    store = make_good_run(tmp_path, small_grid)
    store.run_metadata.unlink()
    assert [p.path.name for p in check_metadata(store.run_dir)] == ["run_metadata.json"]
