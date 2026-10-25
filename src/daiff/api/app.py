"""FastAPI application factory (spec §6.13). Reads only the published run and reference/."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from daiff.api.routers import labelling, meta, point, subbasins, tiles
from daiff.api.state import AppState
from daiff.config import DaiffConfig
from daiff.pipeline.stages import REPO_ROOT


def _mount_dashboard(app: FastAPI, dist: Path) -> None:
    """Serve web/dist; unknown non-API paths fall back to index.html (client-side routes)."""
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        target = (dist / path).resolve()
        if path and target.is_file() and dist.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(index)


def create_app(
    cfg: DaiffConfig, reference_dir: Path | None = None, web_dist: Path | None = None
) -> FastAPI:
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
    dist = Path(web_dist) if web_dist else REPO_ROOT / "web" / "dist"
    if (dist / "index.html").exists():
        _mount_dashboard(app, dist)
    return app
