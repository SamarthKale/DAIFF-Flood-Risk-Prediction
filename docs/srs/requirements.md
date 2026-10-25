# DAIFF Requirement Register (transcribed from DAIFF-SRS v1.0)

Source: *Software Requirements Specification — AI-Based Deforestation Monitoring and Flood Risk
Prediction Using Sentinel-2 and Climate Data (DAIFF)*, v1.0, 25 October 2026, Problem Statement 3,
HPC Research Internship. The PDF is kept locally at `docs/srs/DAIFF-SRS-v1.0.pdf` (not committed).

This file is the working copy every session uses. **Do not edit requirement text or acceptance
criteria here.** Interpretations and deviations go in `docs/decisions.md`; implementation status
goes in `docs/verification_matrix.md`.

Conventions (SRS 1.2): **shall** = binding; **should** = recommendation, not verified.
Tier 1 = mandatory for acceptance. Tier 2 = planned extension. Tier 3 = research, reported
regardless of outcome. Verification methods: T = test, A = analysis, I = inspection,
D = demonstration.

## 1. Scope (SRS 1.4, 2.3, 2.4)

DAIFF is a decision-support research prototype for one pilot river basin of 5,000–20,000 km² with
documented forest loss and repeated flooding since 2015. It does not replace official forecasts.

| Tier | Functionality | Techniques | Completion criterion |
|---|---|---|---|
| 1 Minimum working system | S2 composites; annual forest/non-forest maps; loss maps between any two years; flood-susceptibility map driven by latest forest map; change-in-susceptibility map; dashboard; high-risk sub-basin flags | NDVI, NBR with Random Forest or small U-Net; Random Forest or XGBoost for susceptibility | All Tier 1 acceptance criteria pass |
| 2 Planned extension | Rainfall-triggered alerts (observed or forecast); what-if scenarios; monthly forest updates | Per-sub-basin rainfall exceedance thresholds; counterfactual runs | Alert skill targets met on held-out events |
| 3 Research | SAR–optical fusion (S1+S2) for monsoon gaps; spatio-temporal transformer forecasting inundation 1–7 days ahead | Fusion network or feature stacking; transformer over image + rainfall sequences | Compared with Tier 1 on same test sets and reported |

Flood framing: Tier 1 = flood **susceptibility** (no time horizon, five classes); Tier 2 =
rainfall-triggered risk classification per sub-basin; Tier 3 = 1–7 day forecasting.

## 2. Key definitions (SRS Table 1)

| Term | Definition |
|---|---|
| Forest | Pixel with tree canopy cover ≥ 30% |
| Forest loss | Pixel that is forest at the baseline date and non-forest at the comparison date |
| Analysis cell | 30 m cell on the common project grid; unit of modelling |
| Sub-basin | Hydrological sub-catchment from HydroBASINS or equivalent; unit of reporting and alerting |
| Flood susceptibility | Modelled probability a cell is inundated during a flood event given terrain, soil, land cover, rainfall climate; no time horizon |
| Flood risk class | Susceptibility binned into 5 ordered classes: very low, low, moderate, high, very high |
| Coupling features | C1, C2, C3 — the only inputs through which forest change enters the flood model |
| Event-triggered alert | Warning for a sub-basin whose risk class is high/very high when observed or forecast rainfall exceeds the sub-basin threshold |
| Baseline year t₀ | Reference year for loss and ΔS (OI-2) |

## 3. Coupling model (SRS chapter 3)

- Forest fraction **f(c, t)**: share of 10 m forest pixels inside 30 m cell c in year t, 0–1.
- Baseline **t₀**: 2017 or 2018 per SRS (OI-2).
- Local loss **ΔF(c, t) = f(c, t₀) − f(c, t)**, clipped at 0. Regrowth recorded separately, unused in Tier 1.

| ID | Feature | Computation | Rationale |
|---|---|---|---|
| C1 | Local forest fraction and local loss | f(c,t) and ΔF(c,t) per cell | Less canopy → less interception/infiltration |
| C2 | Upstream forest loss U(c,t) | Area-weighted share of upstream contributing area deforested since t₀, D8 flow directions, Eq. (1) | Runoff from cleared slopes reaches low cells |
| C3 | Curve number and runoff depth | SCS CN from land-cover class in year t and hydrologic soil group; runoff Q for design rainfall P; Eqs. (2), (3) | Physically based channel; clearing raises CN |

