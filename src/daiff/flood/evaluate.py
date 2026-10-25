"""Flood-model skill: held-out AUC, HAND baseline, ablation, importance, block CV (SRS 7.4)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from daiff.config import DaiffConfig
from daiff.flood.dataset import COUPLING_FEATURES, FEATURES
from daiff.flood.model import train_model

HAND_THRESHOLD_M = 5.0


def _proba(model, df: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    return model.predict_proba(df[list(features)])[:, 1]


def evaluate(model, df_test: pd.DataFrame, features: Sequence[str], cfg: DaiffConfig) -> dict:
    y = df_test["label"].to_numpy()
    p = _proba(model, df_test, features)
    hand = df_test["hand"].to_numpy()
    high = cfg.flood.class_breaks[2]  # classes 4-5 start at the third break
    return {
        "auc": float(roc_auc_score(y, p)),
        "hand_baseline_auc_binary": float(roc_auc_score(y, (hand < HAND_THRESHOLD_M).astype(int))),
        "hand_baseline_auc_continuous": float(roc_auc_score(y, -hand)),
        "share_flooded_in_high": float((p[y == 1] >= high).mean()),
        "n_test": int(len(y)),
    }


def ablation(
    df_train: pd.DataFrame, df_test: pd.DataFrame, cfg: DaiffConfig, n_boot: int = 1000
) -> dict:
    """FR-R3: AUC with and without C1–C3, paired bootstrap 95% CI of the difference."""
    reduced = [f for f in FEATURES if f not in COUPLING_FEATURES]
    p_full = _proba(train_model(df_train, FEATURES, cfg), df_test, FEATURES)
    p_red = _proba(train_model(df_train, reduced, cfg), df_test, reduced)
    y = df_test["label"].to_numpy()
    auc_full, auc_red = roc_auc_score(y, p_full), roc_auc_score(y, p_red)
    rng = np.random.default_rng(cfg.runtime.seed)
    deltas = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        deltas.append(roc_auc_score(y[i], p_full[i]) - roc_auc_score(y[i], p_red[i]))
    delta = auc_full - auc_red
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    return {
        "auc_full": float(auc_full),
        "auc_no_coupling": float(auc_red),
        "delta": float(delta),
        "ci95": [float(min(lo, delta)), float(max(hi, delta))],
        "n_boot": len(deltas),
    }


def permutation_importance_table(
    model, df_test: pd.DataFrame, features: Sequence[str], seed: int
) -> pd.DataFrame:
    r = permutation_importance(
        model,
        df_test[list(features)],
        df_test["label"],
        scoring="roc_auc",
        n_repeats=5,
        random_state=seed,
    )
    table = pd.DataFrame(
        {
            "feature": list(features),
            "importance_mean": r.importances_mean,
            "importance_std": r.importances_std,
        }
    )
    return table.sort_values("importance_mean", ascending=False).reset_index(drop=True)


def spatial_block_cv(df: pd.DataFrame, cfg: DaiffConfig, k: int = 5) -> dict:
    aucs = []
    for tr, te in GroupKFold(n_splits=k).split(df, groups=df["block"]):
        model = train_model(df.iloc[tr], FEATURES, cfg)
        test = df.iloc[te]
        if test["label"].nunique() < 2:
            continue
        aucs.append(roc_auc_score(test["label"], _proba(model, test, FEATURES)))
    return {"auc_mean": float(np.mean(aucs)), "auc_std": float(np.std(aucs)), "n_folds": k}
