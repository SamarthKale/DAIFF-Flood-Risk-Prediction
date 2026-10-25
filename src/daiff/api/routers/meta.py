from __future__ import annotations

from fastapi import APIRouter, Depends

from daiff.api.colormaps import LEGENDS
from daiff.api.state import LAYERS, current_plan, read_metrics
from daiff.pipeline.stages import RunPlan

router = APIRouter()


@router.get("/api/meta")
def meta(plan: RunPlan = Depends(current_plan)) -> dict:
    metrics = read_metrics(plan)
    flood = metrics.get("flood") or metrics.get("flood_train") or {}
    forest = metrics.get("forest", {})
    available = [
        layer
        for layer in LAYERS
        if layer != "preview" or plan.store.preview(max(plan.years)).exists()
    ]
    return {
        "run_id": plan.store.run_id,
        "project": plan.cfg.project.name,
        "basin": plan.cfg.project.basin,
        "years": list(plan.years),
        "t0": plan.t0,
        "layers": available,
        "legends": LEGENDS,
        "metrics": {
            "flood_auc": flood.get("auc"),
            "forest_oa": forest.get("fr_f1", {}).get("overall_accuracy"),
        },
    }


@router.get("/api/metrics")
def metrics(plan: RunPlan = Depends(current_plan)) -> dict:
    return read_metrics(plan)
