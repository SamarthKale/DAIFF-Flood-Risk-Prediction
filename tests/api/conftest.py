import json

import pytest
from fastapi.testclient import TestClient

from daiff.api.app import create_app
from daiff.config import load_config
from daiff.pipeline.stages import run_pipeline
from daiff.synthetic import make_basin
from tests.conftest import SYN_CONFIG


@pytest.fixture(scope="session")
def api_env(tmp_path_factory):
    root = tmp_path_factory.mktemp("api")
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(root)})
    raw = make_basin(cfg)
    # give one sub-basin a non-ASCII name to check UTF-8 round-trips
    fc = json.loads(raw.subbasins.read_text(encoding="utf-8"))
    fc["features"][0]["properties"]["name"] = "Āmchang Kopili-ūpper"
    raw.subbasins.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    run_id = run_pipeline(cfg)
    ref = tmp_path_factory.mktemp("reference")
    return cfg, run_id, ref


@pytest.fixture(scope="session")
def client(api_env):
    cfg, _, ref = api_env
    return TestClient(create_app(cfg, reference_dir=ref))
