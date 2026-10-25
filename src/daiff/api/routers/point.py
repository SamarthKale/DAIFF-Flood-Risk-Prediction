from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
from fastapi import APIRouter, Depends, HTTPException
from rasterio.warp import transform
from rasterio.windows import Window

from daiff.api.state import current_plan
from daiff.flood.explain import explain_cell
from daiff.flood.model import load_model
from daiff.pipeline.stages import COUPLING_BANDS, RAIN_BANDS, RunPlan
from daiff.terrain.derive import STATIC_BANDS

router = APIRouter()


def _px(path: Path, r: int, c: int) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(window=Window(c, r, 1, 1))[:, 0, 0].astype(float)


@lru_cache(maxsize=4)
def _model(model_dir: str):
    return load_model(Path(model_dir))


def _clean(v: float) -> float | None:
    return None if np.isnan(v) else float(v)


@router.get("/api/point")
def point(lon: float, lat: float, year: int, plan: RunPlan = Depends(current_plan)) -> dict:
    if year not in plan.years:
        raise HTTPException(status_code=404, detail=f"No data here for year {year}")
    xs, ys = transform("EPSG:4326", plan.grid.crs, [lon], [lat])
    try:
        r, c = plan.grid.xy_to_rowcol(xs[0], ys[0])
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail="No data here (outside the study area)"
        ) from exc
    s = plan.store
    S = _px(s.susceptibility(year), r, c)[0]
    if np.isnan(S):
        raise HTTPException(status_code=404, detail="No data here (water or missing input)")
    model_id = s.model_id_file.read_text(encoding="utf-8").strip()
    model, feats = _model(str(plan.models_dir / model_id))
    values = dict(zip(STATIC_BANDS, _px(s.static_features, r, c), strict=True))
    values.update(zip(RAIN_BANDS, _px(plan.rain, r, c), strict=True))
    values.update(zip(COUPLING_BANDS, _px(s.coupling(year), r, c), strict=True))
    values["CN"] = _px(s.cn(year), r, c)[0]
    row = np.array([values[f] for f in feats])
    return {
        "row": int(r),
        "col": int(c),
        "year": year,
        "forest_fraction": [
            {"year": y, "value": _clean(_px(s.forest(y), r, c)[0])} for y in plan.years
        ],
        "susceptibility": float(S),
        "risk_class": int(_px(s.riskclass(year), r, c)[0]),
        "delta_s": _clean(_px(s.delta_s(year), r, c)[0]),
        "top_features": explain_cell(model, row, feats),
    }
