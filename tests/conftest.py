from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SYN_CONFIG = REPO / "configs" / "synthetic.yaml"


def make_good_run(data_root, grid, drop_tag=None, drop_key=None):
    """A run with one fully tagged output and complete run metadata (NFR-4 fixtures)."""
    import numpy as np

    from daiff.store.cog import write_cog
    from daiff.store.provenance import build_tags
    from daiff.store.run_store import RUN_METADATA_KEYS, RunStore, write_run_metadata

    store = RunStore(data_root, "abc123def456")
    tags = build_tags(
        run_id="abc123def456",
        config_hash="c" * 64,
        code_commit="deadbeef",
        model_id="n/a",
        inputs=[],
        data_root=data_root,
        data_versions={"synthetic": "seed=42"},
        year=2020,
        t0=2019,
    )
    tags.pop(drop_tag, None)
    write_cog(store.forest(2020), np.zeros(grid.shape, "float32"), grid, nodata=np.nan, tags=tags)
    meta = {k: "x" for k in RUN_METADATA_KEYS}
    meta.pop(drop_key, None)
    write_run_metadata(store, meta)
    return store


@pytest.fixture
def small_grid():
    from daiff.grid import Grid

    return Grid.from_bounds("EPSG:32646", (300000, 2900010, 300120, 2900100), res=30)


@pytest.fixture
def synthetic_cfg(tmp_path):
    from daiff.config import load_config

    return load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)})
