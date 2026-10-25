from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SYN_CONFIG = REPO / "configs" / "synthetic.yaml"


@pytest.fixture
def small_grid():
    from daiff.grid import Grid

    return Grid.from_bounds("EPSG:32646", (300000, 2900010, 300120, 2900100), res=30)


@pytest.fixture
def synthetic_cfg(tmp_path):
    from daiff.config import load_config

    return load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)})
