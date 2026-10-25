# DAIFF — System Design Specification

| | |
|---|---|
| Date | 2026-10-25 |
| Status | Design approved in brainstorming; written spec under review |
| Implements | DAIFF-SRS v1.0 — requirement register in [`docs/srs/requirements.md`](../../srs/requirements.md) |
| Authority | Architecture, interfaces and conventions. `CLAUDE.md` summarises this file; this file wins on conflict. Requirement text always comes from the register. |

## 1. Goal and success criteria

DAIFF is a decision-support prototype for the **Kopili basin, Assam**. It maps annual forest loss
from Sentinel-2, turns that loss into a change in flood susceptibility through three coupling
features (C1–C3), and presents maps, sub-basin statistics, flags and alerts in a web dashboard.

Success is the SRS acceptance procedure (SRS 8.3): every Tier 1 requirement — FR-D1–D5, FR-F1–F4,
FR-C1–C4, FR-R1–R3, FR-V1–V3, FR-A1 and NFR-1–NFR-10 — passes its acceptance criterion, recorded in
`docs/test_log.md`. Tier 2 (FR-F5, FR-R4, FR-R5, FR-A2) and Tier 3 (FR-R6, FR-A3) are built and
their results reported; they never block Tier 1.

## 2. Decisions

| ID | Decision | Rationale |
|---|---|---|
| D-01 | Data access through **Google Earth Engine** (free non-commercial projects) | Every dataset in one catalogue; server-side compositing keeps local downloads to a few GB |
| D-02 | Pilot basin **Kopili, Assam**; grid CRS **EPSG:32646** (UTM 46N) | Near-annual floods make ≥ 6 events low-risk; documented upstream forest loss. Closes OI-1 |
| D-03 | **All three tiers** in scope, built in tier order | Team decision |
| D-04 | Local compute is **CPU-only**; all GPU work runs on **Google Colab**; the local GPU is never used | Team decision |
| D-05 | Develop on a laptop now, **SLURM-ready** (dask-jobqueue config + job scripts) | HPC access pending (OI-4) |
| D-06 | Dashboard: **FastAPI + rio-tiler** backend; **React + TypeScript + Vite + MapLibre GL** frontend | Tiled COG serving meets NFR-5 |
| D-07 | Public GitHub repo, trunk-based on `main`, push after every task, **CI non-blocking** | Relay handoff between teammates |
| D-08 | **No AI co-author trailers** in commits or PRs | Team decision |
| D-09 | **Architecture A**: GEE produces pixels (composites, forest classes, S1 flood masks, clipped reference layers); local Python does terrain, coupling, models, validation, outputs | C2 needs weighted D8 accumulation and FR-C1 needs exact unit tests — neither is possible server-side |
| D-10 | GEE products are exported as **Earth Engine assets** (batch tasks) and downloaded tile by tile with `ee.data.getPixels` onto the common grid. Colab exchanges data through **Google Drive** | No Drive API or OAuth client needed locally; long computations never hit interactive time limits |
| D-11 | Own small **stage-DAG runner**, not Snakemake/Prefect | Readable by any teammate or Claude session in one sitting |
| D-12 | Hydrologic soil groups from **HYSOGs250m** (derived from SoilGrids) | Purpose-built HSG product. Deviation from "SoilGrids" logged |
| D-13 | **Python 3.12** (matches Colab), env in `.venv` managed by **uv**, `link-mode = copy` | Repo lives on an exFAT drive; no hard links |
| D-14 | Forest classifier: **Random Forest in GEE** (primary); small **U-Net on Colab** (challenger). The one with better reference-sample metrics is used | SRS 2.3 allows either |
| D-15 | Flood model: **XGBoost with monotone constraints** | SRS 3.4 item 3 |
| D-16 | Design rainfall and climatology from **CHIRPS** (0.05°); **NOAA CPC** also ingested (FR-D3) and used as cross-check | CPC 0.5° is coarser than most sub-basins; SRS 2.8 permits CHIRPS |
| D-17 | **Reference-labelling tool** inside the dashboard; labels committed to `reference/` | SRS 7.3 needs 600 points, two interpreters + adjudicator |

Interpretations made while designing (also logged in `docs/decisions.md`):

