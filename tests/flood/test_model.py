import json

from daiff.flood.dataset import FEATURES
from daiff.flood.evaluate import ablation, evaluate, permutation_importance_table, spatial_block_cv
from daiff.flood.model import load_model, save_model, train_model


def _split(df):
    return df[df["split"] == "train"], df[df["split"] == "test"]


def test_fr_r1_train_from_config_saves_model_features_metrics(flood_ctx, tmp_path):
    train, test = _split(flood_ctx.dataset)
    model = train_model(train, FEATURES, flood_ctx.cfg)
    metrics = evaluate(model, test, FEATURES, flood_ctx.cfg)
    model_id = save_model(model, FEATURES, metrics, flood_ctx.cfg, tmp_path / "models")
    d = tmp_path / "models" / model_id
    assert (d / "model.json").exists() and (d / "config.yaml").exists()
    assert json.loads((d / "features.json").read_text()) == list(FEATURES)
    assert json.loads((d / "metrics.json").read_text())["auc"] == metrics["auc"]
    loaded, feats = load_model(d)
    assert feats == list(FEATURES)
    assert (loaded.predict_proba(test[feats])[:, 1] == model.predict_proba(test[feats])[:, 1]).all()


def test_model_beats_hand_baseline_on_synthetic(flood_ctx):
    train, test = _split(flood_ctx.dataset)
    m = evaluate(train_model(train, FEATURES, flood_ctx.cfg), test, FEATURES, flood_ctx.cfg)
    assert m["auc"] > m["hand_baseline_auc_binary"]
    assert 0 <= m["share_flooded_in_high"] <= 1


def test_fr_r3_ablation_reports_ci(flood_ctx):
    train, test = _split(flood_ctx.dataset)
    a = ablation(train, test, flood_ctx.cfg, n_boot=200)
    assert {"auc_full", "auc_no_coupling", "delta", "ci95"} <= a.keys()
    lo, hi = a["ci95"]
    assert lo <= a["delta"] <= hi


def test_permutation_importance_and_block_cv(flood_ctx):
    train, test = _split(flood_ctx.dataset)
    model = train_model(train, FEATURES, flood_ctx.cfg)
    table = permutation_importance_table(model, test, FEATURES, seed=0)
    assert list(table.columns) == ["feature", "importance_mean", "importance_std"]
    assert set(table["feature"]) == set(FEATURES)
    cv = spatial_block_cv(flood_ctx.dataset, flood_ctx.cfg, k=3)
    assert cv["n_folds"] == 3 and 0.5 < cv["auc_mean"] <= 1.0


def test_training_is_deterministic(flood_ctx, tmp_path):
    train, _ = _split(flood_ctx.dataset)
    ids = [
        save_model(
            train_model(train, FEATURES, flood_ctx.cfg), FEATURES, {}, flood_ctx.cfg, tmp_path
        )
        for _ in range(2)
    ]
    assert ids[0] == ids[1]
