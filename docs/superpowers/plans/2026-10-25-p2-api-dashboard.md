# P2 API + Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Checkbox steps. CLAUDE.md session protocol applies to every task.

**Goal:** A FastAPI backend serving tiles, tables, exports, point queries, flags, metrics and labelling
from the published run, and a React + MapLibre dashboard (Map, Sub-basins, Validation, Labelling) —
all working on the synthetic run.

**Architecture:** `daiff.api` (FastAPI app factory reading `data/store/CURRENT`), routers per concern;
`web/` Vite React TS app talking to `/api`. In production `daiff serve` also serves `web/dist`.

**Tech Stack:** fastapi, uvicorn, rio-tiler, httpx (tests); React 18, TypeScript (strict), Vite,
maplibre-gl, @tanstack/react-table, recharts, react-router-dom, vitest + @testing-library/react.

**Spec:** §6.13, §6.14, §8. **Depends on:** P1 (a published synthetic run).

## Global Constraints

- Layers: `preview, forest, loss, susceptibility, riskclass, delta_s`. Colormaps fixed server-side:
  forest 0–1 white→dark green; loss 0–1 transparent→red; susceptibility 0–1 viridis; riskclass
  1–5 `#1a9850,#91cf60,#fee08b,#fc8d59,#d73027`; delta_s −0.2–0.2 diverging blue–white–red.
- Banner text exactly: "Experimental decision support — not an official flood warning." followed by
  "Model AUC <x.xx> (held-out events)" (or "Forest OA <x.x>%" on the forest layers) from `/api/meta`.
- API never writes into `data/store/`; labels go to `reference/forest_labels_<project>.csv`.
- NFR-5: tiles < 3 s, table < 1 s.

## Review Focus

1. **Year with a missing layer** (e.g. `preview` absent for synthetic) — tile endpoint returns 404 JSON, map shows the layer as unavailable instead of breaking; pinned in Task 2.
2. **Click outside the basin / on nodata** — `/api/point` returns 404 with message, panel shows "No data here"; pinned in Task 4.
3. **Two interpreters labelling the same point** — labels keyed by `(point_id, interpreter)`, re-submission overwrites only that pair; pinned in Task 5.
4. **No published run** — every endpoint returns 503 `{"detail": "no published run"}`; pinned in Task 1.
5. **Sub-basin names with non-ASCII characters** — CSV/GeoJSON UTF-8 round-trip; pinned in Task 3.

---