| ID | Interpretation |
|---|---|
| D-18 | **Season year**: forest map *t* = dry-season composite 1 Nov (t−1) – 31 Mar t. A flood in the monsoon of year Y is paired with forest map Y, the latest map before the event (SRS 3.4 item 2) |
| D-19 | **Sub-basin risk class** = risk class of the sub-basin's mean susceptibility (`mean_s` binned with the cell breaks). FR-A1 flags classes 4–5 |
| D-20 | **ΔF** = fraction of the cell's 10 m pixels inside MMU-filtered loss patches (forest at t₀, non-forest at t). f(c,t) is the raw 3×3 aggregation |
| D-21 | **A(c)** in Eq. (1) includes c itself (standard flow-accumulation convention) |
| D-22 | **CN** is area-weighted by forest fraction: CN = f·CN_woods[HSG] + (1−f)·CN_nonforest[class, HSG]. Makes CN continuous and monotone in loss |
| D-23 | Dual soil groups (A/D, B/D, C/D) are treated as **D** (undrained) |
| D-24 | Baseline **t₀ defaults to 2019** if GEE's S2 L2A covers < 90% of the AOI in the 2017/2018 dry seasons (checked in P3; OI-2) |

## 3. Architecture

```
┌──────────────────────── Google Earth Engine (team's free project) ───────────────────────┐
│ S2 L2A ─ SCL mask ─ dry-season median ─ indices ─ Random Forest → forest class (10 m)    │
│ S1 GRD ─ pre/post VV change ─ Otsu → flood mask per event                                │
│ Clip/reproject: SRTM, Hansen GFC, JRC GSW, Global Flood DB, HYSOGs, Dynamic World,       │
│                 HydroBASINS sub-basins, CHIRPS daily per sub-basin                       │
└────────── Export.image.toAsset (batch) ──► ee.data.getPixels tiles on the common grid ───┘
                                     │
 NOAA PSL (CPC NetCDF) ──┐           ▼
 OSM rivers (Overpass) ──┴──► data/raw/ ──► local pipeline  (daiff run | daiff watch)
                               terrain → forest → coupling → flood → tables/flags → validation → publish
                                     │
                                     ▼
                     data/store/<run_id>/   +   data/store/CURRENT
                                     │
            FastAPI: tiles · sub-basins · point query · exports · flags/alerts · metrics · labelling
                                     │
                         React + MapLibre dashboard (browser)

 Google Colab (GPU) ◄── Google Drive (chips, weights, sequences) ──► U-Net challenger, Tier 3
```

The coupling stage is the **only** path from forest outputs to the flood model (SRS 3.1). No other
module reads forest rasters on behalf of the flood model.

## 4. Repository layout

```
CLAUDE.md                     session protocol, hard rules, conventions
README.md                     human quick start
pyproject.toml, uv.lock       package `daiff`, Python 3.12; extras: dev, dl (CPU torch), hpc
.env.example                  DAIFF_GEE_PROJECT, DAIFF_DATA_ROOT, SMTP_* (real .env is gitignored)
configs/
  kopili.yaml                 AOI, years, t0, grid, thresholds, seeds, pinned dataset IDs
  synthetic.yaml              fake basin for tests, CI and demos (no GEE)
src/daiff/
  config.py                   pydantic models, loading, canonical hash
  grid.py                     Grid, nested 10 m grid, FR-D5 alignment check
  store/                      COG write/read, provenance tags, run store, publish, metadata check
  pipeline/                   Stage, DAG runner, fingerprints, `watch`
  gee/                        auth, aoi, s2, forest_rf, s1_flood, refdata, export/download
  ingest/                     rainfall (CPC, CHIRPS), rivers (OSM), sub-basin names
  terrain/                    fill, D8, accumulation, slope, TWI, streams, HAND, distance (numba)
  forest/                     aggregation, loss, MMU, stats, Hansen comparison, U-Net model code
  coupling/                   C1, C2 (weighted upstream loss), C3 (CN, SCS runoff), design rainfall
  flood/                      events, labels, dataset, model, predict, classes, baseline, ablation,
                              scenarios (T2), rainfall risk (T2)
  validation/                 sampling, forest accuracy, flood skill, alert skill, kappa, reports
  alerts/                     flags (FR-A1), thresholds, engine, notifiers (T2)
  api/                        FastAPI app and routers
  research/                   Tier 3: fusion, forecaster
  synthetic.py                synthetic basin generator
  cli.py                      `daiff` command (typer)
web/                          React + TS + Vite + MapLibre app
notebooks/colab/              thin notebooks installing `daiff` from GitHub (U-Net, Tier 3)
hpc/slurm/                    sbatch scripts + dask-jobqueue config
tests/                        unit/, integration/, api/ (+ web tests under web/)
reference/                    committed small data: flood_events.csv, forest_sample_points.csv,
                              forest_labels.csv, subbasin_names.csv
docs/
  srs/                        requirements.md (register), problem-statement.md, SRS PDF (local only)
  superpowers/specs|plans/    this spec; one plan per phase
  STATUS.md                   handoff state
  decisions.md                decision log + open-issue tracker
  verification_matrix.md      requirement → test/script → status
  test_log.md                 SRS 8.3 test log
  perf/                       NFR-1/NFR-2 timing logs
  setup/gee.md                Earth Engine registration steps
  LICENSES.md                 data and library licences (NFR-7)
data/                         gitignored: raw/, interim/, models/, state/, store/
.github/workflows/ci.yml      tests, coverage, synthetic end-to-end, gitleaks, web build
```

