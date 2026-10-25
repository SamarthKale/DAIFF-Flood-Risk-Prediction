import pytest
from pydantic import ValidationError

from daiff.config import config_hash, load_config, section_hash
from tests.conftest import REPO, SYN_CONFIG

YEARS = "years: [2019, 2020, 2021, 2022, 2023, 2024]"


def _variant(tmp_path, old, new):
    p = tmp_path / "configs" / "variant.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    text = SYN_CONFIG.read_text()
    assert old in text
    p.write_text(text.replace(old, new))
    return p


def test_load_synthetic_config():
    cfg = load_config(SYN_CONFIG, env={})
    assert cfg.project.name == "synthetic"
    assert cfg.grid.crs == "EPSG:32646" and cfg.grid.res == 30
    assert cfg.years.t0 == 2019 and cfg.years.years == [2019, 2020, 2021, 2022, 2023, 2024]
    assert cfg.data_root == (REPO / "data" / "synthetic").resolve()


def test_env_overrides_data_root_and_gee_project(tmp_path):
    cfg = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path), "DAIFF_GEE_PROJECT": "p1"})
    assert cfg.data_root == (tmp_path / "synthetic").resolve()
    assert cfg.gee.project == "p1"


def test_config_hash_ignores_machine_specific_settings(tmp_path):
    a = load_config(SYN_CONFIG, env={})
    b = load_config(SYN_CONFIG, env={"DAIFF_DATA_ROOT": str(tmp_path), "DAIFF_GEE_PROJECT": "x"})
    assert config_hash(a) == config_hash(b)
    assert len(config_hash(a)) == 64


def test_config_hash_and_section_hash_track_science_settings(tmp_path):
    base = load_config(SYN_CONFIG, env={})
    changed = load_config(_variant(tmp_path, "seed: 42", "seed: 7"), env={})
    assert config_hash(changed) != config_hash(base)
    assert section_hash(changed, "runtime") != section_hash(base, "runtime")
    assert section_hash(changed, "grid") == section_hash(base, "grid")


def test_unknown_key_is_rejected(tmp_path):
    with pytest.raises(ValidationError):
        load_config(
            _variant(tmp_path, "runtime: {seed: 42}", "runtime: {seed: 42, sede: 1}"), env={}
        )


@pytest.mark.parametrize(
    "years_line",
    [
        "years: [2020, 2019, 2021, 2022, 2023, 2024]",
        "years: [2019, 2019, 2021, 2022, 2023, 2024]",
        "years: [2020, 2021, 2022, 2023, 2024, 2025]",
        "years: [2014, 2019, 2021, 2022, 2023, 2024]",
    ],
)
def test_invalid_years_are_rejected(tmp_path, years_line):
    with pytest.raises(ValidationError):
        load_config(_variant(tmp_path, YEARS, years_line), env={})