Equations (A(c) = set of cells draining through c; a(u) = area of cell u; S, Q, P in mm;
P = 10-year return period one-day maximum rainfall for the sub-basin, OI-3):

```
(1)  U(c,t) = Σ_{u∈A(c)} a(u)·ΔF(u,t) / Σ_{u∈A(c)} a(u)
(2)  S = 25400 / CN − 254
(3)  Q = (P − 0.2·S)² / (P + 0.8·S)   if P > 0.2·S;   Q = 0 otherwise
```

Use in the flood model (SRS 3.4):
1. Features: elevation, slope, TWI, HAND, distance to river, hydrologic soil group, rainfall climatology + C1, C2, C3.
2. Time-matched training: each historical flood event paired with the forest map of the year before the event.
3. Monotonic constraint: predicted susceptibility shall not decrease when ΔF, U or CN increases, all else equal (XGBoost monotone constraints, or post-training check for RF).
4. ΔS(c,t) = S(c,t) − S(c,t₀), same trained model, baseline vs current coupling features.
5. Sub-basin summary: forest loss (ha), mean ΔS, area that moved up ≥ 1 risk class.
6. Risk classes at probability thresholds 0.2, 0.4, 0.6, 0.8 unless quantile breaks adopted after calibration (OI-7).

Scientific caveat (SRS 3.5): forest–flood link is contested for large floods; the coupling
contribution is measured by ablation and reported even if small.

## 4. External interfaces (SRS chapter 4)

User interface:
- Web map with switchable layers (S2 composite, forest, forest loss, susceptibility, ΔS) and a year selector.
- Sub-basin table: forest loss, mean ΔS, risk class, area by class; sortable by any column.
- Location panel on map click: forest fraction over time, susceptibility, three most influential features.
- Banner on every map view: outputs are experimental decision support, with the displayed model's validation accuracy.
- Alert list (Tier 2): active alerts with sub-basin, rainfall amount, time.

Software interfaces: GEE or Copernicus Data Space (S1/S2), NOAA (CPC Global Unified Precipitation,
GHCN-Daily), USGS/OpenTopography (SRTM 1″), GFW/Hansen GFC (loss labels), flood archives (DFO,
EM-DAT, Copernicus EMS; manual download, stored as vector/CSV), e-mail server SMTP over TLS (Tier 2).

Compute: SLURM batch jobs; tile parallelism with Dask or job arrays; GPU only for U-Net and Tier 3.
Communication: dashboard over HTTPS; credentials outside the repository; Tier 2 alerts by e-mail and on the dashboard.

## 5. Functional requirements (SRS chapter 5)

### 5.1 Data ingestion (FR-D)

| ID | Requirement | Tier | Method | Acceptance criterion |
|---|---|---|---|---|
| FR-D1 | Query and download Sentinel-2 L2A imagery for the study area and a given date range | 1 | T | For one dry season, the list of fetched tiles matches the catalogue query for the study area |
| FR-D2 | Mask clouds and shadows using the scene classification layer and build a median composite per period | 1 | I, T | Masked gaps ≤ 5% of study area; visual check of 20 random 1 km windows finds no cloud remnants in ≥ 18 |
| FR-D3 | Ingest daily rainfall (NOAA CPC or GHCN-Daily, optionally IMD or CHIRPS) from 2000 to present | 1 | T | Daily series for every sub-basin with no gap > 3 days, or each such gap flagged |
| FR-D4 | Ingest SRTM 1″ elevation; derive slope, flow direction, flow accumulation, TWI, HAND | 1 | A | Derived stream network within 60 m of the mapped river network for ≥ 90% of its length |
| FR-D5 | Reproject all layers to one grid: study-area UTM zone, 30 m, common origin | 1 | T | Automated check confirms identical CRS, resolution and extent for every layer in the feature stack |

### 5.2 Forest change (FR-F)

| ID | Requirement | Tier | Method | Acceptance criterion |
|---|---|---|---|---|
| FR-F1 | Classify each 10 m pixel as forest / non-forest for each annual composite | 1 | A | Overall accuracy ≥ 90% and forest-class F1 ≥ 0.85 on the reference sample (SRS 7.3) |
| FR-F2 | Produce a forest-loss map between any two user-selected years | 1 | A | Loss-class F1 ≥ 0.70 against the reference sample for the test period |
| FR-F3 | Report forest loss in hectares per sub-basin and per year | 1 | T, A | Totals equal the sum of loss pixels within 0.5%; study-area total within 25% of Hansen for the same years, or the difference explained |
| FR-F4 | Remove isolated loss patches smaller than the minimum mapping unit | 1 | I | No loss patch < 0.5 ha (OI-6) remains |
| FR-F5 | Update the forest map monthly using all cloud-free observations | 2 | A | Monthly maps for one full dry season; loss-class F1 within 0.05 of the annual map |