## 5. Spatial, temporal and file conventions

- **Grid.** EPSG:32646; 30 m analysis cells; origin snapped to multiples of 30 m; extent = AOI bounds
  + 1 km buffer. The 10 m pixel grid shares the origin, so each 30 m cell is exactly 3 × 3 pixels.
  The grid definition lives in config and is written to `data/raw/grid.json`.
- **Alignment.** Rasters are resampled only in ingestion, with an explicit method (bilinear for
  continuous, nearest/mode for categorical). Readers never resample; they raise on misalignment.
  `daiff check-grid` implements FR-D5.
- **Years.** Season-year convention D-18. t₀ from config (D-24, OI-2).
- **Nodata.** float32 → NaN; uint8 classes → 255. Permanent water (JRC occurrence > 90%) is excluded
  from flood labels and set to nodata in susceptibility outputs.
- **Units.** Rainfall mm; elevation m; slope degrees; forest loss ha in tables; areas km².
- **Rasters.** COG, DEFLATE (predictor 2 for integers, 3 for floats), 512 × 512 blocks, overviews.
- **Provenance (NFR-4).** GDAL metadata tags on every output: `DAIFF_RUN_ID`, `DAIFF_CONFIG_HASH`,
  `DAIFF_CODE_COMMIT` (`<sha>` or `<sha>-dirty`), `DAIFF_MODEL_ID`, `DAIFF_INPUTS` (JSON list of
  input paths + SHA-256), `DAIFF_DATA_VERSIONS` (dataset IDs + versions), `DAIFF_YEAR`, `DAIFF_T0`.
  Tags hold no timestamps so a tagged config re-run can be byte-identical (NFR-3). Wall-clock
  timings go only to `run_metadata.json` and `docs/perf/`.
- **run_id** = first 12 hex chars of SHA-256(config hash + code commit + input checksums).

## 6. Module design

### 6.1 `config`
Pydantic models loaded from YAML, with environment overrides:
`project` (name, AOI source, sub-basin level), `grid` (crs, res, buffer), `years` (t₀, year list,
season months), `gee` (project from `DAIFF_GEE_PROJECT`, asset root, pinned dataset IDs), `forest`
(classifier, RF params, sample sizes, MMU 0.5 ha), `terrain` (stream threshold km², major-stream
threshold for FR-D4), `coupling` (return period 10 y, CN table, DW→TR-55 mapping, dual-HSG policy),
`flood` (features, monotone signs, sample caps, split years, block size 10 km, class breaks or
quantile), `alerts` (percentile 99, wet-day 1 mm, notifier), `runtime` (dask workers, tile size,
seed), `paths` (`data_root` default `./data`, env `DAIFF_DATA_ROOT`). The config hash is SHA-256 of
canonical JSON.

### 6.2 `grid`
`Grid(crs, transform, width, height)` with `from_bounds()`, `nested(factor=3)`, `cell_area_m2`,
`xy_to_rowcol()`. `check_alignment(paths) -> AlignmentReport` lists every layer whose CRS,
transform or shape differs (FR-D5).

### 6.3 `store`
`write_cog(path, array, grid, nodata, tags, band_names=None)`, `read_raster(path, grid)`,
`ProvenanceBuilder`, `RunStore(data_root, run_id)` returning Appendix C paths,
`publish(run_id)` (writes `data/store/CURRENT` — a plain text file because exFAT has no symlinks),
`check_metadata(run_dir) -> list[problem]` behind `daiff check-metadata` (NFR-4).

### 6.4 `pipeline`
A `Stage` declares name, input paths, config sections, output paths and a function. The runner sorts
stages topologically and computes a fingerprint (input checksums + config-section hash + stage code
version). It stores the fingerprint in `data/state/<stage>.json` and skips stages whose fingerprint
is unchanged.
- `daiff run -c cfg [--stages …] [--years …] [--force]`.
- `daiff watch -c cfg` polls the forest-class directory (polling, not filesystem events — exFAT and
  network drives are unreliable for events). On a new year it runs aggregation → coupling →
  prediction → ΔS → tables → flags → publish with the existing trained model (FR-C2).
- Per-cell stages are tiled with Dask: `LocalCluster` now, `dask_jobqueue.SLURMCluster` through
  config later. Grid-global algorithms (fill, D8, accumulation) run basin-wide in memory
  (Kopili ≈ 18 M cells, about 70 MB per float32 layer).

