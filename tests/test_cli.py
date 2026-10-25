import numpy as np
from affine import Affine
from typer.testing import CliRunner

from daiff import __version__
from daiff.cli import app
from daiff.store.cog import write_cog
from daiff.store.run_store import publish
from tests.conftest import SYN_CONFIG, make_good_run

runner = CliRunner()


def _env(tmp_path):
    return {"DAIFF_DATA_ROOT": str(tmp_path)}


def test_cli_version_prints_package_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"daiff {__version__}"


def test_fr_d5_synth_then_check_grid_passes(tmp_path):
    assert runner.invoke(app, ["synth", "-c", str(SYN_CONFIG)], env=_env(tmp_path)).exit_code == 0
    r = runner.invoke(app, ["check-grid", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    assert r.exit_code == 0 and "FR-D5 PASS: 15 layers aligned" in r.stdout


def test_fr_d5_check_grid_fails_on_shifted_layer(tmp_path):
    runner.invoke(app, ["synth", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    from daiff.config import load_config
    from daiff.grid import Grid
    from daiff.store.raw_layout import RawLayout

    cfg = load_config(SYN_CONFIG, env=_env(tmp_path))
    g = Grid.from_config(cfg)
    shifted = Grid(g.crs, g.transform @ Affine.translation(0.5, 0), g.width, g.height)
    write_cog(
        RawLayout(cfg.data_root).dem, np.zeros(g.shape, "float32"), shifted, nodata=np.nan, tags={}
    )
    r = runner.invoke(app, ["check-grid", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    assert r.exit_code == 1 and "FR-D5 FAIL" in r.stdout and "dem.tif" in r.stdout


def test_check_grid_without_raw_layers_fails_clearly(tmp_path):
    r = runner.invoke(app, ["check-grid", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    assert r.exit_code == 1 and "no raw layers found" in r.stdout


def test_check_metadata_without_published_run_exits_2(tmp_path):
    r = runner.invoke(app, ["check-metadata", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    assert r.exit_code == 2 and "no published run" in r.stdout


def test_run_then_check_metadata_on_synthetic(tmp_path):
    env = _env(tmp_path)
    runner.invoke(app, ["synth", "-c", str(SYN_CONFIG)], env=env)
    r = runner.invoke(app, ["run", "-c", str(SYN_CONFIG)], env=env)
    assert r.exit_code == 0, r.stdout
    assert "published run" in r.stdout
    r = runner.invoke(app, ["check-metadata", "-c", str(SYN_CONFIG)], env=env)
    assert r.exit_code == 0 and "NFR-4 PASS" in r.stdout
    r = runner.invoke(app, ["watch", "-c", str(SYN_CONFIG), "--once"], env=env)
    assert r.exit_code == 0 and "no new forest maps" in r.stdout


def test_nfr_4_check_metadata_passes_on_published_run(tmp_path, small_grid):
    make_good_run(tmp_path / "synthetic", small_grid)
    publish(tmp_path / "synthetic", "abc123def456")
    r = runner.invoke(app, ["check-metadata", "-c", str(SYN_CONFIG)], env=_env(tmp_path))
    assert r.exit_code == 0 and "NFR-4 PASS" in r.stdout
