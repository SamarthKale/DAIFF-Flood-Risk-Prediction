from __future__ import annotations

from functools import lru_cache

import numpy as np
from fastapi import APIRouter, Depends, Response
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import Reader
from rio_tiler.utils import render

from daiff.api.colormaps import RISK_CMAP, STYLES
from daiff.api.state import current_plan, layer_path
from daiff.pipeline.stages import RunPlan

router = APIRouter()
HEADERS = {"Cache-Control": "public, max-age=3600"}


@lru_cache(maxsize=1)
def _empty_png() -> bytes:
    return render(np.zeros((1, 256, 256), dtype="uint8"), mask=np.zeros((256, 256), "uint8"))


@lru_cache(maxsize=2048)
def _render(path: str, layer: str, z: int, x: int, y: int, mtime: float) -> bytes:
    del mtime  # part of the cache key only
    name, rng = STYLES[layer]
    with Reader(path) as src:
        try:
            img = src.tile(x, y, z, tilesize=256)
        except TileOutsideBounds:
            return _empty_png()
    if layer == "riskclass":
        return img.render(img_format="PNG", colormap=RISK_CMAP)
    if layer == "preview":
        return img.render(img_format="PNG")
    img.rescale(in_range=(rng,))
    return img.render(img_format="PNG", colormap=cmap.get(name))


@router.get("/api/tiles/{layer}/{year}/{z}/{x}/{y}.png")
def tile(
    layer: str, year: int, z: int, x: int, y: int, plan: RunPlan = Depends(current_plan)
) -> Response:
    path = layer_path(plan, layer, year)
    data = _render(str(path), layer, z, x, y, path.stat().st_mtime)
    return Response(content=data, media_type="image/png", headers=HEADERS)
