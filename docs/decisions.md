# Decisions and Open Issues

Every decision that interprets, fixes or deviates from DAIFF-SRS v1.0 is recorded here. Add new
rows at the bottom; never rewrite history. If a decision is superseded, add a new row that says so.

## Decision log

| ID | Date | Decision | Why | SRS ref |
|---|---|---|---|---|
| D-01 | 2026-10-25 | Data access through Google Earth Engine (free non-commercial projects) | All datasets in one catalogue; server-side compositing; small downloads | 2.6, 4.2 |
| D-02 | 2026-10-25 | Pilot basin Kopili, Assam; grid CRS EPSG:32646 | Near-annual floods, documented upstream forest loss, single UTM zone | 1.4, OI-1 |
| D-03 | 2026-10-25 | All three tiers in scope, built in tier order | Team decision | 2.3 |
| D-04 | 2026-10-25 | Local compute CPU-only; GPU work only on Google Colab; local GPU never used | Team decision | 2.6, 4.3 |
| D-05 | 2026-10-25 | Laptop now, SLURM-ready (dask-jobqueue + sbatch scripts); NFR-1/2 measured on the laptop until HPC access exists | HPC access pending | 2.6, 4.3, OI-4 |
| D-06 | 2026-10-25 | Dashboard: FastAPI + rio-tiler; React + TypeScript + Vite + MapLibre GL | Tile serving for NFR-5 | 4.1, NFR-5 |
| D-07 | 2026-10-25 | Public GitHub repo; trunk-based on `main`; push after every task; CI non-blocking | Relay handoff between teammates | NFR-9 |
| D-08 | 2026-10-25 | No AI co-author trailers in commits or PRs | Team decision | — |
| D-09 | 2026-10-25 | Architecture A: GEE produces pixels; local Python does terrain, coupling, models, validation, outputs | C2 and FR-C1 tests need local, testable code | 2.1, 3 |
| D-10 | 2026-10-25 | GEE products exported as EE assets and downloaded with `ee.data.getPixels`; Colab uses Google Drive | No local Drive/OAuth client; robust to long computations | 4.2 |
| D-11 | 2026-10-25 | Own small stage-DAG runner instead of Snakemake/Prefect | Readability for a rotating team | — |
| D-12 | 2026-10-25 | Hydrologic soil groups from HYSOGs250m (derived from SoilGrids) instead of a texture rule on raw SoilGrids | Purpose-built HSG product | 3.3, 7.1 |
| D-13 | 2026-10-25 | Python 3.12, uv-managed `.venv`, link-mode copy | Matches Colab; exFAT drive | 2.6 |
| D-14 | 2026-10-25 | Random Forest in GEE is the primary forest classifier; a U-Net on Colab is the challenger; the better one on the reference sample is used | SRS allows either | 2.3 |
| D-15 | 2026-10-25 | Flood model = XGBoost with monotone constraints | Enforces FR-C4 | 3.4 |
| D-16 | 2026-10-25 | CHIRPS for design rainfall and climatology; NOAA CPC also ingested and used as cross-check | CPC 0.5° coarser than sub-basins | 2.8, FR-D3 |
| D-17 | 2026-10-25 | Reference-labelling tool in the dashboard; labels committed to `reference/` | 600 double-interpreted points needed | 7.3 |
| D-18 | 2026-10-25 | Forest map *t* = dry season 1 Nov (t−1) – 31 Mar t; a flood in the monsoon of year Y pairs with forest map Y (latest map before the event) | Makes "year before the event" concrete | 2.7, 3.4 |
| D-19 | 2026-10-25 | Sub-basin risk class = class of the sub-basin's mean susceptibility; FR-A1 flags classes 4–5 | SRS does not define a sub-basin class | FR-A1, App. C |
| D-20 | 2026-10-25 | ΔF = fraction of the cell's 10 m pixels inside MMU-filtered loss patches; f(c,t) = raw 3×3 aggregation | Keeps MMU filtering (FR-F4) consistent with coupling | 3.2, FR-F4 |
| D-21 | 2026-10-25 | A(c) in Eq. (1) includes c itself | Standard flow-accumulation convention | Eq. (1) |
| D-22 | 2026-10-25 | CN = f·CN_woods[HSG] + (1−f)·CN_nonforest[class, HSG] | Continuous, monotone in loss | 3.3, App. B |
| D-23 | 2026-10-25 | Dual hydrologic soil groups (A/D, B/D, C/D) treated as D | Conservative (undrained) | 3.3 |
| D-24 | 2026-10-25 | t₀ = 2019 if GEE S2 L2A covers < 90% of the AOI in the 2017/2018 dry seasons; otherwise 2018 | L2A sparse over India before ~Dec 2018 | 3.2, OI-2 |
| D-25 | 2026-10-25 | Kopili catchment ≈ 20,068 km² (Wikipedia) is at the SRS's "approximately 5,000–20,000 km²" upper bound; keep the whole basin and record the HydroBASINS area in P3. If compute is tight, restrict to the catchment above Dharamtul and log it | Upstream forest loss (Karbi Anglong, Dima Hasao) and the flooded plains (Nagaon, Morigaon) must both be inside | 1.4, OI-1 |
| D-26 | 2026-10-25 | Flood-event inventory starts as `reference/flood_events_kopili.csv` with 7 candidates (2017–2025), all `usable=False` until P3 confirms each Sentinel-1 flood extent; train ≤ 2021 currently has only 2020 (+2017/2019 if confirmed) — expect to revisit the temporal split (OI-5) | Sources found for 2020, 2022 (May, June), 2024, 2025; 2017/2019 statewide only | 7.4, OI-5 |
| D-33 | 2026-10-26 | Flood model hyper-parameters stay at defaults (depth 6, 400 trees). A regularised variant (depth 4, 300 trees, min_child_weight 50, subsample/colsample 0.8) was tried and scored lower on block CV (0.740 vs 0.745) and leave-one-event-out (0.753 vs 0.762), so it was dropped. Config keys `min_child_weight`, `subsample`, `colsample_bytree` remain available | Choice made on block CV, never by tuning on the held-out events | FR-R2 |
| D-27 | 2026-10-25 | t0 = 2018 (closes OI-2). GEE S2 L2A over Kopili: 2017 season 75 scenes, 2018 season 128, 2019-2026 322-431, all 8 MGRS tiles. Years 2018-2026. Kopili AOI = HydroBASINS L6 4060884570 (19,705.8 km2, within the SRS 20,000 km2 bound; supersedes the 20,068 km2 concern in D-25); 41 level-8 sub-basins; grid 7155 x 5671 cells (EPSG:32646) | Full-tile coverage from 2018 with a good scene count; 2017 composite would rest on half the scenes. The 2017 flood candidate has no forest map and stays unusable | 3.2, OI-1, OI-2 |
| D-28 | 2026-10-25 | Hydrologic soil groups from SoilGrids topsoil (0-30 cm, depth-weighted) sand/clay via a TR-55 texture rule (D: clay > 40 %; C: clay 20-40 %; A: sand >= 90 % and clay < 10 %; else B). Supersedes D-12 (HYSOGs is not available as a GEE asset). Earth Engine asset storage is not initialised for the project, so downloads use direct `computePixels` tiles (D-10 fallback) | Back to the SRS's SoilGrids source; over Kopili this gives mostly group C | 3.3, 7.1 |
| D-29 | 2026-10-25 | Forest RF training samples composites at 30,000 random points per year (not `stratifiedSample` over the basin), and S2 composites keep scenes < 40 % cloudy, at most 12 least-cloudy per MGRS tile per season | The first full-basin stratified sampling burned ~349 EECU-hours (over the 150 h Community quota) before it was cancelled; one-sub-basin test: 0.40 EECU-h per 403 km2 per year | 2.3, 2.7 |
| D-30 | 2026-10-25 | Flow routing (D8, accumulation, streams, HAND, TWI) on the MERIT Hydro hydrologically adjusted elevation (`MERIT/Hydro/v1_0_1` elv, 90 m -> 30 m bilinear); elevation and slope features stay SRTM | Raw SRTM routes the flat floodplain badly (17-21 % of plains streams within 60 m of OSM vs 38-50 % with MERIT); HAND is the key flood predictor | FR-D4, 3.4 |
| D-31 | 2026-10-25 | FR-D4 compares derived streams with catchment >= 200 km2 against OSM waterway=river/canal lines | OSM tags smaller channels as streams, which the river/canal query excludes | FR-D4 |
| D-32 | 2026-10-26 | Kopili flood model uses leave-one-event-out (`flood.strategy: loeo`): skill is measured on each of the 6 events predicted by a model trained on the other 5; the published model trains on all 6. The SRS temporal split (train <= 2021, test from 2022) is still computed and reported (`strategy: temporal`) | Only 2 usable events (2019, 2020) fall in the SRS training period; user asked for a stronger model | 7.4, OI-5 |