### 5.3 Coupling (FR-C)

| ID | Requirement | Tier | Method | Acceptance criterion |
|---|---|---|---|---|
| FR-C1 | Compute C1, C2, C3 for each cell and year as in chapter 3 | 1 | T | Unit tests on a synthetic 10 × 10 grid with known flow paths reproduce hand-computed values exactly |
| FR-C2 | Recompute C1–C3 and re-run the flood-risk model automatically whenever a new forest map is produced | 1 | D | Adding a forest map triggers a run that publishes new susceptibility and ΔS maps with no manual step |
| FR-C3 | Produce a ΔS map between the baseline year and any later year | 1 | T | ΔS is zero (within 10⁻⁶) everywhere when the same forest map is supplied for both years |
| FR-C4 | Predicted susceptibility shall not decrease when forest loss increases, all other inputs equal | 1 | T | Synthetic test: removing forest from 100 upstream cells never lowers S at any downstream cell and raises S at the outlet cell |

### 5.4 Flood risk (FR-R)

| ID | Requirement | Tier | Method | Acceptance criterion |
|---|---|---|---|---|
| FR-R1 | Train a flood-susceptibility model on historical flood extents using the SRS 3.4 features | 1 | D | Training script runs end to end from a configuration file and saves model, feature list and metrics |
| FR-R2 | Output susceptibility probability 0–1 per cell and a five-class risk map | 1 | A | AUC-ROC ≥ 0.80 on held-out flood events and ≥ 0.05 above the HAND baseline (SRS 7.4) |
| FR-R3 | Report the contribution of coupling features to model skill | 1 | A | Ablation table (with/without C1–C3) and permutation importance produced on the test set |
| FR-R4 | Classify each sub-basin's risk for a given daily rainfall input, observed or forecast | 2 | A | POD and FAR targets in Table 16 met on held-out event days |
| FR-R5 | What-if scenarios applying a user-specified additional forest loss to a sub-basin | 2 | T | A 10% additional-loss scenario returns a ΔS map for one sub-basin in under 5 minutes |
| FR-R6 | Research track compares SAR–optical fusion and a spatio-temporal transformer with the Tier 1 baseline | 3 | A | Results table on the Tier 1 test sets, including compute cost, reported regardless of outcome |

### 5.5 Dashboard (FR-V)

| ID | Requirement | Tier | Method | Acceptance criterion |
|---|---|---|---|---|
| FR-V1 | Display S2 composites, forest-loss, susceptibility and ΔS maps as switchable layers with a year selector | 1 | D | In a recorded walkthrough, every layer loads for every available year |
| FR-V2 | Show a sub-basin table; export the table as CSV and maps as GeoTIFF | 1 | T | Exported CSV values match pipeline output exactly; exported GeoTIFFs open in QGIS with correct georeferencing |
| FR-V3 | Clicking a location shows forest fraction over time, susceptibility and the three most influential features | 1 | T | Correct values for 10 random test points, checked against the rasters |

### 5.6 Alerts (FR-A)

| ID | Requirement | Tier | Method | Acceptance criterion |
|---|---|---|---|---|
| FR-A1 | Flag every sub-basin whose risk class is high or very high in the latest susceptibility map | 1 | T | Flag list matches the risk map for all sub-basins |
| FR-A2 | Issue an alert when daily rainfall over a flagged sub-basin exceeds its threshold (99th percentile of wet-day rainfall unless tuned, OI-8), on the dashboard and by e-mail | 2 | D | Replaying a past event raises the alert within 1 hour of the rainfall data becoming available |
| FR-A3 | Research track forecasts inundation probability 1–7 days ahead | 3 | A | Skill reported against persistence and climatology baselines |

### 5.7 Use cases (SRS Table 7)

