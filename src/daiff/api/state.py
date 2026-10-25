"""Shared API state: the config, the reference folder, and the published run (read-only)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request

from daiff.config import DaiffConfig
from daiff.pipeline.stages import RunPlan, plan_for_run
from daiff.store.run_store import current_run

LAYERS = ("preview", "forest", "loss", "susceptibility", "riskclass", "delta_s")


@dataclass
class AppState:
    cfg: DaiffConfig
    reference_dir: Path


def state(request: Request) -> AppState:
    return request.app.state.daiff


def current_plan(request: Request) -> RunPlan:
    st = state(request)
    run_id = current_run(st.cfg.data_root)
    if run_id is None:
        raise HTTPException(status_code=503, detail="no published run")
    cache = request.app.state.plans
    if run_id not in cache:
        cache[run_id] = plan_for_run(st.cfg, run_id)
    return cache[run_id]


def layer_path(plan: RunPlan, layer: str, year: int) -> Path:
    s = plan.store
    paths = {
        "preview": s.preview(year),
        "forest": s.forest(year),
        "loss": s.loss(plan.t0, year),
        "susceptibility": s.susceptibility(year),
        "riskclass": s.riskclass(year),
        "delta_s": s.delta_s(year),
    }
    if layer not in paths or year not in plan.years:
        raise HTTPException(status_code=404, detail=f"unknown layer/year {layer}/{year}")
    p = paths[layer]
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"{layer} is not available for {year}")
    return p


def read_metrics(plan: RunPlan) -> dict:
    out = {}
    if plan.store.metrics_dir.exists():
        for f in sorted(plan.store.metrics_dir.glob("*.json")):
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out
