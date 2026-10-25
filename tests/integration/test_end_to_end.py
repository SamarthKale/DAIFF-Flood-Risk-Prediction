import hashlib
import json
import time

import pandas as pd
import pytest

from daiff.config import load_config
from daiff.flood.tables import TABLE_COLUMNS
from daiff.pipeline.stages import run_pipeline
from daiff.pipeline.watch import watch
from daiff.store.check import check_metadata
from daiff.store.run_store import RunStore, current_run
from daiff.synthetic import make_basin
from tests.conftest import SYN_CONFIG


def _hashes(run_dir):
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(run_dir.glob("*.tif"))
    }


@pytest.fixture(scope="module")
def e2e(tmp_path_factory):
    root = tmp_path_factory.mktemp("e2e")
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(root)})
    make_basin(cfg)
    start = time.perf_counter()
    run_id = run_pipeline(cfg)
    return cfg, run_id, time.perf_counter() - start


def test_end_to_end_synthetic_produces_appendix_c_outputs(e2e):
    cfg, run_id, seconds = e2e
    assert current_run(cfg.data_root) == run_id
    s = RunStore(cfg.data_root, run_id)
    t0 = cfg.years.t0
    for y in cfg.years.years:
        for p in (
            s.forest(y),
            s.loss(t0, y),
            s.coupling(y),
            s.susceptibility(y),
            s.riskclass(y),
            s.delta_s(y),
            s.subbasin_csv(y),
        ):
            assert p.exists(), p
        assert list(pd.read_csv(s.subbasin_csv(y)).columns) == TABLE_COLUMNS
    meta = json.loads(s.run_metadata.read_text())
    assert meta["run_id"] == run_id and set(meta["timings"]) >= {"terrain", "predict"}
    assert check_metadata(s.run_dir) == []
    assert seconds < 300


def test_nfr_3_rerun_is_byte_identical(e2e, tmp_path):
    cfg, run_id, _ = e2e
    cfg2 = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)})
    make_basin(cfg2)
    run_id2 = run_pipeline(cfg2)
    assert run_id2 == run_id
    a = _hashes(RunStore(cfg.data_root, run_id).run_dir)
    b = _hashes(RunStore(cfg2.data_root, run_id2).run_dir)
    assert a == b and len(a) > 20


def test_unusable_event_without_mask_does_not_block_training(tmp_path):
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)})
    raw = make_basin(cfg)
    ev = pd.read_csv(raw.flood_events_csv)
    extra = ev.iloc[[0]].assign(event_id="no_mask_2020", usable=False)
    pd.concat([ev, extra]).to_csv(raw.flood_events_csv, index=False)
    assert run_pipeline(cfg)


def test_fr_c2_watch_processes_new_forest_map(tmp_path):
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)})
    make_basin(cfg)
    first = run_pipeline(cfg, years=[2019, 2020, 2021, 2022, 2023])
    assert watch(cfg, once=True) == [2024]
    second = current_run(cfg.data_root)
    assert second != first
    s = RunStore(cfg.data_root, second)
    assert s.susceptibility(2024).exists() and s.delta_s(2024).exists()
    assert s.model_id_file.read_text() == RunStore(cfg.data_root, first).model_id_file.read_text()
    assert watch(cfg, once=True) == []
