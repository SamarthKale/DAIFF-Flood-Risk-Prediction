"""FastAPI application factory (spec §6.13). Reads only the published run and reference/."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from daiff.api.routers import labelling, meta, point, subbasins, tiles
from daiff.api.state import AppState
from daiff.config import DaiffConfig
from daiff.pipeline.stages import REPO_ROOT


def create_app(cfg: DaiffConfig, reference_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="DAIFF API", version="0.1.0")
    app.state.daiff = AppState(
        cfg=cfg, reference_dir=Path(reference_dir or REPO_ROOT / "reference")
    )
    app.state.plans = {}
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (meta.router, tiles.router, subbasins.router, point.router, labelling.router):
        app.include_router(r)
    return app
