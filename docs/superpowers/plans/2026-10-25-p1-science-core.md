# P1 Science Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Checkbox steps. Follow CLAUDE.md's session protocol: tick, update STATUS, commit (no AI trailer), push after every task.

**Goal:** Every local science stage — terrain, forest loss, coupling C1–C3, flood model, ΔS, sub-basin
tables, FR-A1 flags — runs end to end on the synthetic basin through `daiff run`, with `daiff watch`
(FR-C2) and `daiff validate`.

**Architecture:** Pure functions on numpy arrays (numba for grid-global algorithms), wrapped as
pipeline `Stage`s that read `RawLayout` and write a `RunStore`. Only `coupling` reads forest outputs
on behalf of the flood model.

**Tech Stack:** numba, scipy, scikit-learn, xgboost, pandas/pyarrow, dask[distributed], rasterio.

**Spec:** `docs/superpowers/specs/2026-10-25-daiff-system-design.md` §6.4, 6.7–6.12, 6.16, 8, 11.
**Depends on:** P0 (config, grid, store, RawLayout, runner, synthetic).

## Global Constraints

- D8 codes, ESRI: E=1, SE=2, S=4, SW=8, W=16, NW=32, N=64, NE=128; 0 = outlet/sink (flows off grid).
- Cell area 900 m² (30 m). MMU 0.5 ha = 50 px at 10 m, 8-connectivity.
- Feature order (exact, 13): `elevation, slope, twi, hand, dist_river, hsg, rain_mean_annual, rain_p10y_1d, f, dF, U, CN, Q`.
- Monotone constraints: `dF:+1, U:+1, CN:+1, Q:+1, f:-1`, others 0. Coupling features = `f, dF, U, CN, Q`.
- Risk breaks `[0.2, 0.4, 0.6, 0.8]` → classes 1–5 (`np.digitize(S, breaks) + 1`); NaN S → class 255.
- Sub-basin risk class = class of `mean_s` (D-19); flag = class ≥ 4.
- HAND baseline: susceptible ⇔ HAND < 5 m.
- Spatial CV block = 10 km; temporal split: train events ≤ `flood.train_until` (default 2021).
- Design rainfall: Gumbel method of moments, T = 10 y: `P = mean + K·std`, `K = −(√6/π)(0.5772 + ln(ln(T/(T−1))))` (K₁₀ ≈ 1.3046).
- DW → TR-55 cover: trees→woods, grass→pasture, shrub_and_scrub→pasture, flooded_vegetation→pasture,
  crops→row_crops, bare→fallow, snow_and_ice→fallow, built→impervious, water→excluded (NaN).
- CN table = SRS Appendix B (woods 30/55/70/77, pasture 39/61/74/80, row_crops 67/78/85/89, fallow 77/86/91/94, impervious 98).

## Review Focus

1. **Flat or pitted terrain** — depressions and flats must still drain (fill + epsilon) so every cell reaches an outlet; pinned in Task 2 (`test_every_cell_reaches_outlet_after_fill`).
2. **Nodata forest cells (cloud gaps)** — NaN ΔF must be excluded from both U sums, never treated as 0 loss or crash; pinned in Task 5.
3. **Sub-basin with no valid cells / all-NaN S** — table row must still appear with NaN stats and `risk_flag = no`; pinned in Task 9.
4. **Re-running with an identical forest map** — ΔS exactly 0 (FR-C3); pinned in Task 8.
5. **Class imbalance / a single-class event** — sampling must not crash when an event has fewer flooded cells than the cap; pinned in Task 7.

---

### Task 1: Dependencies, config sections, Dask runtime

**Files:** Modify `pyproject.toml`, `src/daiff/config.py`, `configs/*.yaml`. Create `src/daiff/runtime.py`, `tests/test_runtime.py`, `hpc/slurm/daiff_run.sbatch`, `hpc/slurm/README.md`.

