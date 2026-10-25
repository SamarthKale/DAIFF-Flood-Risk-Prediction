"""`daiff sample-points` and `daiff validate` (SRS 7.3, 7.4; test log per SRS 8.3)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from daiff.config import DaiffConfig
from daiff.flood.dataset import FEATURES, build_dataset
from daiff.flood.evaluate import ablation, evaluate, permutation_importance_table, spatial_block_cv
from daiff.flood.model import load_model
from daiff.pipeline.stages import REPO_ROOT, features_for, plan_for_run
from daiff.store.cog import read_raster
from daiff.store.run_store import current_run
from daiff.validation.forest_accuracy import accuracy_report, cohens_kappa
from daiff.validation.report import write_test_log_entry
from daiff.validation.sampling import strata_map, stratified_sample, stratum_weights

DEFAULT_REFERENCE_DIR = REPO_ROOT / "reference"
TEST_LOG = REPO_ROOT / "docs" / "test_log.md"


class MissingLabels(RuntimeError):
    pass


def _plan(cfg: DaiffConfig):
    run_id = current_run(cfg.data_root)
    if run_id is None:
        raise FileNotFoundError("no published run — run the pipeline first")
    return plan_for_run(cfg, run_id)


def _strata(p) -> np.ndarray:
    t0, last = p.t0, max(p.years)
    return strata_map(
        read_raster(p.store.forest10m(t0), p.fine),
        read_raster(p.store.forest10m(last), p.fine),
        read_raster(p.store.loss10m(t0, last), p.fine),
    )


def sample_points(cfg: DaiffConfig, reference_dir: Path = DEFAULT_REFERENCE_DIR) -> Path:
    p = _plan(cfg)
    df = stratified_sample(_strata(p), p.fine, seed=cfg.runtime.seed)
    out = Path(reference_dir) / f"forest_sample_points_{cfg.project.name}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, lineterminator="\n")
    return out


def _pair(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    return a.merge(b, left_index=True, right_index=True, how="inner", suffixes=("_a", "_b"))


def adjudicated_labels(labels: pd.DataFrame) -> pd.DataFrame:
    """One label pair per point: ADJ if present, else A where A and B agree."""
    adj = labels[labels["interpreter"] == "ADJ"].set_index("point_id")
    a = labels[labels["interpreter"] == "A"].set_index("point_id")
    b = labels[labels["interpreter"] == "B"].set_index("point_id")
    agree = _pair(a, b)
    agree = agree[(agree.label_t0_a == agree.label_t0_b) & (agree.label_t_a == agree.label_t_b)]
    out = agree[["label_t0_a", "label_t_a"]].rename(
        columns={"label_t0_a": "label_t0", "label_t_a": "label_t"}
    )
    out = pd.concat([out[~out.index.isin(adj.index)], adj[["label_t0", "label_t"]]])
    return out[~out["label_t0"].eq("unsure") & ~out["label_t"].eq("unsure")]


def _ref_class(t0: str, t: str) -> int:
    if t0 == "forest" and t == "non_forest":
        return 3
    return 1 if t == "forest" else 2


def validate_forest(cfg: DaiffConfig, reference_dir: Path = DEFAULT_REFERENCE_DIR) -> dict:
    ref = Path(reference_dir)
    pts_path = ref / f"forest_sample_points_{cfg.project.name}.csv"
    lab_path = ref / f"forest_labels_{cfg.project.name}.csv"
    if not pts_path.exists() or not lab_path.exists():
        raise MissingLabels(
            f"reference labels missing ({lab_path.name}): run `daiff sample-points`, then two "
            "interpreters label the points on the dashboard's Labelling page (human task)"
        )
    p = _plan(cfg)
    pts = pd.read_csv(pts_path).set_index("point_id")
    labels = pd.read_csv(lab_path)
    adj = adjudicated_labels(labels).join(pts, how="inner")
    weights = stratum_weights(_strata(p))
    map_cls = adj["stratum"].to_numpy()
    ref_cls = np.array([_ref_class(a, b) for a, b in zip(adj.label_t0, adj.label_t, strict=True)])
    three = accuracy_report(map_cls, ref_cls, weights)
    # FR-F1: forest / non-forest at year t (forest = stratum 1)
    w2 = {1: weights.get(1, 0.0), 2: weights.get(2, 0.0) + weights.get(3, 0.0)}
    fr_f1 = accuracy_report(np.where(map_cls == 1, 1, 2), np.where(ref_cls == 1, 1, 2), w2)
    a = labels[labels.interpreter == "A"].set_index("point_id")
    b = labels[labels.interpreter == "B"].set_index("point_id")
    both = _pair(a, b)
    metrics = {
        "n_points": int(len(adj)),
        "fr_f1": {
            "overall_accuracy": fr_f1["overall_accuracy"],
            "forest_f1": fr_f1["classes"][1]["f1"],
        },
        "fr_f2": {"loss_f1": three["classes"].get(3, {}).get("f1", float("nan"))},
        "stratified": three,
        "kappa_t": cohens_kappa(both.label_t_a, both.label_t_b) if len(both) else float("nan"),
        "kappa_t0": cohens_kappa(both.label_t0_a, both.label_t0_b) if len(both) else float("nan"),
    }
    _write(p, "forest.json", metrics)
    return metrics


def validate_flood(cfg: DaiffConfig, n_boot: int = 1000) -> dict:
    p = _plan(cfg)
    model, feats = load_model(p.models_dir / p.store.model_id_file.read_text().strip())
    events = pd.read_csv(p.raw.flood_events_csv)
    events = events[events["year"].isin(p.years)]
    df = build_dataset(
        events,
        lambda y: features_for(p, y),
        lambda eid: read_raster(p.raw.flood_fraction(eid), p.grid),
        p.grid,
        cfg,
    )
    train, test = df[df.split == "train"], df[df.split == "test"]
    cls = read_raster(p.store.riskclass(max(p.years)), p.grid)
    valid = cls != 255
    metrics = evaluate(model, test, feats, cfg)
    metrics.update(
        {
            "high_class_area_share": float(np.isin(cls[valid], [4, 5]).mean()),
            "ablation": ablation(train, test, cfg, n_boot=n_boot),
            "block_cv": spatial_block_cv(df, cfg, k=5),
            "permutation_importance": permutation_importance_table(
                model, test, list(FEATURES), cfg.runtime.seed
            ).to_dict(orient="records"),
            "events_train": sorted(train.event_id.unique().tolist()),
            "events_test": sorted(test.event_id.unique().tolist()),
        }
    )
    _write(p, "flood.json", metrics)
    return metrics


def _write(p, name: str, metrics: dict) -> Path:
    p.store.metrics_dir.mkdir(parents=True, exist_ok=True)
    out = p.store.metrics_dir / name
    out.write_text(json.dumps(metrics, indent=2, sort_keys=True, default=float), encoding="utf-8")
    return out


def log_results(cfg: DaiffConfig, what: str, m: dict, by: str = "daiff validate") -> None:
    p = _plan(cfg)
    ref = f"{cfg.project.name} / {p.store.run_id} / {p.commit[:12]}"
    dev = " — dev check, not acceptance" if cfg.project.name == "synthetic" else ""
    if what == "forest":
        f1 = m["fr_f1"]
        ok1 = f1["overall_accuracy"] >= 0.90 and f1["forest_f1"] >= 0.85
        ok2 = m["fr_f2"]["loss_f1"] >= 0.70
        rows = [
            ("FR-F1", ok1, f"OA {f1['overall_accuracy']:.3f}, forest F1 {f1['forest_f1']:.3f}"),
            ("FR-F2", ok2, f"loss F1 {m['fr_f2']['loss_f1']:.3f}"),
        ]
        evidence = "metrics/forest.json"
    else:
        ok_auc = m["auc"] >= 0.80 and m["auc"] - m["hand_baseline_auc_binary"] >= 0.05
        ok_share = m["share_flooded_in_high"] >= 0.60 and m["high_class_area_share"] <= 0.30
        a = m["ablation"]
        rows = [
            (
                "FR-R2",
                ok_auc and ok_share,
                f"AUC {m['auc']:.3f} (HAND {m['hand_baseline_auc_binary']:.3f}); flooded in 4-5 "
                f"{m['share_flooded_in_high']:.2f}, area {m['high_class_area_share']:.2f}",
            ),
            (
                "FR-R3",
                True,
                f"ablation dAUC {a['delta']:.3f} [{a['ci95'][0]:.3f}, {a['ci95'][1]:.3f}]",
            ),
        ]
        evidence = "metrics/flood.json"
    for req, ok, detail in rows:
        write_test_log_entry(
            TEST_LOG,
            requirement=req,
            method="A",
            run_ref=ref,
            result=("PASS" if ok else "FAIL") + f": {detail}{dev}",
            evidence=evidence,
            by=by,
        )
