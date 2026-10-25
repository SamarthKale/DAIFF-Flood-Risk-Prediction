from __future__ import annotations

from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from daiff.api.state import AppState, state
from daiff.validation.forest_accuracy import cohens_kappa
from daiff.validation.labels import LabelStore

router = APIRouter()
Label = Literal["forest", "non_forest", "unsure"]


class LabelIn(BaseModel):
    point_id: str
    interpreter: Literal["A", "B", "ADJ"]
    label_t0: Label
    label_t: Label
    note: str = ""


def _paths(st: AppState):
    name = st.cfg.project.name
    return (
        st.reference_dir / f"forest_sample_points_{name}.csv",
        LabelStore(st.reference_dir / f"forest_labels_{name}.csv"),
    )


@router.get("/api/labelling/points")
def points(interpreter: Literal["A", "B", "ADJ"], st: AppState = Depends(state)) -> dict:
    pts_path, store = _paths(st)
    if not pts_path.exists():
        raise HTTPException(
            status_code=404, detail="no sample points yet — run daiff sample-points"
        )
    pts = pd.read_csv(pts_path)
    labels = store.all()
    mine = labels[labels.interpreter == interpreter].set_index("point_id")
    out = []
    for p in pts.to_dict(orient="records"):
        lab = mine.loc[p["point_id"]].to_dict() if p["point_id"] in mine.index else None
        out.append({**p, "label": lab})
    return {"interpreter": interpreter, "points": out, "done": int(len(mine))}


@router.post("/api/labelling/labels")
def submit(body: LabelIn, st: AppState = Depends(state)) -> dict:
    _, store = _paths(st)
    store.upsert(body.point_id, body.interpreter, body.label_t0, body.label_t, body.note)
    return {"ok": True}


@router.get("/api/labelling/agreement")
def agreement(st: AppState = Depends(state)) -> dict:
    _, store = _paths(st)
    labels = store.all()
    a = labels[labels.interpreter == "A"].set_index("point_id")
    b = labels[labels.interpreter == "B"].set_index("point_id")
    adj = set(labels[labels.interpreter == "ADJ"].point_id)
    both = a.merge(b, left_index=True, right_index=True, suffixes=("_a", "_b"))
    differ = both[(both.label_t0_a != both.label_t0_b) | (both.label_t_a != both.label_t_b)]
    return {
        "n_both": int(len(both)),
        "kappa_t": cohens_kappa(both.label_t_a, both.label_t_b) if len(both) else None,
        "kappa_t0": cohens_kappa(both.label_t0_a, both.label_t0_b) if len(both) else None,
        "needs_adjudication": sorted(set(differ.index) - adj),
    }