### Task 1: API app factory and `/api/meta`
**Files:** `src/daiff/api/__init__.py`, `app.py`, `deps.py`, `routers/meta.py`; `tests/api/conftest.py` (fixture: synthetic run built once per session via `run_pipeline`), `tests/api/test_meta.py`. Deps: `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `rio-tiler>=7.0`, dev `httpx>=0.27`.
- `create_app(cfg: DaiffConfig) -> FastAPI`; `CurrentRun` dependency (run_id, RunStore, years, t0, metrics) — 503 if none.
- `GET /api/meta` → `{run_id, project, years, t0, layers, legends, metrics: {flood_auc, forest_oa}}`.
- CLI `daiff serve -c CFG [--port 8000]`.
- [x] Tests: meta keys/values on synthetic run; 503 without run (Review 4). Commit `feat(api): app factory and meta`.

### Task 2: Tiles (FR-V1, NFR-5)
**Files:** `routers/tiles.py`, `colormaps.py`; `tests/api/test_tiles.py`.
- `GET /api/tiles/{layer}/{year}/{z}/{x}/{y}.png` with rio-tiler `Reader` (WebMercator TMS), colormap per layer, nodata transparent, `Cache-Control: max-age=3600`; 404 JSON for unknown layer/year/missing file (Review 1); empty tile outside bounds returns transparent 256×256 PNG.
- [x] Tests: tile over synthetic centre is PNG 256×256 with non-transparent pixels; unknown layer 404; tile render < 300 ms locally (`time.perf_counter`). Commit `feat(api): COG tile endpoint`.

### Task 3: Sub-basins and exports (FR-V2, NFR-6)
**Files:** `routers/subbasins.py`, `routers/export.py`; tests.
- `GET /api/subbasins?year=` GeoJSON (EPSG:4326, simplified 0.0005°) with Table 25 properties; `GET /api/subbasins/{year}.csv` streams the pipeline file unchanged (`text/csv; charset=utf-8`); `GET /api/export/{layer}/{year}.tif` streams the COG (`Content-Disposition: attachment`); `GET /api/flags?year=`.
- [x] Tests: `test_fr_v2_csv_is_byte_identical_to_pipeline`; `test_fr_v2_geotiff_export_has_crs_and_transform` (rasterio open of response bytes == grid); non-ASCII name round-trip (Review 5); flags == `flags(table)`. Commit `feat(api): sub-basin table, exports and flags`.

### Task 4: Point query (FR-V3)
**Files:** `routers/point.py`, `src/daiff/flood/explain.py`; tests.
- `explain_cell(model, features_row: np.ndarray, names) -> list[tuple[str, float]]` — XGBoost `pred_contribs=True`, top-3 by |contribution|.
- `GET /api/point?lon=&lat=&year=` → `{row, col, forest_fraction: [{year, value}], susceptibility, risk_class, delta_s, top_features: [{name, contribution, value}]}`; 404 outside grid/nodata (Review 2).
- [x] Tests: `test_fr_v3_point_values_match_rasters_at_10_random_points` (seeded); top_features length 3 and names ⊂ FEATURES; outside → 404. Commit `feat(api): point query with top-3 feature contributions`.

### Task 5: Metrics and labelling endpoints
**Files:** `routers/metrics.py`, `routers/labelling.py`, `src/daiff/validation/labels.py`; tests.
- `GET /api/metrics` → contents of `metrics/*.json`.
- `GET /api/labelling/points?interpreter=A|B|ADJ` → sample points (from `reference/forest_sample_points_<project>.csv`) + that interpreter's existing labels; `POST /api/labelling/labels` `{point_id, interpreter, label_t0, label_t, note}` (labels: `forest|non_forest|unsure`); `GET /api/labelling/agreement` → kappa, n disagreements, list of points needing adjudication.
- `LabelStore(csv_path)` with `upsert(...)`, `all() -> pd.DataFrame` (UTF-8, sorted, atomic write via temp file + replace).
- [x] Tests: upsert overwrites same (point, interpreter) only (Review 3); agreement kappa matches `cohens_kappa`. Commit `feat(api): metrics and reference-labelling endpoints`.

### Task 6: Web scaffold and API client
**Files:** `web/` via `npm create vite@latest web -- --template react-ts`, then add deps; `web/src/api.ts`, `web/src/types.ts`, `web/vite.config.ts` (proxy `/api` → `http://localhost:8000`), `web/src/App.tsx` (router + nav: Map, Sub-basins, Validation, Labelling), `web/src/components/Banner.tsx`.
- [ ] Vitest: `Banner` renders exact text with AUC from props; `api.ts` builds tile URL `"/api/tiles/{layer}/{year}/{z}/{x}/{y}.png"`. `npm run build` succeeds. Commit `feat(web): scaffold React app, API client, banner`.

### Task 7: Map page (FR-V1, FR-V3, NFR-8)
**Files:** `web/src/pages/MapPage.tsx`, `components/LayerSwitcher.tsx`, `YearSelector.tsx`, `Legend.tsx`, `PointPanel.tsx`.
- MapLibre with CARTO Positron basemap (attribution), raster source per layer/year, sub-basin outlines (flagged = red), click → `/api/point` → panel with Recharts line (forest fraction by year), S, class, ΔS, top-3 features; "No data here" on 404. Banner always visible.
- [ ] Vitest: LayerSwitcher emits selected layer; PointPanel renders values and "No data here". Manual: `uv run daiff serve` + `npm run dev`, every layer for every year loads (record in STATUS). Commit `feat(web): map page with layers, years, legend and point panel`.

### Task 8: Sub-basins, Validation and Labelling pages
**Files:** `pages/SubbasinsPage.tsx` (TanStack sortable table, name search box, CSV/GeoTIFF download links, row click → map zoom), `pages/ValidationPage.tsx` (metrics cards, ablation table, confusion matrix), `pages/LabellingPage.tsx` (interpreter picker, point-by-point view with Esri World Imagery + preview composites per year, buttons forest / non-forest / unsure for t₀ and t, progress counter, agreement summary).
- [ ] Vitest: table sorts by `forest_loss_ha` desc on header click; search filters by name; labelling submits the right payload. Commit `feat(web): sub-basins, validation and labelling pages`.

### Task 9: Production serving, CI web job, NFR-5 check, close-out
- `daiff serve` mounts `web/dist` at `/` when present (SPA fallback to `index.html`).
- CI job `web`: `actions/setup-node@v4` (node 20), `npm ci`, `npm test -- --run`, `npm run build` in `web/`.
- `scripts/nfr5_timing.py`: times 5 layer tiles + table endpoint against a running server, appends to `docs/perf/`.
- [ ] Update verification matrix (FR-V1–V3, NFR-5, NFR-8 → passing on synthetic), STATUS → P2 done, next = P3. Commit `feat: serve built dashboard; ci web job; close P2`; push.
