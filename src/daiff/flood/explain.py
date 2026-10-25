"""Per-cell feature contributions (XGBoost TreeSHAP) for the FR-V3 location panel."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import xgboost as xgb


def explain_cell(model, row: np.ndarray, names: Sequence[str], top: int = 3) -> list[dict]:
    dm = xgb.DMatrix(np.asarray(row, dtype=float).reshape(1, -1), feature_names=list(names))
    contrib = model.get_booster().predict(dm, pred_contribs=True)[0][:-1]  # last = bias
    order = np.argsort(-np.abs(contrib))[:top]
    return [
        {"name": names[i], "contribution": float(contrib[i]), "value": float(row[i])} for i in order
    ]