**Interfaces — Produces:**
- deps: `numba>=0.60`, `scipy>=1.13`, `scikit-learn>=1.5`, `xgboost>=2.1`, `pyarrow>=16`, `dask[distributed]>=2024.8`; extra `hpc = ["dask-jobqueue>=0.9"]`.
- Config sections (pydantic, forbid extra, all with defaults so P0 YAMLs stay valid):
  `ForestConfig(mmu_ha=0.5)`, `TerrainConfig(stream_threshold_km2=1.0, major_stream_km2=50.0)`,
  `CouplingConfig(return_period_years=10, dual_hsg="D")`,
  `FloodConfig(sample_cap_per_class=50000, train_until=2021, block_size_m=10000, class_breaks=[0.2,0.4,0.6,0.8], n_estimators=400, max_depth=6, learning_rate=0.05, flooded_fraction_threshold=0.5)`,
  `RuntimeConfig(seed=42, cluster="local", n_workers=2, threads_per_worker=2, tile_size=1024)`.
- `make_client(rt: RuntimeConfig) -> distributed.Client` — `LocalCluster` for `"local"`; `"slurm"` imports `dask_jobqueue.SLURMCluster` lazily (ImportError message: "install with `uv sync --extra hpc`").

- [x] Test `test_make_client_local_runs_task`: client with 1 worker computes `client.submit(sum, [1, 2]).result() == 3`; `test_slurm_without_extra_gives_install_hint` (monkeypatch import to fail → `ImportError` matching `"--extra hpc"`). Config test: synthetic config exposes `cfg.flood.class_breaks == [0.2, 0.4, 0.6, 0.8]`.
- [x] Implement; sbatch template runs `uv run daiff run -c $CONFIG` with `--cpus-per-task`, `--mem`, `--time` placeholders documented in `hpc/slurm/README.md`.
- [x] `uv sync --extra dev`, full test suite, ruff. Commit `feat(runtime): science deps, config sections, dask client`. Push.

### Task 2: Terrain — fill, D8, topological order, accumulation

**Files:** Create `src/daiff/terrain/__init__.py`, `src/daiff/terrain/flow.py`; Test `tests/terrain/test_flow.py`.

**Interfaces — Produces** (all numba-jitted cores behind typed wrappers; arrays `(h, w)`):
- `fill_depressions(dem: np.ndarray, epsilon: float = 1e-4) -> np.ndarray` — priority-flood + epsilon (Barnes et al. 2014); NaN cells are nodata and act as outlets' neighbours (edge-like).
- `d8_directions(filled: np.ndarray, res: float) -> np.ndarray[uint8]` — steepest drop / distance (diagonal distance res·√2); edge cells with no lower in-grid neighbour → 0.
- `downstream_index(dirs) -> np.ndarray[int64]` flat index of receiver, −1 for outlets.
- `topological_order(dirs) -> np.ndarray[int64]` — upstream-first (Kahn on receiver graph).
- `accumulate(dirs, weights: np.ndarray, order=None) -> np.ndarray[float64]` — sum of `weights` over each cell and all its upstream cells (NaN weights count as 0).

- [x] Tests:
  - `test_d8_codes_on_plane_tilted_east`: dem = `-x` 5×5 → interior & non-east-edge cells all `1`; east edge `0`.
  - `test_d8_prefers_steepest_including_diagonal`: 3×3 with centre 10, SE corner 0, others 9.5 → centre code `2`.
  - `test_fill_raises_pit_to_spill_level`: 5×5 bowl with centre pit 1, rim 5, one rim gap at 3 → filled centre ≥ 3 and every interior cell > its receiver.
  - `test_every_cell_reaches_outlet_after_fill` (Review 1): random 50×50 dem with pits and a flat plateau → following `downstream_index` from any cell terminates at an outlet within h·w steps.
  - `test_accumulate_counts_upstream_cells`: east-tilted 3×4 plane, weights 1 → row values `[1, 2, 3, 4]`.
- [x] Implement (heap of `(elev, idx)` with numba typed list + heapq).
- [x] Tests + ruff; commit `feat(terrain): priority-flood fill, D8 and flow accumulation`; push.

### Task 3: Terrain — slope, TWI, streams, HAND, distance; static stage

**Files:** Create `src/daiff/terrain/derive.py`, `src/daiff/terrain/stage.py`; Test `tests/terrain/test_derive.py`.

