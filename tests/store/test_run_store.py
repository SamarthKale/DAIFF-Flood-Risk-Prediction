import pytest

from daiff.store.run_store import RunStore, current_run, publish


def test_appendix_c_file_names(tmp_path):
    s = RunStore(tmp_path, "abc123def456")
    d = tmp_path / "store" / "abc123def456"
    assert s.run_dir == d
    assert s.forest(2021) == d / "forest_2021.tif"
    assert s.loss(2019, 2021) == d / "loss_2019_2021.tif"
    assert s.coupling(2021) == d / "coupling_2021.tif"
    assert s.susceptibility(2021) == d / "susceptibility_2021.tif"
    assert s.riskclass(2021) == d / "riskclass_2021.tif"
    assert s.delta_s(2021) == d / "delta_s_2021.tif"
    assert s.subbasin_csv(2021) == d / "subbasin_2021.csv"
    assert s.run_metadata == d / "run_metadata.json"
    assert s.forest10m(2021) == d / "forest10m_2021.tif"
    assert s.loss10m(2019, 2021) == d / "loss10m_2019_2021.tif"
    assert s.regrowth(2019, 2021) == d / "regrowth_2019_2021.tif"
    assert s.cn(2021) == d / "cn_2021.tif"
    assert s.static_features == d / "static_features.tif"
    assert s.preview(2021) == d / "preview_2021.tif"
    assert s.subbasins_geojson == d / "subbasins.geojson"
    assert s.metrics_dir == d / "metrics"
    assert s.model_id_file == d / "model_id.txt"


def test_publish_and_current_run(tmp_path):
    assert current_run(tmp_path) is None
    with pytest.raises(FileNotFoundError):
        publish(tmp_path, "missing")
    RunStore(tmp_path, "abc").run_dir.mkdir(parents=True)
    publish(tmp_path, "abc")
    assert (tmp_path / "store" / "CURRENT").read_text().strip() == "abc"
    assert current_run(tmp_path) == "abc"