| ID | Use case | Actor | Tier | Realised by |
|---|---|---|---|---|
| UC-01 | View forest-loss maps | Environmental analyst | 1 | FR-F1, FR-F2, FR-V1 |
| UC-02 | Generate forest-loss report | Environmental analyst | 1 | FR-F3, FR-V2 |
| UC-03 | View flood-risk and ΔS maps | Disaster management officer | 1 | FR-R2, FR-C3, FR-V1 |
| UC-04 | Inspect location details | Analyst, officer | 1 | FR-V3 |
| UC-05 | Export maps and tables | Analyst, officer | 1 | FR-V2 |
| UC-06 | Receive rainfall alerts | Disaster management officer | 2 | FR-R4, FR-A2 |
| UC-07 | Run what-if scenario | Environmental analyst | 2 | FR-R5 |
| UC-08 | Ingest data and update forest map | System operator | 1 | FR-D1–FR-D5, FR-F1 |
| UC-09 | Train and validate models | Operator, evaluator | 1 | FR-R1, FR-R3 |
| UC-10 | Review validation metrics | Researcher / evaluator | 1 | FR-R3, NFR-8 |
| UC-11 | Configure study area and thresholds | System operator | 1 | FR-D5, FR-A1 |
| UC-12 | Recompute flood-risk maps | System (in UC-08) | 1 | FR-C1, FR-C2 |

## 6. Non-functional requirements (SRS chapter 6) — all Tier 1

| ID | Category | Requirement | Method | Acceptance criterion |
|---|---|---|---|---|
| NFR-1 | Performance | One annual update for the study area within 6 hours on the HPC allocation (OI-4) | T | Timed run from raw imagery to published maps; timing log kept in the repository |
| NFR-2 | Scalability | Processing tiled to run in parallel across nodes | T | Doubling workers reduces wall time by ≥ 40% on the benchmark run |
| NFR-3 | Reproducibility | Every run driven by a version-controlled config with fixed seeds and recorded data versions | T | Re-running a tagged configuration produces identical rasters (checksum match) |
| NFR-4 | Provenance | Each output records inputs, dates, model version and code commit in its metadata | I | A metadata check script passes on all outputs |
| NFR-5 | Responsiveness | Map layers load < 3 s; sub-basin table < 1 s on a 10 Mbps connection | T | Measured with browser developer tools on 5 layers |
| NFR-6 | Usability | A new user finds the risk class and forest loss for a named sub-basin without assistance | D | ≥ 4 of 5 non-team test users succeed within 2 minutes |
| NFR-7 | Openness | Only openly licensed data and open-source libraries, licences listed in the repository | I | Licence list reviewed and accepted by the project guide |
| NFR-8 | Transparency | Outputs labelled experimental decision support; model accuracy shown beside each map | I | Label and metrics visible on every map view |
| NFR-9 | Maintainability | Automated tests for FR-C1, FR-C3, FR-C4 and FR-D5 run on every commit | T | CI run passes; coupling-module test coverage ≥ 80% |
| NFR-10 | Security | Data-service credentials not stored in the code repository | I | A secret scan of the repository finds no credentials |

Design constraints (SRS 2.7): open data and open-source only; Tier 1 must also run on a single
16 GB RAM workstation for a reduced test area; 8-month duration; dry-season (Nov–Mar) Sentinel-2
composites because of monsoon cloud; all rasters in the study-area UTM zone on a common 30 m grid.
Assumptions (SRS 2.8): S2 L2A from 2017; ≥ 6 distinct flood events since 2015 (OI-5); NOAA daily
rainfall covers the area (IMD or CHIRPS where finer resolution needed); S2 classified at 10 m,
modelling at 30 m.

## 7. Data and validation plan (SRS chapter 7)

### 7.1 Datasets (SRS Table 15)

| Dataset | Use | Resolution / period | Role |
|---|---|---|---|
| Sentinel-2 L2A | Forest classification | 10 m; 2017– | Input |
| Sentinel-1 GRD | Flood extents; Tier 3 fusion | 10 m; 2015– | Labels, input |
| NOAA CPC Global Unified; GHCN-Daily | Rainfall climatology, design and event rainfall | 0.5° grid, stations; daily | Input |
| IMD gridded or CHIRPS | Finer rainfall where NOAA is coarse | 0.25°, 0.05°; daily | Input (optional) |
| SRTM 1″ | Elevation, terrain | 30 m | Input |
| SoilGrids | Hydrologic soil group for CN | 250 m | Input |
| Hansen GFC | Forest-loss reference labels | 30 m; annual from 2001 | Validation |
| Hand-interpreted points | Independent forest/loss reference | Points | Validation |
| ESA WorldCover; Dynamic World | Land-cover cross-check, CN classes | 10 m | Cross-check |
| Global Flood Database | Historical flood extents | 250 m; 2000–2018 | Labels |
| DFO archive | Event dates, approximate extents | Events; 1985– | Event list |
| EM-DAT | Event list and impacts | Events | Event list |
| Copernicus EMS Rapid Mapping | Detailed event flood maps | Events | Test labels |
| State/district disaster records; NRSC Bhuvan | Local event dates, areas, hazard zones | Varies | Test labels, comparison |
| JRC Global Surface Water | Permanent-water mask | 30 m | Mask |