### 6.5 `gee`
- `auth`: `ee.Initialize(project=…)`. On failure it prints the fix and a link to `docs/setup/gee.md`.
- `aoi`: Kopili polygon assembled from HydroBASINS (`WWF/HydroSHEDS/v1/Basins/hybas_<level>`) by
  upstream selection from the Kopili outlet. Sub-basins are exported as `data/raw/subbasins.geojson`.
  The level is chosen in P3 to give roughly 20–60 sub-basins (default 8).
- `s2`: `COPERNICUS/S2_SR_HARMONIZED` filtered to AOI and season. The SCL mask removes classes 0, 1,
  3, 8, 9, 10. The per-season median composite has bands B2–B8A, B11, B12 plus NDVI and NBR.
  `s2_inventory()` lists the MGRS tiles and scenes used (FR-D1).
- `forest_rf`: automatic high-confidence training points. **Forest**: Hansen treecover2000 ≥ 30,
  no Hansen loss up to t, and Dynamic World mean `trees` probability ≥ 0.6. **Non-forest**:
  treecover2000 < 10 and DW `trees` < 0.2, or Hansen loss before t and DW `trees` < 0.2.
  Samples are stratified (default 5,000 per class per year) and pooled across years.
  `ee.Classifier.smileRandomForest(300, seed)` is trained once and applied per year. Masked pixels
  take the previous year's class when available; the rest stay nodata, and the gap share is reported
  (FR-D2 ≤ 5%). Training points are never used for validation.
- `s1_flood`: per event from `reference/flood_events.csv`. Reference = median VV over a dry window
  before the event; event = minimum VV in the event window; 50 m focal-mean speckle smoothing. Otsu
  threshold on the difference histogram within the AOI. JRC permanent water and slope > 5° are
  excluded. The 10 m mask is aggregated to a 30 m flooded fraction.
- `refdata`: SRTM `USGS/SRTMGL1_003` (bilinear), Hansen GFC (pinned version), JRC GSW occurrence,
  Global Flood Database events, HYSOGs250m, Dynamic World annual mode label, ESA WorldCover
  (cross-check). CHIRPS `UCSB-CHG/CHIRPS/DAILY` sub-basin daily means are fetched as tables.
- `export`: `submit_asset_export()`, `wait_for_tasks()`, and `download_asset(asset_id, grid, path,
  tile=2048)` — `getPixels` tiles mosaicked into a COG. Idempotent: skips when the local file
  records the same asset version.

### 6.6 `ingest`
- `rainfall`: NOAA CPC Global Unified daily NetCDF (NOAA PSL, 2000–present), area-weighted to
  sub-basins, and CHIRPS series from GEE. Gaps > 3 days are written to `rainfall_gaps.csv` (FR-D3).
- `rivers`: OSM waterways (river, canal) for the AOI bbox via the Overpass API, stored as
  `data/raw/osm_rivers.gpkg` for the FR-D4 check.
- `names`: `reference/subbasin_names.csv` maps HYBAS_ID to a readable name (dominant OSM river name
  + district). It is generated as a suggestion, then hand-edited; NFR-6 needs named sub-basins.

### 6.7 `terrain` (FR-D4)
Numba implementations on the 30 m grid:
- priority-flood depression filling with epsilon (Barnes et al. 2014)
- D8 with ESRI codes (1, 2, 4, …, 128)
- topological ordering and weighted flow accumulation
- slope (Horn)
- TWI = ln(a / tan β), with a = specific catchment area and tan β ≥ 0.001
- streams = accumulation ≥ threshold
- HAND = z − z(first stream cell downstream along D8)
- distance to river via a Euclidean distance transform

Output `static_features.tif`, multiband with band names in tags. `daiff check-streams` reports the
share of derived major-stream length within 60 m of OSM rivers (target ≥ 90%).

### 6.8 `forest` (FR-F1–F5)
- Input: `forest10m_<year>.tif` (0 = non-forest, 1 = forest, 255 = nodata).
- f(c,t) = mean of valid pixels in each 3×3 block (NaN if none valid) → `forest_<year>.tif`.
- Loss between any y₁ < y₂ (FR-F2): pixel forest at y₁ and non-forest at y₂. 8-connected patches
  smaller than the MMU (0.5 ha = 50 px) are removed (FR-F4) → `loss10m_<y1>_<y2>.tif`. The 30 m
  ΔF (D-20) → `loss_<t0>_<year>.tif`. Regrowth → `regrowth_<t0>_<year>.tif` (not used in Tier 1).
