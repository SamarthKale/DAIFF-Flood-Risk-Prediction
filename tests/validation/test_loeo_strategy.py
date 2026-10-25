import json

from typer.testing import CliRunner

from daiff.cli import app
from daiff.config import load_config
from daiff.store.run_store import RunStore, current_run
from tests.conftest import REPO

runner = CliRunner()


def test_loeo_strategy_runs_and_validates_out_of_event(tmp_path):
    cfg_path = tmp_path / "configs" / "syn_loeo.yaml"
    cfg_path.parent.mkdir()
    text = (REPO / "configs" / "synthetic.yaml").read_text()
    cfg_path.write_text(
        text.replace("flood: {block_size_m: 2000}", "flood: {block_size_m: 2000, strategy: loeo}")
    )
    env = {"DAIFF_DATA_ROOT": str(tmp_path)}
    assert runner.invoke(app, ["synth", "-c", str(cfg_path)], env=env).exit_code == 0
    r = runner.invoke(app, ["run", "-c", str(cfg_path)], env=env)
    assert r.exit_code == 0, r.stdout
    r = runner.invoke(
        app,
        ["validate", "-c", str(cfg_path), "--what", "flood", "--n-boot", "50", "--no-log"],
        env=env,
    )
    assert r.exit_code == 0, r.stdout
    cfg = load_config(cfg_path, env=env)
    run = RunStore(cfg.data_root, current_run(cfg.data_root))
    m = json.loads((run.metrics_dir / "flood.json").read_text())
    assert m["strategy"] == "loeo" and len(m["per_event_auc"]) == 5
    assert m["auc"] > m["hand_baseline_auc_binary"] and "per_event" in m["ablation"]
    train_m = json.loads((run.metrics_dir / "flood_train.json").read_text())
    assert train_m["strategy"] == "loeo"