### 7.2 Data quality
- All layers checked for CRS, resolution and extent consistency before modelling (FR-D5).
- Cells with permanent water (JRC occurrence > 90%) excluded from flood labels.
- Every dataset version and download date recorded in run metadata (NFR-4).

### 7.3 Forest-change validation
1. ≥ 600 points, stratified random on map classes (stable forest, stable non-forest, loss), ≥ 150 in loss (Olofsson et al. 2014).
2. Two team members label each point independently from the S2 time series and high-resolution imagery; a third resolves disagreements; Cohen's kappa reported.
3. Loss compared with Hansen loss for the same years after aggregation to 30 m (Hansen = reference, not ground truth; stand-replacing loss only).
4. Metrics: overall accuracy, per-class F1, user's and producer's accuracy, area-adjusted loss estimate with 95% CI.

### 7.4 Flood-susceptibility validation
1. Event inventory since 2015 from DFO, EM-DAT, state records; ≥ 6 usable events (OI-5).
2. Labels: Sentinel-1 change detection (VV decrease, Otsu threshold), checked against Copernicus EMS or Global Flood Database where available; permanent water masked; equal number of non-flooded cells sampled.
3. Splits: temporal hold-out (train on events up to 2021, test from 2022) and spatial block CV with 10 km blocks.
4. Baseline: HAND < 5 m classed susceptible; the model must exceed it.
5. Ablation: retrain without C1–C3; AUC difference = measured contribution of forest change.

### 7.5 Alert validation (Tier 2)
Every sub-basin-day in the test period labelled flooded / not flooded from S1 extents, DFO and
state records; alerts compared to compute POD and FAR.

### 7.6 Acceptance targets (SRS Table 16; to be confirmed with the guide, OI-10)

| Metric | Requirement | Target | Tier |
|---|---|---|---|
| Overall accuracy, forest/non-forest | FR-F1 | ≥ 90% | 1 |
| F1, forest class | FR-F1 | ≥ 0.85 | 1 |
| F1, loss class | FR-F2 | ≥ 0.70 | 1 |
| AUC-ROC on held-out events | FR-R2 | ≥ 0.80 and ≥ 0.05 above HAND baseline | 1 |
| Share of flooded test cells in high + very high classes | FR-R2 | ≥ 60%, with those classes covering ≤ 30% of the study area | 1 |
| Coupling ablation | FR-R3 | Reported with confidence interval; no minimum | 1 |
| POD, sub-basin event days | FR-R4, FR-A2 | ≥ 0.70 | 2 |
| FAR, sub-basin event days | FR-R4, FR-A2 | ≤ 0.40 | 2 |

## 8. Acceptance procedure (SRS 8.3)
1. Team runs each Tier 1 verification and records inputs, outputs and results in the test log in the repository (`docs/test_log.md`).
2. Analysis results computed by committed scripts on frozen test sets.
3. Project guide reviews the test log and witnesses demonstrations for FR-C2, FR-R1, FR-V1.
4. Accepted when every Tier 1 requirement passes. Tier 2/3 results reported but do not affect acceptance.

Traceability of expected outcomes (SRS Table 19): deforestation maps → FR-D1, FR-D2, FR-F1–F4;
flood model → FR-D3, FR-D4, FR-C1–C4, FR-R1–R3; dashboard → FR-V1–V3, NFR-5, NFR-6, NFR-8;
early warning → FR-A1 (Tier 1), FR-R4, FR-A2 (Tier 2).

## 9. Open issues (SRS Table 21)
Status tracked in `docs/decisions.md`.