## Open issues (SRS chapter 10)

| OI | Issue | Status | Resolution / current default |
|---|---|---|---|
| OI-1 | Pilot basin and sub-basin layer | **Resolved** (D-02, D-27) | Kopili = HydroBASINS L6 4060884570, 19,705.8 km²; 41 level-8 sub-basins |
| OI-2 | Baseline year t₀ | **Resolved** (D-27) | t₀ = 2018 |
| OI-3 | Design-rainfall return period | **Adopted** | 10-year, one-day maximum (Gumbel on CHIRPS annual maxima) |
| OI-4 | HPC node type, GPU hours, NFR-1 budget | Open — guide | Laptop timings recorded meanwhile (D-05) |
| OI-5 | Flood-event inventory, ≥ 6 usable events | **Resolved** (P3) | 6 usable S1-mapped events: 2019, 2020 (train); 2022-05, 2022-06, 2024, 2025 (test). Train set is small — see D-26 |
| OI-6 | Minimum mapping unit | **Adopted** | 0.5 ha (50 px at 10 m) |
| OI-7 | Fixed or quantile risk-class breaks | Open — P4 | Fixed 0.2/0.4/0.6/0.8 until calibration |
| OI-8 | Rainfall alert threshold method | Open — P5 | 99th percentile of wet-day (≥ 1 mm) CHIRPS rainfall per sub-basin |
| OI-9 | Reconcile Figure 1 / Appendix A with the team presentation | Open — needs the presentation | — |
| OI-11 | FR-D4 target (90 % of derived streams within 60 m of mapped rivers) is not reachable with 30-90 m DEMs in the Kopili floodplain: best 67.6 % (hills 86-89 %, plains ~50 %). Options for the guide: accept with this evidence, revise the criterion (e.g. hills only, or 150 m), or burn OSM rivers into the DEM (then the check is circular) | Open — guide | Evidence in data/kopili/raw/fr_d4.json and the test log |
| OI-12 | FR-R2 (AUC >= 0.80 and >= HAND + 0.05) on real Kopili data: leave-one-event-out AUC 0.762 vs HAND 0.516 (+0.246, passes the margin, misses 0.80); per-event 0.69-0.83; coupling ablation +0.019 [0.019, 0.020]. Limits: only 6 Sentinel-1 events, noisy forest maps, elevation/slope dominate. Options for the guide: accept with evidence, add events (Planetary Computer S1, more years), or the U-Net forest challenger (P4) | Open — guide | metrics/flood.json in run 80f819fb49b2 / current run |
| OI-13 | FR-D2 visual cloud check: 2018 fails (14/20 clean), 2022 and 2026 pass (18/20). 2018 is the first season so it has no earlier year to gap-fill from | Open — fix in P4 (stricter cloud mask or cloud-probability filter for 2018, costs EE quota) | data/kopili/review/ and docs/test_log.md |
| OI-10 | Confirm Table 16 targets | Open — guide | Targets as written in the SRS |
