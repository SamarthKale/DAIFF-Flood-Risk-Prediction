from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SYN_CONFIG = REPO / "configs" / "synthetic.yaml"


@pytest.fixture
def synthetic_cfg(tmp_path):
    from daiff.config import load_config

    return load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path)})