**Interfaces — Produces:**
- `slope_degrees(dem, res) -> np.ndarray` (Horn 3×3; edges by replication).
- `twi(acc_cells, slope_deg, res) -> np.ndarray` — `ln((acc·res²/res) / max(tan β, 0.001))`.
- `streams(acc_cells, cell_area_m2, threshold_km2) -> np.ndarray[bool]`.
- `hand(filled, dirs, stream_mask, order) -> np.ndarray` — process cells downstream-first (reverse of `order`): `ref[c] = z[c]` if stream else `ref[receiver(c)]`; cells whose path never meets a stream get NaN. `HAND = dem − ref` (use original dem, clip ≥ 0).
- `distance_to_stream(stream_mask, res) -> np.ndarray` (scipy `distance_transform_edt` × res).
- `STATIC_BANDS = ("elevation", "slope", "twi", "hand", "dist_river", "hsg")`; `build_static_features(raw: RawLayout, grid: Grid, cfg) -> dict[str, np.ndarray]` also returns `dirs`, `order`, `streams` for later stages.
- Stage `terrain` (outputs `RunStore.static_features` multiband with `STATIC_BANDS` + `data_root/interim/d8.tif` (uint8) + `interim/streams.tif`).

- [x] Tests: `test_slope_of_plane` (dz/dx = 0.1 on 30 m → 5.71°±0.01); `test_hand_zero_on_streams_and_height_above_downstream_stream` (east-tilted plane with stream at east column: HAND = elevation − elevation of that row's stream cell); `test_hand_nan_when_no_stream_downstream`; `test_distance_to_stream_in_metres` (single stream column → distances 0, 30, 60); `test_twi_increases_with_accumulation`.
- [x] Implement; commit `feat(terrain): slope, TWI, streams, HAND, distance and static stage`; push.

### Task 4: Forest — fraction, loss with MMU, regrowth, sub-basin raster and stats

**Files:** Create `src/daiff/forest/__init__.py`, `src/daiff/forest/change.py`, `src/daiff/zones.py`; Test `tests/forest/test_change.py`, `tests/test_zones.py`.

**Interfaces — Produces:**
- `forest_fraction(forest10m: np.ndarray[uint8]) -> np.ndarray[float32]` — 3×3 block mean over valid (≠255) pixels; NaN if none valid.
- `loss_mask(f_y1: uint8, f_y2: uint8, mmu_px: int) -> np.ndarray[uint8]` — 1 where forest→non-forest (both valid), 8-connected components < `mmu_px` removed (scipy `ndimage.label` with 3×3 ones); 255 where either invalid.
- `regrowth_mask(f_y1, f_y2) -> uint8` (non-forest→forest, no MMU).
- `block_fraction(mask10m: uint8) -> float32` — same aggregation as `forest_fraction` (ΔF per D-20).
- `rasterize_subbasins(geojson_path: Path, grid: Grid) -> tuple[np.ndarray[int32], pd.DataFrame]` — ids raster (0 = outside) via `rasterio.features.rasterize` after `transform_geom` to grid CRS; frame `subbasin_id, name`.
- `zonal_sum(values, zones) -> pd.Series`, `zonal_mean(values, zones) -> pd.Series` (NaN-aware, index = subbasin_id, every id present).
- `loss_hectares_by_subbasin(loss10m: uint8, zones30: int32) -> pd.Series` — loss px count × 0.01 (zones upsampled ×3 with `np.repeat`).
- `hansen_comparison(ours_ha: float, hansen_ha: float) -> dict` (`diff_pct`, `within_25pct`).
- Stage `forest` per year: `forest_<y>.tif`, `loss10m_<t0>_<y>.tif`, `loss_<t0>_<y>.tif`, `regrowth_<t0>_<y>.tif`, copy `forest10m_<y>.tif` into the run.

- [x] Tests: `test_forest_fraction_ignores_nodata` (block with 3 forest, 3 non-forest, 3×255 → 0.5; all 255 → NaN); `test_fr_f4_loss_patches_below_mmu_removed` (one 8×8 patch=64 px kept, one 7×7=49 px removed, diagonal-touching pixels count as connected); `test_fr_f3_hectares_equal_loss_pixel_sum` (sum of per-subbasin ha == mask.sum()·0.01 within 0.5% — exact); `test_rasterize_subbasins_synthetic_quadrants` (4 ids, each 100×100 cells); `test_zonal_mean_keeps_empty_zone_as_nan`.
- [x] Implement; commit `feat(forest): forest fraction, MMU-filtered loss and sub-basin stats`; push.

### Task 5: Coupling C1–C3 (FR-C1)

**Files:** Create `src/daiff/coupling/__init__.py`, `src/daiff/coupling/features.py`, `src/daiff/coupling/rainfall.py`, `src/daiff/coupling/stage.py`; Test `tests/coupling/test_features.py`.

**Interfaces — Produces:**
- `upstream_loss(dF: np.ndarray, dirs, cell_area: float, order=None) -> np.ndarray` — `accumulate(area·dF_valid)/accumulate(area·valid)`; NaN dF excluded from both (D-21: includes self).
- `CN_TABLE: dict[str, tuple[int,int,int,int]]`, `DW_TO_TR55: dict[int, str | None]`.
- `curve_number(f: np.ndarray, dw_class: np.ndarray[uint8], hsg: np.ndarray[uint8]) -> np.ndarray` — D-22: `f·CN_woods[hsg] + (1−f)·CN[DW_TO_TR55[class]][hsg]`; water/nodata → NaN; dual HSG already mapped to D upstream.
- `scs_runoff(cn, p_mm) -> np.ndarray` — Eqs. (2)(3).
- `gumbel_design_rainfall(annual_max: np.ndarray, T: int = 10) -> float`.
- `design_rainfall_by_subbasin(daily: pd.DataFrame, T: int) -> pd.Series` (annual max per calendar year per sub-basin, then Gumbel); `mean_annual_rainfall(daily) -> pd.Series`.
- `coupling_features(f, f_t0, loss_frac, dw_class, hsg, dirs, order, p_mm_raster, cell_area) -> dict[str, np.ndarray]` with keys `f, dF, U, CN, Q` (dF = loss_frac).
- Stage `coupling` per year: `coupling_<y>.tif` (bands `f, dF, U, Q`), `cn_<y>.tif`; static rain bands `rain_mean_annual`, `rain_p10y_1d` written to `interim/rain_features.tif`.

- [x] Tests (`test_fr_c1_*`):
  - `test_fr_c1_upstream_loss_matches_hand_computed`: 10×10 east-tilted plane (all codes 1); row 0 dF = `[0.0, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]` → U row 0 = `[0, 0.5, 0.5, 0.375, 0.3, 0.25, 0.2142857, 0.1875, 0.1666667, 0.25]` (abs 1e-9); other rows dF=0 → U=0.
  - `test_fr_c1_nan_loss_excluded` (Review 2): row `[nan, 1.0, 0.0]` → U = `[nan-or-any, 1.0, 0.5]` — cell 0's own U is NaN, cells 1–2 ignore it.
  - `test_fr_c1_curve_number_and_runoff_hand_computed` (P = 100 mm, HSG B): f=1 → CN 55, Q 12.8253; f=0 & crops → CN 78, Q 46.657; f=0.5 & crops → CN 66.5, Q 27.360 (abs 1e-3); water → NaN; `P ≤ 0.2S` → Q 0.
  - `test_gumbel_design_rainfall_k10`: maxima with mean 100, sample std 20 → 126.09 (abs 0.01).
  - `test_coupling_monotone_in_loss`: increasing loss_frac in one upstream cell never decreases dF, U, CN, Q anywhere.
- [x] Implement; add CI coverage gate later (Task 10). Commit `feat(coupling): C1 local loss, C2 upstream loss, C3 curve number and runoff`; push.

### Task 6: Synthetic flood events

**Files:** Modify `src/daiff/store/raw_layout.py`, `src/daiff/synthetic.py`; Test `tests/integration/test_synthetic_floods.py`.

**Interfaces — Produces:**
- `RawLayout.flood_events_csv` (`raw/flood_events.csv`: `event_id,start,end,peak,year,sources,usable,split`), `RawLayout.flood_fraction(event_id)` (`raw/floods/flood_<event_id>.tif`, float32 0–1 at 30 m).
- `make_flood_events(cfg, raw) -> list[str]` (called at the end of `make_basin`): one event per configured year after t₀ (5 events for synthetic, ids `syn_<year>`), peak in August of that year; flooded fraction = sigmoid(`2.5 − 0.6·HAND + 6·U + 0.03·Q + N(0,0.5)`) thresholded at 0.5 → 1.0 else 0.0, permanent water (jrc > 90) NaN. Uses terrain + coupling functions with the forest map of that year. `split = "train"` if year ≤ `flood.train_until` else `"test"`.

- [ ] Tests: CSV has 5 events, splits = 2 train (2020, 2021) + 3 test; each mask has both classes with ≥ 1% flooded; flooded share is higher in cells with HAND < 5 than HAND ≥ 5; deterministic per seed.
- [ ] Commit `feat(synthetic): flood events driven by HAND and upstream loss`; push.

### Task 7: Flood dataset, model training, baseline, ablation (FR-R1, FR-R3)

**Files:** Create `src/daiff/flood/__init__.py`, `src/daiff/flood/dataset.py`, `src/daiff/flood/model.py`, `src/daiff/flood/evaluate.py`; Test `tests/flood/test_dataset.py`, `tests/flood/test_model.py`.

**Interfaces — Produces:**
- `FEATURES: tuple[str, ...]` (13, Global Constraints order); `COUPLING_FEATURES = ("f", "dF", "U", "CN", "Q")`; `MONOTONE = {"dF": 1, "U": 1, "CN": 1, "Q": 1, "f": -1}`.
- `sample_event(flooded: np.ndarray, valid: np.ndarray, cap: int, rng) -> tuple[np.ndarray, np.ndarray]` — flat indices of positives (≤ cap) and equal-count negatives; empty arrays if no positives (Review 5).
- `build_dataset(events: pd.DataFrame, feature_stack: Callable[[int], dict[str, np.ndarray]], flood_masks: Callable[[str], np.ndarray], grid: Grid, cfg) -> pd.DataFrame` — columns `event_id, split, cell, x, y, block, label, *FEATURES`; `block = f"{int(x // bs)}_{int(y // bs)}"`.
- `train_model(df, features=FEATURES, cfg) -> xgboost.XGBClassifier` (monotone constraints tuple in feature order, `random_state=seed`, `tree_method="hist"`, `n_jobs=1` for determinism).
- `save_model(model, features, metrics, cfg, out_dir) -> str` (model_id = 12-hex of model.json bytes); `load_model(model_dir) -> tuple[XGBClassifier, list[str]]`.
- `evaluate(model, df_test, features) -> dict` (`auc`, `hand_baseline_auc_binary`, `hand_baseline_auc_continuous`, `share_flooded_in_high`, n).
- `spatial_block_cv(df, cfg, k=5) -> dict` (GroupKFold on `block`, mean/sd AUC).
- `ablation(df_train, df_test, cfg, n_boot=1000) -> dict` (`auc_full`, `auc_no_coupling`, `delta`, `ci95: [lo, hi]` paired bootstrap on test rows).
- `permutation_importance_table(model, df_test, features) -> pd.DataFrame` (sklearn, seeded).
- Stage `train` (on demand, `daiff train` / first `run`): writes `data_root/models/<model_id>/{model.json, features.json, metrics.json, config.yaml}`; `RunStore.model_id_file`.

- [ ] Tests: `test_sample_event_balances_and_respects_cap`; `test_sample_event_with_no_positives_returns_empty` (Review 5); `test_fr_r1_train_from_config_saves_model_features_metrics` (synthetic dataset → files exist, features.json == FEATURES); `test_model_beats_hand_baseline_on_synthetic` (AUC > baseline); `test_fr_r3_ablation_reports_ci` (keys present, lo ≤ delta ≤ hi); `test_training_is_deterministic` (two trainings → identical model.json bytes).
- [ ] Commit `feat(flood): dataset, monotone XGBoost, baseline, block CV and ablation`; push.

### Task 8: Prediction, risk classes, ΔS (FR-R2, FR-C3, FR-C4)

**Files:** Create `src/daiff/flood/predict.py`; Test `tests/flood/test_predict.py`.

**Interfaces — Produces:**
- `assemble_features(static: dict, rain: dict, coupling: dict) -> np.ndarray` shape `(n_cells, 13)` in FEATURES order + `valid` mask.
- `predict_grid(model, stack: np.ndarray, valid, shape, tile_rows: int = 256) -> np.ndarray[float32]` (NaN invalid; row tiles; optional dask client).
- `risk_classes(S, breaks) -> np.ndarray[uint8]`.
- `baseline_coupling(f_t0, cn_t0, q_t0) -> dict` (f=f_t0, dF=0, U=0, CN=cn_t0, Q=q_t0); `delta_s(S_t, S_t0) -> np.ndarray`.
- Stage `predict` per year: `susceptibility_<y>.tif`, `riskclass_<y>.tif`, `delta_s_<y>.tif`.

- [ ] Tests: `test_fr_c3_same_forest_map_gives_zero_delta_s` (|ΔS| ≤ 1e-6 everywhere — Review 4); `test_fr_c4_removing_upstream_forest_never_lowers_s` (synthetic: set forest10m→0 in 100 cells (30 m) upstream of the outlet, recompute coupling+predict: no cell's S decreases (tol 1e-7), outlet S increases); `test_risk_classes_breaks` (`[0.1,0.2,0.39,0.4,0.79,0.8,nan] → [1,2,2,3,4,5,255]`); `test_predict_matches_model_predict_proba` on 100 random cells.
- [ ] Commit `feat(flood): grid prediction, risk classes and delta-S`; push.

### Task 9: Sub-basin table and FR-A1 flags

**Files:** Create `src/daiff/flood/tables.py`, `src/daiff/alerts/__init__.py`, `src/daiff/alerts/flags.py`; Test `tests/flood/test_tables.py`, `tests/alerts/test_flags.py`.

**Interfaces — Produces:**
- `TABLE_COLUMNS = ["subbasin_id", "name", "area_km2", "forest_loss_ha", "forest_fraction", "mean_s", "mean_delta_s", "area_class_1", …, "area_class_5", "area_moved_up_km2", "risk_class", "risk_flag"]` (Table 25 + `name`, `risk_class`).
- `subbasin_table(zones, names: pd.DataFrame, loss_ha: pd.Series, f, S, dS, cls_t, cls_t0, breaks, cell_area) -> pd.DataFrame` — `risk_flag` "yes"/"no"; floats rounded to 6 dp; sorted by id.
- `flags(table) -> list[int]` (ids with `risk_class >= 4`).
- Stage `tables` per year: `subbasin_<y>.csv` (UTF-8, `\n`, no index).

- [ ] Tests: `test_table_has_table25_columns_and_one_row_per_subbasin`; `test_area_classes_sum_to_area`; `test_empty_subbasin_row_is_nan_and_not_flagged` (Review 3); `test_fr_a1_flags_match_risk_map` (flag ⇔ class of mean_s ≥ 4 for all rows).
- [ ] Commit `feat(tables): sub-basin table (App. C) and FR-A1 flags`; push.

### Task 10: Pipeline wiring — `daiff run`, `daiff watch`, run metadata, end-to-end

**Files:** Create `src/daiff/pipeline/stages.py`, `src/daiff/pipeline/watch.py`; Modify `src/daiff/cli.py`, `.github/workflows/ci.yml`; Test `tests/integration/test_end_to_end.py`, `tests/integration/test_watch.py`.

**Interfaces — Produces:**
- `build_stages(cfg) -> list[Stage]` order: `terrain → forest → coupling → train → predict → tables → publish`; every output written via `write_cog` with `build_tags` (model_id `"n/a"` before train; forest outputs record `"forest:<classifier>"` from raw tags).
- `run_pipeline(cfg, *, stages=None, years=None, force=False) -> str` — computes `run_id` from config hash + `code_commit(repo root)` + checksums of all raw inputs; runs; writes `run_metadata.json` (all `RUN_METADATA_KEYS`; timings per stage); `publish`; appends timings to `docs/perf/` only when `--log-perf`.
- `watch(cfg, interval_s: float = 30, once: bool = False) -> list[int]` — detects forest10m years not yet in `cfg.years`' last published run → runs `forest → coupling → predict → tables → publish` for them with the existing model (FR-C2), returns processed years.
- CLI: `daiff run -c CFG [--stages a,b] [--years 2020,2021] [--force] [--log-perf]`, `daiff watch -c CFG [--interval 30] [--once]`, `daiff train -c CFG`.
- CI: add `uv run daiff synth -c configs/synthetic.yaml && uv run daiff run -c configs/synthetic.yaml` twice, then a script comparing SHA-256 of all `*.tif` in both runs (NFR-3); `--cov=daiff.coupling --cov-fail-under=80` as a separate step.

- [ ] Tests: `test_end_to_end_synthetic_produces_appendix_c_outputs` (every App. C file for every year; `check_metadata` → []; runtime < 120 s → mark `slow` only if exceeded); `test_nfr_3_rerun_is_byte_identical` (force re-run into a second data root → identical tif hashes); `test_fr_c2_watch_processes_new_forest_map` (publish with years up to 2023, then add `forest10m_2024.tif` via synthetic → `watch(once=True) == [2024]` and `susceptibility_2024.tif`, `delta_s_2024.tif` exist in the newly published run with no manual step).
- [ ] Commit `feat(pipeline): run/watch/train commands and synthetic end-to-end`; push.

### Task 11: Validation module and `daiff validate`

**Files:** Create `src/daiff/validation/__init__.py`, `sampling.py`, `forest_accuracy.py`, `report.py`; Modify `src/daiff/cli.py`; Test `tests/validation/test_*.py`.

**Interfaces — Produces:**
- `stratified_sample(strata: np.ndarray[uint8], n_total=600, min_per_stratum=150, seed) -> pd.DataFrame` — strata codes 1 stable forest, 2 stable non-forest, 3 loss; proportional allocation with floor `min_per_stratum`; columns `point_id, row, col, x, y, lon, lat, stratum`.
- `confusion(map_cls, ref_cls, labels) -> np.ndarray`; `accuracy_report(map_cls, ref_cls, strata_weights) -> dict` — OA, per-class F1, user's/producer's accuracy, Olofsson area-adjusted loss proportion & area with 95% CI.
- `cohens_kappa(a, b) -> float`.
- `write_test_log_entry(path: Path, *, requirement, method, run_ref, result, evidence, by) -> None` (appends a Markdown table row).
- `daiff validate -c CFG --what forest|flood` → `metrics/forest.json` / `metrics/flood.json` in the current run + a test-log row (flood uses Task 7 `evaluate`, `spatial_block_cv`, `ablation`, `permutation_importance_table`). `daiff sample-points -c CFG` writes `reference/forest_sample_points_<project>.csv`.
- [ ] Tests: allocation respects 600/150; kappa of identical = 1, of known 2×2 example = documented value (e.g. a=[1,1,0,0,1,0], b=[1,0,0,0,1,1] → 0.333…); Olofsson example from the paper's Table (pinned numbers: use their 3-class example, area estimate within 1e-3); test-log row appended with correct columns.
- [ ] Commit `feat(validation): forest accuracy (Olofsson), kappa, flood report, validate CLI`; push.

### Task 12: Bench (NFR-1/2) and P1 close-out

**Files:** Create `src/daiff/bench.py`; Modify `src/daiff/cli.py`, `docs/verification_matrix.md`, `docs/STATUS.md`.
- `daiff bench -c CFG --workers 1,2` runs `predict` tiled with each worker count and appends rows to `docs/perf/<date>-<machine>.md`; reports speed-up.
- [ ] Test: bench on synthetic writes a perf file with 2 rows.
- [ ] Update verification matrix (FR-C1/C3/C4, FR-F3/F4, FR-R1/R3 machinery, FR-A1, NFR-3/4 → "passing (synthetic)"); STATUS → P1 done, next = P2 Task 1. Commit `docs: close P1`; push.