- Stats (FR-F3): per sub-basin and year, loss ha = loss-pixel count × 0.01, which equals the sum of
  loss pixels by construction. The Hansen comparison counts loss-year pixels in (t₀, t] with
  treecover2000 ≥ 30 and flags differences > 25% for explanation.
- U-Net challenger (D-14): 256 × 256 chips of 10 m composites with the same automatic labels are
  exported to Drive. A small U-Net (~2 M parameters) is trained and run on Colab, one year at a time
  to stay within Drive quota. Class maps return through Drive and `daiff forest import-unet`.
- FR-F5 (Tier 2): monthly dry-season composites with the same classifier, plus a consistency report
  against the annual map.

### 6.9 `coupling` (FR-C1–C4)
- **C1**: f(c,t), ΔF(c,t).
- **C2**: U = weighted accumulation of a·ΔF ÷ weighted accumulation of a, in D8 topological order
  (D-21). Cells with nodata ΔF are excluded from both sums.
- **C3**: CN per D-22. The DW→TR-55 mapping is in config (trees → woods, grass/shrub → pasture,
  crops → row crops, bare → fallow, built → impervious; water excluded); D-23 for dual HSG.
  S and Q follow Eqs. (2) and (3). P is the sub-basin 10-year one-day design rainfall from a Gumbel
  fit (method of moments) to CHIRPS annual maxima (OI-3).
- Outputs: `coupling_<year>.tif` with the four Appendix C bands (f, ΔF, U, Q); CN in a separate
  `cn_<year>.tif`.
- Monotonicity holds by construction: more loss → ΔF ↑, f ↓, CN ↑, Q ↑, U ↑ (non-decreasing).

### 6.10 `flood` (FR-R1–R5)
- **Events**: `reference/flood_events.csv` (event_id, start, end, peak, sources, S1 scene dates,
  usable, split).
- **Labels**: a cell is flooded if its S1 flooded fraction is ≥ 0.5. Agreement with EMS/GFD is
  reported where available. Permanent water is masked. An equal number of non-flooded valid cells is
  sampled (seeded), with a per-event cap (default 50 k per class).
- **Dataset**: rows are (event, cell, label, static features, coupling features for the paired
  forest year), stored in `data/interim/flood_samples.parquet`.
- **Features (13)**: elevation, slope, twi, hand, dist_river, hsg, rain_mean_annual, rain_p10y_1d,
  f, dF, U, CN, Q.
- **Model**: XGBoost `binary:logistic`, seeded. Monotone signs: dF +1, U +1, CN +1, Q +1, f −1,
  others 0. Saved to `data/models/<model_id>/` as model.json, features.json, metrics.json and a
  config snapshot (FR-R1).
- **Splits**: temporal (train ≤ 2021, test ≥ 2022; adjusted only if the inventory forces it, with
  the change logged) and spatial block CV (10 km blocks, GroupKFold).
- **Baseline**: HAND < 5 m as a binary classifier; continuous −HAND AUC also reported.
- **Ablation (FR-R3)**: retrain without C1–C3; ΔAUC with a 1,000-sample bootstrap 95% CI;
  permutation importance on the test set.
- **Prediction (FR-R2)**: S for every year on the full grid (tiled) and `riskclass` from breaks
  (OI-7). ΔS = S(t) − S(t₀), with t₀ coupling features (f(t₀), ΔF = 0, U = 0, CN(t₀), Q(t₀)).
  Supplying the same forest map for both years gives ΔS = 0 (FR-C3).
- **Sub-basin table**: Appendix C Table 25 fields; risk class per D-19.
- **FR-R4 (Tier 2)**: daily rainfall R per sub-basin → exceedance ratio R / threshold combined with
  the sub-basin's high/very-high area share → risk class. Rules are calibrated on training
  event-days and validated on held-out event-days.
- **FR-R5 (Tier 2)**: a scenario (sub-basin, +X%) reduces f by X% of the remaining forest uniformly
  in that sub-basin. It recomputes ΔF, CN and Q there, recomputes U globally (seconds), predicts for
  the sub-basin plus everything downstream, and returns a ΔS map within 5 minutes.

### 6.11 `validation`
- **Forest (SRS 7.3)**: `reference/forest_sample_points.csv` — seeded stratified sample, ≥ 600
  points, ≥ 150 in loss. `reference/forest_labels.csv` holds interpreter A, B and adjudicated labels.
  Metrics: OA; per-class F1; user's and producer's accuracy; area-adjusted loss estimate with 95% CI
  (Olofsson stratified estimators); Cohen's κ; Hansen comparison.
- **Flood (SRS 7.4)**: test-event AUC; share of flooded test cells in classes 4–5 and those classes'
  area share; HAND baseline; ablation; permutation importance; block-CV AUC mean ± sd.
