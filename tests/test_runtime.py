import builtins

import pytest

from daiff.config import RuntimeConfig
from daiff.runtime import make_client


def test_make_client_local_runs_task():
    with make_client(RuntimeConfig(n_workers=1, threads_per_worker=1)) as client:
        assert client.submit(sum, [1, 2]).result() == 3


def test_slurm_without_extra_gives_install_hint(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("dask_jobqueue"):
            raise ImportError("no dask_jobqueue")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match="--extra hpc"):
        make_client(RuntimeConfig(cluster="slurm"))


def test_synthetic_config_exposes_science_sections(synthetic_cfg):
    assert synthetic_cfg.flood.class_breaks == [0.2, 0.4, 0.6, 0.8]
    assert synthetic_cfg.forest.mmu_ha == 0.5
    assert synthetic_cfg.coupling.return_period_years == 10
    assert synthetic_cfg.terrain.stream_threshold_km2 == 1.0
