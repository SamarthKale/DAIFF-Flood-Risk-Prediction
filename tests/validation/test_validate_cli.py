import json

import pandas as pd
import pytest
from typer.testing import CliRunner

from daiff.cli import app
from daiff.config import load_config
from daiff.store.cog import read_raster
from daiff.store.raw_layout import RawLayout
from daiff.store.run_store import RunStore, current_run
from tests.conftest import SYN_CONFIG

runner = CliRunner()


@pytest.fixture(scope="module")
def published(tmp_path_factory):
    root = tmp_path_factory.mktemp("val")
    env = {"DAIFF_DATA_ROOT": str(root)}
    assert runner.invoke(app, ["synth", "-c", str(SYN_CONFIG)], env=env).exit_code == 0
    assert runner.invoke(app, ["run", "-c", str(SYN_CONFIG)], env=env).exit_code == 0
    return env, load_config(SYN_CONFIG, env=env), root


def test_validate_flood_writes_metrics(published, tmp_path):
    env, cfg, _ = published
    r = runner.invoke(
        app,
        ["validate", "-c", str(SYN_CONFIG), "--what", "flood", "--n-boot", "50", "--no-log"],
        env=env,
    )
    assert r.exit_code == 0, r.stdout
    m = json.loads(
        (RunStore(cfg.data_root, current_run(cfg.data_root)).metrics_dir / "flood.json").read_text()
    )
    assert {
        "auc",
        "hand_baseline_auc_binary",
        "ablation",
        "block_cv",
        "high_class_area_share",
        "permutation_importance",
    } <= m.keys()


def test_validate_forest_without_labels_explains_human_task(published, tmp_path):
    env, _, _ = published
    r = runner.invoke(
        app,
        [
            "validate",
            "-c",
            str(SYN_CONFIG),
            "--what",
            "forest",
            "--reference-dir",
            str(tmp_path),
            "--no-log",
        ],
        env=env,
    )
    assert r.exit_code == 2 and "label" in r.stdout


def test_sample_points_then_validate_forest_with_true_labels(published, tmp_path):
    env, cfg, _ = published
    r = runner.invoke(
        app, ["sample-points", "-c", str(SYN_CONFIG), "--reference-dir", str(tmp_path)], env=env
    )
    assert r.exit_code == 0, r.stdout
    pts = pd.read_csv(tmp_path / "forest_sample_points_synthetic.csv")
    assert len(pts) >= 600 and (pts["stratum"] == 3).sum() >= 150
    raw = RawLayout(cfg.data_root)
    fine = raw.read_grid().nested(3)
    t0, last = cfg.years.t0, cfg.years.years[-1]
    a, b = read_raster(raw.forest10m(t0), fine), read_raster(raw.forest10m(last), fine)
    lab = lambda v: "forest" if v == 1 else "non_forest"  # noqa: E731
    rows = []
    for p in pts.itertuples():
        for who in ("A", "B"):
            rows.append(
                {
                    "point_id": p.point_id,
                    "interpreter": who,
                    "label_t0": lab(a[p.row, p.col]),
                    "label_t": lab(b[p.row, p.col]),
                    "note": "",
                }
            )
    pd.DataFrame(rows).to_csv(tmp_path / "forest_labels_synthetic.csv", index=False)
    r = runner.invoke(
        app,
        [
            "validate",
            "-c",
            str(SYN_CONFIG),
            "--what",
            "forest",
            "--reference-dir",
            str(tmp_path),
            "--no-log",
        ],
        env=env,
    )
    assert r.exit_code == 0, r.stdout
    m = json.loads(
        (
            RunStore(cfg.data_root, current_run(cfg.data_root)).metrics_dir / "forest.json"
        ).read_text()
    )
    assert m["fr_f1"]["overall_accuracy"] > 0.95 and m["kappa_t"] == 1.0
    assert m["fr_f2"]["loss_f1"] > 0.9