- **Alerts (SRS 7.5)**: sub-basin-day labels; POD and FAR.
- `daiff validate -c cfg --what forest|flood|alerts` writes `metrics/*.json` into the run and
  appends a dated entry to `docs/test_log.md`.

### 6.12 `alerts`
- **FR-A1**: flags = sub-basins with risk class 4 or 5 under D-19; exposed in the table, the API and
  the map.
- **FR-A2 (Tier 2)**: the engine polls every 30 min.
  - Observed rainfall: near-real-time GPM IMERG via GEE. Forecast: NOAA GFS 0.25° via GEE.
    Dataset IDs are pinned in P5.
  - Thresholds: 99th percentile of wet-day (≥ 1 mm) CHIRPS daily rainfall per sub-basin (OI-8).
  - Alerts are stored in `data/alerts.sqlite`, shown in the dashboard, and e-mailed over SMTP+TLS
    when `SMTP_*` is set; otherwise they go to `data/outbox/`.
  - `daiff alerts replay --event <id>` measures the delay from data availability to alert
    (target ≤ 1 h).

### 6.13 `api` (FastAPI)
Reads only the run named in `data/store/CURRENT`, plus `reference/` and `data/alerts.sqlite`.

| Method | Path | Purpose | Requirement |
|---|---|---|---|
| GET | `/api/meta` | run id, years, t₀, layers, legends, displayed model metrics | NFR-8 |
| GET | `/api/tiles/{layer}/{year}/{z}/{x}/{y}.png` | tiles from COGs (`preview`, `forest`, `loss`, `susceptibility`, `riskclass`, `delta_s`) | FR-V1, NFR-5 |
| GET | `/api/subbasins?year=` | GeoJSON with Table 25 attributes and names | FR-V2, NFR-6 |
| GET | `/api/subbasins/{year}.csv` | the pipeline CSV, streamed unmodified | FR-V2 |
| GET | `/api/export/{layer}/{year}.tif` | COG download | FR-V2 |
| GET | `/api/point?lon=&lat=&year=` | forest-fraction series, S, class, ΔS, top-3 features (XGBoost TreeSHAP `pred_contribs`) | FR-V3 |
| GET | `/api/flags` | flagged sub-basins | FR-A1 |
| GET | `/api/alerts` | active and past alerts | FR-A2 |
| POST | `/api/scenarios` | what-if run, returns ΔS layer id | FR-R5 |
| GET | `/api/metrics` | validation reports | UC-10, NFR-8 |
| GET/POST | `/api/labelling/*` | sample points, submit labels, agreement | SRS 7.3 |

Tiles use rio-tiler `Reader` with server-side colormaps and an in-process LRU cache. The built
frontend is served as static files in production mode.

### 6.14 `web`
- **Pages**: Map, Sub-basins, Alerts, Validation, Labelling. The Map page also hosts the Tier 2
  scenario panel.
- **Map page**: layer switcher, year selector, legend, sub-basin outlines with flags, click panel
  with a forest-fraction chart, S, class, ΔS and top-3 features.
- **Banner** on every map view: "Experimental decision support — not an official flood warning",
  plus the displayed model's validation metric (NFR-8).
- **Sub-basin search** by name (NFR-6).
- **Basemaps**: OSM/CARTO with attribution; Esri World Imagery only on the Labelling page.
- **Libraries**: MapLibre GL, TanStack Table (sortable), Recharts, Vitest.

### 6.15 `research` (Tier 3, Colab)
- **FR-R6**: S1 VV/VH temporal statistics stacked with S2 features (and a small fusion CNN variant)
  for forest classification in cloud-gap months. Compared with the Tier 1 classifier on the same
  reference sample; results table includes GPU hours.
- **FR-A3**: a spatio-temporal transformer forecasting inundation probability 1–7 days ahead at
  sub-basin / 1 km scale. Inputs are sequences of CHIRPS/GFS rainfall, static features and recent S1
  flooded fraction. Baselines are persistence and climatology; skill is reported per lead time.
- **Notebooks** `pip install "daiff @ git+https://github.com/SamarthKale/DAIFF-Flood-Risk-Prediction@<commit>"`
  (pinned to a commit), mount Drive, and call `daiff.research`. They checkpoint to Drive to survive Colab disconnects.

### 6.16 `synthetic`
`make_basin(seed, size=200)` writes raw inputs in exactly the layout the GEE stage produces:
- DEM with a valley and channel
- 10 m forest maps for 6 years with progressive clearing
- HSG and DW classes
- CHIRPS-like daily rainfall
- flood events drawn from a known logistic process of HAND, U and Q
- D8-watershed sub-basins

`configs/synthetic.yaml` runs every local stage end to end without GEE in under 2 minutes. CI, demos
and API/web development use it.

