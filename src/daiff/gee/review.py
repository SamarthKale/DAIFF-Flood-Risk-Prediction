"""FR-D2 human cloud check: 20 random 1 km windows per season as 10 m true-colour images.

Writes data/<project>/review/fr_d2.html (self-contained: images are embedded) where a reviewer
marks each window "clean" or "cloud/shadow remnants" and downloads the result as CSV. Pass is
at least 18 of 20 clean (SRS FR-D2).
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from rasterio.warp import transform

from daiff.gee import s2
from daiff.grid import Grid

WINDOW_M = 1000
PX = WINDOW_M // 10  # 10 m pixels


def pick_windows(valid: np.ndarray, grid: Grid, n: int, seed: int) -> list[tuple[float, float]]:
    """Centres (x, y in grid CRS) of `n` random windows fully inside the valid footprint."""
    half = WINDOW_M / 2 / grid.res
    rows, cols = np.nonzero(valid)
    rng = np.random.default_rng(seed)
    out: list[tuple[float, float]] = []
    for i in rng.permutation(len(rows)):
        r, c = rows[i], cols[i]
        r0, r1, c0, c1 = int(r - half), int(r + half) + 1, int(c - half), int(c + half) + 1
        if r0 < 0 or c0 < 0 or r1 > valid.shape[0] or c1 > valid.shape[1]:
            continue
        if not valid[r0:r1, c0:c1].all():
            continue
        out.append(
            (grid.transform.c + (c + 0.5) * grid.res, grid.transform.f - (r + 0.5) * grid.res)
        )
        if len(out) == n:
            break
    return out


def fetch_window(ee, aoi, year: int, x: float, y: float, crs: str) -> np.ndarray:
    """10 m RGB uint8 array (PX, PX, 3) of the season composite around (x, y)."""
    img = s2.preview_rgb(ee, aoi, year)
    request = {
        "expression": img,
        "fileFormat": "NUMPY_NDARRAY",
        "grid": {
            "dimensions": {"width": PX, "height": PX},
            "affineTransform": {
                "scaleX": 10,
                "shearX": 0,
                "translateX": x - WINDOW_M / 2,
                "shearY": 0,
                "scaleY": -10,
                "translateY": y + WINDOW_M / 2,
            },
            "crsCode": crs,
        },
    }
    arr = ee.data.computePixels(request)
    return np.stack([arr[n] for n in arr.dtype.names], axis=-1).astype(np.uint8)


def to_data_uri(rgb: np.ndarray, scale: int = 4) -> str:
    im = Image.fromarray(rgb).resize((rgb.shape[1] * scale, rgb.shape[0] * scale), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def build_page(items: list[dict], out: Path, project: str) -> Path:
    cards = []
    for it in items:
        cards.append(
            f'<div class="card" data-id="{it["id"]}" data-year="{it["year"]}">'
            f'<img src="{it["img"]}" width="260" height="260">'
            f'<div class="cap">#{it["id"]} · {it["year"]} · {it["lat"]:.4f}, {it["lon"]:.4f}</div>'
            f'<label><input type="radio" name="w{it["year"]}_{it["id"]}" '
            'value="clean"> clean</label> '
            f'<label><input type="radio" name="w{it["year"]}_{it["id"]}" value="remnants"> '
            "cloud / shadow remnants</label></div>"
        )
    html = f"""<!doctype html><meta charset="utf-8"><title>FR-D2 cloud check — {project}</title>
<style>body{{font-family:system-ui;margin:20px;background:#f5f7f6}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,280px);gap:14px}}
.card{{background:#fff;border:1px solid #dde3e1;border-radius:8px;padding:10px}}
.cap{{font-size:12px;color:#64737a;margin:4px 0}} button{{padding:8px 14px;margin:10px 0}}</style>
<h2>FR-D2 visual cloud check — {project}</h2>
<p>Each image is a 1 km window of the 10 m dry-season composite (true colour). Mark <b>clean</b> if
there are no cloud or cloud-shadow remnants. Pass = at least 18 of 20 clean in every season.
Reviewer name: <input id="who"> <button onclick="save()">Download results (CSV)</button>
<span id="n"></span></p>
<div class="grid">{"".join(cards)}</div>
<script>
function rows(){{return [...document.querySelectorAll('.card')].map(c=>{{
 const v=c.querySelector('input:checked');return [c.dataset.year,c.dataset.id,v?v.value:'']}})}}
document.addEventListener('change',()=>{{const r=rows();document.getElementById('n').textContent=
 r.filter(x=>x[2]).length+' / '+r.length+' marked'}});
function save(){{const who=document.getElementById('who').value||'unknown';
 const csv='year,window,verdict,reviewer\\n'+rows().map(r=>r.concat(who).join(',')).join('\\n');
 const a=document.createElement('a');
 a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));
 a.download='fr_d2_review_'+who+'.csv';a.click()}}
</script>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def score_review(csv_path: Path, required: int = 18) -> dict:
    """Per-season clean counts from a reviewer CSV and the FR-D2 verdict."""
    df = pd.read_csv(csv_path)
    per_year = {}
    for year, g in df.groupby("year"):
        per_year[int(year)] = {
            "clean": int((g["verdict"] == "clean").sum()),
            "total": int(len(g)),
            "marked": int(g["verdict"].notna().sum()),
        }
    ok = all(v["clean"] >= required and v["marked"] == v["total"] for v in per_year.values())
    return {"per_year": per_year, "required_clean": required, "pass": bool(ok)}


def lonlat(grid: Grid, x: float, y: float) -> tuple[float, float]:
    lon, lat = transform(grid.crs, "EPSG:4326", [x], [y])
    return lon[0], lat[0]


def save_windows_json(items: list[dict], out: Path) -> None:
    slim = [{k: v for k, v in it.items() if k != "img"} for it in items]
    out.write_text(json.dumps(slim, indent=2), encoding="utf-8")
