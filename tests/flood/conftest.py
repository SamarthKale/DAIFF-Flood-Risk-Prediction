import pytest

from daiff.config import load_config
from daiff.flood.dataset import FloodContext, build_dataset_from_raw
from daiff.synthetic import make_basin
from tests.conftest import SYN_CONFIG


@pytest.fixture(scope="session")
def flood_ctx(tmp_path_factory) -> FloodContext:
    root = tmp_path_factory.mktemp("flood")
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(root)})
    raw = make_basin(cfg)
    return build_dataset_from_raw(cfg, raw)


@pytest.fixture(scope="session")
def trained(flood_ctx):
    from daiff.flood.dataset import FEATURES
    from daiff.flood.model import train_model

    train = flood_ctx.dataset[flood_ctx.dataset["split"] == "train"]
    return train_model(train, FEATURES, flood_ctx.cfg)