## 7. Data sources

| Dataset | Access | Use | Licence |
|---|---|---|---|
| Sentinel-2 L2A | GEE `COPERNICUS/S2_SR_HARMONIZED` | Forest classification | Copernicus open licence |
| Sentinel-1 GRD | GEE `COPERNICUS/S1_GRD` | Flood labels; Tier 3 | Copernicus open licence |
| SRTM 1″ | GEE `USGS/SRTMGL1_003` | Terrain | Public domain |
| Hansen GFC | GEE `UMD/hansen/global_forest_change_*` (pinned) | Loss reference, training labels | CC BY 4.0 |
| JRC Global Surface Water | GEE `JRC/GSW1_4/GlobalSurfaceWater` | Permanent-water mask | Copernicus open licence |
| Global Flood Database | GEE `GLOBAL_FLOOD_DB/MODIS_EVENTS/V1` | Label check, events | CC BY-NC 4.0 |
| CHIRPS daily | GEE `UCSB-CHG/CHIRPS/DAILY` | Climatology, design rainfall, thresholds | CC0 |
| NOAA CPC Global Unified | NOAA PSL HTTPS (NetCDF) | Rainfall ingest (FR-D3), cross-check | Public domain |
| Dynamic World | GEE `GOOGLE/DYNAMICWORLD/V1` | Training-label filter, non-forest class for CN | CC BY 4.0 |
| ESA WorldCover | GEE `ESA/WorldCover/v200` | Cross-check | CC BY 4.0 |
| HydroBASINS | GEE `WWF/HydroSHEDS/v1/Basins/hybas_*` | AOI and sub-basins | HydroSHEDS licence (free, attribution) |
| HYSOGs250m | ORNL DAAC / community GEE asset (pinned in P3) | Hydrologic soil group | Open, attribution |
| OpenStreetMap waterways | Overpass API | FR-D4 stream check, sub-basin names | ODbL |
| DFO, ReliefWeb, ASDMA reports, Copernicus EMS, NRSC Bhuvan | Web (manual) | Flood-event inventory, test labels | Public reports |
| GPM IMERG; NOAA GFS 0.25° | GEE (pinned in P5) | Tier 2 observed / forecast rainfall | Public domain |

EM-DAT requires an account. The inventory starts from DFO, ReliefWeb and ASDMA, and EM-DAT is used
only if a teammate registers. All licences are listed in `docs/LICENSES.md` (NFR-7).

## 8. Testing and verification strategy

- TDD for library code. pytest markers: `gee` (live Earth Engine, skipped by default), `slow`,
  `colab`.
- Tests are named after requirements, e.g. `test_fr_c1_upstream_loss_matches_hand_computed`.
  `docs/verification_matrix.md` maps every requirement to its test or script and status.

| Requirement | Verification artifact |
|---|---|
| FR-C1 | Unit test: hand-computed C1/C2/C3 on a 10 × 10 grid with known D8 paths |
| FR-C3 | Unit + synthetic test: identical forest maps → max \|ΔS\| ≤ 1e-6 |
| FR-C4 | Synthetic test: remove forest in 100 upstream cells → no downstream S decreases; outlet S rises. Plus a property test on monotone constraints |
| FR-D5 | Unit test of `check_alignment` + `daiff check-grid` on every run |
| FR-F3 | Unit test: table totals = loss-pixel sum (≤ 0.5%) |
| FR-F4 | Unit test: no remaining patch < 50 px |
| FR-R1 | Synthetic end-to-end training from config (demonstration on Kopili in P4) |
| FR-A1 | Unit test: flags equal classes 4–5 of the risk map |
| FR-V2, FR-V3 | API tests: CSV byte-equal to the pipeline; point values equal raster values at 10 random points |
| NFR-3 | CI: two synthetic runs → identical SHA-256 per raster |
| NFR-4 | `daiff check-metadata` on every run |
| NFR-9 | CI: tests + coverage report (coupling ≥ 80%) |
| NFR-10 | CI: gitleaks |
| NFR-1, NFR-2 | `daiff bench` → `docs/perf/` |
| FR-F1, F2, R2, R3, R4 | `daiff validate` → metrics JSON + `docs/test_log.md` |
| FR-D1, D2, D3, D4 | Inventory, gap and stream-check reports from P3 stages |

CI (GitHub Actions, ubuntu-latest): `uv sync`, ruff, `pytest -m "not gee and not slow"` with
coverage, the synthetic end-to-end run twice (NFR-3), gitleaks, then `npm ci && npm test &&
npm run build` in `web/`. CI is informative only. Nobody waits for it or stops work because it is
red (D-07).

## 9. Output store