| ID | Issue | Decided by | Needed by |
|---|---|---|---|
| OI-1 | Pilot basin and sub-basin layer (Assam, Kerala or Odisha) | Team + guide | Month 1 |
| OI-2 | Baseline year t₀ (2017 or 2018) | Team | Month 1 |
| OI-3 | Design-rainfall return period for C3 (proposed 10-year, 1-day max) | Team | Month 3 |
| OI-4 | HPC node type, GPU hours, NFR-1 time budget | Guide | Month 1 |
| OI-5 | Flood-event inventory; ≥ 6 usable events | Team | Month 2 |
| OI-6 | Minimum mapping unit for loss patches (proposed 0.5 ha) | Team | Month 2 |
| OI-7 | Fixed or quantile risk-class breaks | Team | Month 4 |
| OI-8 | Rainfall alert threshold method | Team | Month 6 |
| OI-9 | Reconcile Figure 1 / Appendix A with the team presentation | Team | Before submission |
| OI-10 | Confirm acceptance targets (Table 16) | Guide | Month 1 |

## 10. Appendix A — eight-month work plan (SRS Table 22)

| Month | Work | Requirements closed | Gate |
|---|---|---|---|
| 1 | Study area, event inventory, data access, common grid | FR-D1–D5 | Feature stack passes FR-D5 |
| 2–3 | Forest classification, loss maps, reference interpretation | FR-F1–F4 | Forest targets met |
| 3–4 | Flood labels, coupling features, susceptibility model | FR-C1–C4, FR-R1–R3 | Flood targets met |
| 5 | Dashboard and Tier 1 flags | FR-V1–V3, FR-A1 | Tier 1 complete |
| 6–7 | Alerts, scenarios, monthly updates; Tier 3 in parallel | FR-F5, FR-R4, FR-R5, FR-A2, FR-R6, FR-A3 | Alert targets met |
| 8 | Final evaluation, report, handover | NFR verification | Faculty review |

## 11. Appendix B — indicative SCS curve numbers (TR-55 Table 2-2, ARC II)
Verify against the source and map project land-cover classes to TR-55 cover types before use.

| Land cover (TR-55 cover type) | A | B | C | D |
|---|---|---|---|---|
| Woods, good hydrologic condition | 30 | 55 | 70 | 77 |
| Pasture or grassland, good condition | 39 | 61 | 74 | 80 |
| Row crops, straight row, good condition | 67 | 78 | 85 | 89 |
| Fallow, bare soil | 77 | 86 | 91 | 94 |
| Impervious surfaces (paved, roofs) | 98 | 98 | 98 | 98 |

## 12. Appendix C — output data dictionary

Output files (SRS Table 24):

| File | Format | Content |
|---|---|---|
| `forest_<year>.tif` | GeoTIFF (COG) | Forest fraction f(c,t) per 30 m cell, 0–1 |
| `loss_<t0>_<year>.tif` | GeoTIFF (COG) | Forest loss ΔF(c,t), 0–1 |
| `coupling_<year>.tif` | GeoTIFF (COG), 4 bands | C1 forest fraction, C1 loss, C2 upstream loss, C3 runoff depth Q (mm) |
| `susceptibility_<year>.tif` | GeoTIFF (COG) | Flood susceptibility S(c,t), 0–1 |
| `riskclass_<year>.tif` | GeoTIFF (COG) | Risk class 1 (very low) – 5 (very high) |
| `delta_s_<year>.tif` | GeoTIFF (COG) | ΔS relative to t₀ |
| `subbasin_<year>.csv` | CSV | One row per sub-basin (fields below) |
| `run_metadata.json` | JSON | Inputs, data versions, model version, code commit, configuration, timings |

Sub-basin table fields (SRS Table 25):

| Field | Unit | Description |
|---|---|---|
| `subbasin_id` | – | Sub-basin identifier from the sub-basin layer |
| `area_km2` | km² | Sub-basin area |
| `forest_loss_ha` | ha | Forest loss since the baseline year |
| `forest_fraction` | 0–1 | Mean forest fraction in the current year |
| `mean_s` | 0–1 | Mean flood susceptibility |
| `mean_delta_s` | −1 to 1 | Mean change in susceptibility since baseline |
| `area_class_1` … `area_class_5` | km² | Area in each risk class |
| `area_moved_up_km2` | km² | Area that moved up ≥ 1 risk class since baseline |
| `risk_flag` | yes / no | True when the sub-basin is high or very high risk (FR-A1) |
