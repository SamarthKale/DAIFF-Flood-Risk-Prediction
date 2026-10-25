"""Monotone XGBoost flood-susceptibility model (D-15, FR-R1, FR-C4)."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

import pandas as pd
import yaml
from xgboost import XGBClassifier

from daiff.config import DaiffConfig
from daiff.flood.dataset import MONOTONE


def train_model(df: pd.DataFrame, features: Sequence[str], cfg: DaiffConfig) -> XGBClassifier:
    fc = cfg.flood
    model = XGBClassifier(
        n_estimators=fc.n_estimators,
        max_depth=fc.max_depth,
        learning_rate=fc.learning_rate,
        monotone_constraints=tuple(MONOTONE.get(f, 0) for f in features),
        tree_method="hist",
        n_jobs=1,
        random_state=cfg.runtime.seed,
        eval_metric="auc",
    )
    model.fit(df[list(features)], df["label"])
    return model


def _model_bytes(model: XGBClassifier) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "model.json"
        model.save_model(p)
        return p.read_bytes()


def save_model(
    model: XGBClassifier,
    features: Sequence[str],
    metrics: Mapping[str, object],
    cfg: DaiffConfig,
    out_dir: Path,
) -> str:
    """Write model, feature list, metrics and config snapshot; return the 12-hex model id."""
    blob = _model_bytes(model)
    model_id = hashlib.sha256(blob).hexdigest()[:12]
    d = Path(out_dir) / model_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "model.json").write_bytes(blob)
    (d / "features.json").write_text(json.dumps(list(features)), encoding="utf-8")
    (d / "metrics.json").write_text(
        json.dumps(dict(metrics), indent=2, sort_keys=True, default=float), encoding="utf-8"
    )
    snapshot = cfg.model_dump(
        mode="json", exclude={"paths": True, "gee": {"project", "asset_root"}}
    )
    (d / "config.yaml").write_text(yaml.safe_dump(snapshot, sort_keys=True), encoding="utf-8")
    return model_id


def load_model(model_dir: Path) -> tuple[XGBClassifier, list[str]]:
    model = XGBClassifier()
    model.load_model(Path(model_dir) / "model.json")
    features = json.loads((Path(model_dir) / "features.json").read_text(encoding="utf-8"))
    return model, features