`data/store/<run_id>/` contains every Appendix C file under its exact name, plus:
`forest10m_<year>.tif`, `loss10m_<t0>_<year>.tif`, `regrowth_<t0>_<year>.tif`, `cn_<year>.tif`,
`static_features.tif`, `preview_<year>.tif`, `subbasins.geojson`, `metrics/*.json` and `model_id.txt`.
`data/store/CURRENT` names the published run.

## 10. Handoff and workflow

`CLAUDE.md` holds the binding session protocol. Summary:
- Start: pull, then read CLAUDE.md, `docs/STATUS.md` and the active plan.
- Each task: one test-first cycle and one commit, with `wip:` commits if a session might end
  mid-task.
- End of each task: tick the plan checkbox, update STATUS, push to `main`.
- No AI co-author trailers; never wait on CI; secrets only in `.env`; `data/` never committed;
  small irreplaceable data in `reference/`.

## 11. Build phases

Each phase gets its own plan in `docs/superpowers/plans/`, written when the phase starts.

| Phase | Scope | Needs GEE | Exit gate |
|---|---|---|---|
| P0 Bootstrap | Repo hygiene, env, CI, config, grid + FR-D5, store + provenance, stage runner, synthetic basin skeleton, `docs/setup/gee.md`, verification matrix, test log | No | `daiff check-grid` and `check-metadata` work on synthetic outputs; CI file runs |
| P1 Science core | Terrain, forest loss/MMU/stats, coupling C1–C3, flood model + classes + ΔS + baseline + ablation + block CV, tables, FR-A1, `run`/`watch` — all on synthetic | No | FR-C1–C4, FR-F3, FR-F4, FR-A1, NFR-3, NFR-4 tests pass; synthetic end-to-end < 2 min |
| P2 API + dashboard | FastAPI endpoints, React app: Map, Sub-basins, Validation, Labelling; exports; banner | No | FR-V2/V3 API tests pass; walkthrough on synthetic data |
| P3 Kopili ingestion | AOI, sub-basins + names, S2 composites + RF, S1 flood maps, reference layers, rainfall, rivers, event inventory | Yes | FR-D1–D5 acceptance met for Kopili |
| P4 Tier 1 acceptance | Real runs, reference sample + labelling, forest + flood validation, U-Net challenger, NFR checks, test log | Yes (+ Colab) | Every Tier 1 criterion recorded as passed or justified in `docs/test_log.md` |
| P5 Tier 2 | FR-F5, FR-R4, FR-R5, FR-A2, alert validation | Yes | Table 16 Tier 2 targets evaluated and reported |
| P6 Tier 3 | FR-R6, FR-A3 on Colab | Yes (+ Colab) | Results tables with compute cost |
| P7 Close-out | Verification matrix, docs, handover, demo script | — | Guide review package ready |

## 12. Work that only humans can do

Tracked in `docs/STATUS.md` → "Waiting on humans". It is never simulated as done.
- ~~Create the public GitHub repo~~ — done: `SamarthKale/DAIFF-Flood-Risk-Prediction`.
- Every teammate registers a free non-commercial Earth Engine project (`docs/setup/gee.md`).
- Label the 600 reference points: two interpreters plus an adjudicator, using the Labelling page.
- The guide confirms OI-4 (HPC) and OI-10 (targets) and witnesses the FR-C2, FR-R1 and FR-V1 demos.
- Five non-team testers for NFR-6.
- Optional: a Gmail app password for e-mail alerts (otherwise alerts go to the outbox folder).

## 13. Risks and SRS deviations

| Item | Type | Handling |
|---|---|---|
| S2 L2A sparse over Assam before ~Dec 2018 | Risk → possible deviation | D-24: t₀ = 2019 if coverage < 90% |
| Few training events before 2022 for the temporal split | Risk | Inventory in P3; split adjusted only with a logged decision; block CV always reported |
| Weak forest–flood signal in the historical record | Risk (SRS 3.5) | C3 keeps a physical channel; ablation reported with CI regardless |
| Colab free-tier GPU limits and disconnects | Risk | Small models, Drive checkpoints, one year at a time |
| Drive 15 GB free quota | Risk | Only Colab artefacts go to Drive; deleted after import |
| GEE non-commercial quota or policy change | Risk | Exports are small and cached locally; raw layers recorded with versions |
| HYSOGs instead of raw SoilGrids | Deviation | D-12, logged |
| CHIRPS for design rainfall | Deviation (permitted by SRS 2.8) | D-16, logged; CPC still ingested |
| Python 3.12 / laptop instead of HPC for now | Deviation (temporary) | D-05, D-13; SLURM scripts provided |
| EM-DAT not used unless a teammate registers | Deviation | DFO + ReliefWeb + ASDMA cover the inventory |
