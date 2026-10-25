"""Accuracy with stratified estimators (Olofsson et al. 2014) and Cohen's kappa (SRS 7.3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np


def accuracy_report(
    map_cls: Sequence[int], ref_cls: Sequence[int], weights: Mapping[int, float]
) -> dict:
    """Map classes are the sampling strata with area weights W_i. Returns OA, per-class user's /
    producer's accuracy, F1, and area proportion of each reference class with a 95% CI."""
    m, r = np.asarray(map_cls), np.asarray(ref_cls)
    classes = sorted(set(weights) | set(np.unique(r).tolist()))
    k = len(classes)
    pos = {c: i for i, c in enumerate(classes)}
    n = np.zeros((k, k))
    for a, b in zip(m, r, strict=True):
        n[pos[a], pos[b]] += 1
    n_i = n.sum(axis=1)
    W = np.array([weights.get(c, 0.0) for c in classes])
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(n_i[:, None] > 0, n / n_i[:, None], 0.0)
    p = W[:, None] * frac
    row, col = p.sum(axis=1), p.sum(axis=0)
    out = {"overall_accuracy": float(np.trace(p)), "n": int(len(m)), "classes": {}}
    for c, j in pos.items():
        ua = p[j, j] / row[j] if row[j] > 0 else float("nan")
        pa = p[j, j] / col[j] if col[j] > 0 else float("nan")
        f1 = 2 * ua * pa / (ua + pa) if (ua + pa) > 0 else float("nan")
        var = 0.0
        for i in range(k):
            if n_i[i] > 1:
                var += W[i] ** 2 * frac[i, j] * (1 - frac[i, j]) / (n_i[i] - 1)
        out["classes"][c] = {
            "users_accuracy": float(ua),
            "producers_accuracy": float(pa),
            "f1": float(f1),
            "area_proportion": float(col[j]),
            "area_proportion_ci95": float(1.96 * np.sqrt(var)),
        }
    return out


def cohens_kappa(a: Sequence, b: Sequence) -> float:
    a, b = np.asarray(a), np.asarray(b)
    labels = np.unique(np.concatenate([a, b]))
    po = float((a == b).mean())
    pe = float(sum((a == lab).mean() * (b == lab).mean() for lab in labels))
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)
