from __future__ import annotations

import json
import math

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from daiff.alerts.flags import flags
from daiff.api.state import current_plan, layer_path
from daiff.pipeline.stages import RunPlan

router = APIRouter()


def _table(plan: RunPlan, year: int) -> pd.DataFrame:
    path = plan.store.subbasin_csv(year)
    if year not in plan.years or not path.exists():
        raise HTTPException(status_code=404, detail=f"no sub-basin table for {year}")
    return pd.read_csv(path, encoding="utf-8")


def _clean(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v.item() if hasattr(v, "item") else v


@router.get("/api/subbasins")
def subbasins(year: int, plan: RunPlan = Depends(current_plan)) -> JSONResponse:
    table = _table(plan, year).set_index("subbasin_id")
    fc = json.loads(plan.store.subbasins_geojson.read_text(encoding="utf-8"))
    for feat in fc["features"]:
        sid = int(feat["properties"]["subbasin_id"])
        if sid in table.index:
            row = table.loc[sid].to_dict()
            feat["properties"] = {"subbasin_id": sid, **{k: _clean(v) for k, v in row.items()}}
    return JSONResponse(fc)


@router.get("/api/subbasins/{year}.csv")
def subbasins_csv(year: int, plan: RunPlan = Depends(current_plan)) -> FileResponse:
    _table(plan, year)
    return FileResponse(
        plan.store.subbasin_csv(year),
        media_type="text/csv; charset=utf-8",
        filename=f"subbasin_{year}.csv",
    )


@router.get("/api/export/{layer}/{year}.tif")
def export(layer: str, year: int, plan: RunPlan = Depends(current_plan)) -> FileResponse:
    path = layer_path(plan, layer, year)
    return FileResponse(path, media_type="image/tiff", filename=path.name)


@router.get("/api/flags")
def flagged(year: int, plan: RunPlan = Depends(current_plan)) -> dict:
    return {"year": year, "flagged": flags(_table(plan, year))}
