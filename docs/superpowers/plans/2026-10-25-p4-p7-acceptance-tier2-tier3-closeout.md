# P4–P7 Implementation Plans (Tier 1 acceptance, Tier 2, Tier 3, close-out)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. CLAUDE.md protocol applies. These phases depend on real-data findings from P3; **refine each phase's tasks into full test-level steps at the start of the phase** (edit this file, commit, then execute). Interfaces below are binding.

**Spec:** §6.8 (U-Net), §6.10 (FR-R4/R5), §6.11, §6.12 (FR-A2), §6.15, §8, §11–13.

---

## P4 — Tier 1 acceptance on Kopili

**Goal:** every Tier 1 requirement recorded as passed (or justified) in `docs/test_log.md` on Kopili data.

### Task P4.1: Full Kopili run
`daiff run -c configs/kopili.yaml --log-perf` (all years); `daiff check-metadata` (NFR-4); NFR-1 timing row in `docs/perf/`; NFR-2 `daiff bench --workers 2,4`.

### Task P4.2: Reference sample and labelling (human-in-the-loop)
`daiff sample-points -c configs/kopili.yaml` → `reference/forest_sample_points_kopili.csv` (≥ 600, ≥ 150 loss). STATUS "Waiting on humans": interpreters A and B label in the Labelling page, adjudicator resolves; Claude never labels points.

### Task P4.3: U-Net challenger on Colab (D-14)
`src/daiff/forest/unet.py` (PyTorch model def: 4-level U-Net, ~2 M params, input 12 bands, CPU-testable on a 64×64 tensor); `src/daiff/gee/chips.py` (export 256×256 chips + auto-labels to Drive folder `DAIFF/chips/`); `notebooks/colab/unet_train.ipynb`, `unet_infer.ipynb` (pip install package @ commit, mount Drive, train with checkpoints, infer one year at a time, write class maps to Drive); `daiff forest import-unet -c CFG --dir <downloaded>` writes `forest10m_<year>.tif` variants under `raw/forest10m_unet/`. Local tests: model forward shape; import aligns to grid. Selection: whichever classifier has higher forest-F1 on the reference sample becomes the run input (decision logged).

### Task P4.4: Validation and Table 16
`daiff validate --what forest` (FR-F1, FR-F2 OA/F1, area-adjusted loss ± CI, kappa, FR-F3 Hansen comparison) and `--what flood` (FR-R2 AUC vs HAND baseline, high-class share ≤ 30% area, FR-R3 ablation ± CI, permutation importance, block CV). If AUC < 0.80: try in order (a) `flood.flooded_fraction_threshold` 0.3, (b) quantile breaks (OI-7), (c) hyper-parameter search with block CV — each attempt logged; never tune on the test events.

### Task P4.5: NFR acceptance sweep
NFR-3 (re-run tagged config → identical checksums), NFR-5 (`scripts/nfr5_timing.py` on 5 layers), NFR-6 (5 non-team users — human; protocol in `docs/nfr6_protocol.md`), NFR-7 (`docs/LICENSES.md` review by guide — human), NFR-8 (screenshot evidence), NFR-9 (CI + coverage ≥ 80% on coupling), NFR-10 (gitleaks clean). Demo script `docs/demo_tier1.md` for FR-C2/FR-R1/FR-V1 witnessed demos.

---

## P5 — Tier 2

### Task P5.1: Monthly forest (FR-F5)
`daiff.gee.s2.monthly_composites(year)` for Nov–Mar; reuse classifier; `raw/forest10m_monthly/forest10m_<yyyy-mm>.tif`; report loss-class F1 vs annual (target within 0.05).

### Task P5.2: Rainfall-triggered risk (FR-R4)
`src/daiff/alerts/thresholds.py`: `wet_day_percentile(daily, q=99, wet_mm=1.0) -> pd.Series` (OI-8). `src/daiff/flood/rainfall_risk.py`: `classify_subbasin_day(rain_mm, threshold, high_share) -> int` (rule table calibrated on training event-days: class = min(5, base class from `high_share` quintile + 1 if rain ≥ threshold + 1 more if rain ≥ 1.5·threshold)); `event_day_labels(events, masks, zones) -> DataFrame` (sub-basin-day flooded/not); `pod_far(pred, truth) -> dict`. Targets POD ≥ 0.70, FAR ≤ 0.40 on held-out days.

### Task P5.3: What-if scenarios (FR-R5)
`src/daiff/flood/scenario.py`: `run_scenario(cfg, subbasin_id, extra_loss_pct, year) -> Path` (reduce f by pct of remaining forest in the sub-basin, recompute dF/CN/Q locally and U globally, predict sub-basin + downstream cells, write `scenarios/<hash>/delta_s.tif`); `POST /api/scenarios` + Map-page panel. Test: 10% scenario < 300 s on Kopili (timed, logged), ΔS ≥ 0 everywhere (monotone).

### Task P5.4: Alert engine and notifiers (FR-A2)
`src/daiff/alerts/engine.py`: `AlertEngine(cfg, store)` with `poll(now)` reading observed rainfall (GPM IMERG via GEE, dataset pinned here) and forecast (NOAA GFS 0.25° `NOAA/GFS0P25`) per flagged sub-basin; `alerts.sqlite` schema `alerts(id, subbasin_id, kind, rain_mm, threshold_mm, data_time, issued_time, sent_email)`; `notify.py` (SMTP+TLS from env; fallback `data/outbox/<id>.eml`). `daiff alerts poll|replay --event ID`; replay measures `issued_time − data_time` ≤ 1 h. `GET /api/alerts` + Alerts page (sub-basin, rain, time). Validation (SRS 7.5) via `pod_far`.

---

## P6 — Tier 3 (Colab only)

### Task P6.1: SAR–optical fusion (FR-R6)
`src/daiff/research/fusion.py`: feature stack builder (S2 bands + S1 VV/VH monthly median/std) and a small two-branch CNN (CPU-testable forward pass); GEE chip export incl. S1; `notebooks/colab/fusion_train.ipynb`. Compare with Tier 1 classifier on the same reference sample and cloud-gap months; results table `docs/results/tier3_fusion.md` with GPU hours — reported regardless of outcome.

### Task P6.2: Inundation forecaster (FR-A3)
`src/daiff/research/forecaster.py`: dataset builder at sub-basin/day scale (sequences of 30 days CHIRPS/GFS, static features, last S1 flooded fraction) and a small transformer encoder (≤ 1 M params) predicting flooded fraction > 0.05 for leads 1–7; baselines persistence + climatology; metrics AUC and Brier skill per lead; `notebooks/colab/forecaster_train.ipynb`; results `docs/results/tier3_forecast.md`.

---

## P7 — Close-out

### Task P7.1: Verification matrix and test log complete
Every requirement row has artifact + status; every Tier 1 row links its test-log entry.

### Task P7.2: Documentation and handover
README (install, run, serve, Colab), `docs/user_guide.md` (dashboard walkthrough with screenshots), `docs/operator_guide.md` (config, GEE, HPC/SLURM, adding a year), SRS deviations summary for the guide, OI-9 reconciliation once the team presentation is shared. Tag `v1.0.0`.
