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

## Open issues (SRS chapter 10)

| OI | Issue | Status | Resolution / current default |
|---|---|---|---|
| OI-1 | Pilot basin and sub-basin layer | **Resolved** (D-02) | Kopili, Assam. HydroBASINS level chosen in P3 for 20–60 sub-basins (default level 8) |
| OI-2 | Baseline year t₀ | Open — check in P3 | D-24 rule |
| OI-3 | Design-rainfall return period | **Adopted** | 10-year, one-day maximum (Gumbel on CHIRPS annual maxima) |
| OI-4 | HPC node type, GPU hours, NFR-1 budget | Open — guide | Laptop timings recorded meanwhile (D-05) |
| OI-5 | Flood-event inventory, ≥ 6 usable events | Open — P3 | DFO + ReliefWeb + ASDMA + EMS; `reference/flood_events.csv` |
| OI-6 | Minimum mapping unit | **Adopted** | 0.5 ha (50 px at 10 m) |
| OI-7 | Fixed or quantile risk-class breaks | Open — P4 | Fixed 0.2/0.4/0.6/0.8 until calibration |
| OI-8 | Rainfall alert threshold method | Open — P5 | 99th percentile of wet-day (≥ 1 mm) CHIRPS rainfall per sub-basin |
| OI-9 | Reconcile Figure 1 / Appendix A with the team presentation | Open — needs the presentation | — |
| OI-10 | Confirm Table 16 targets | Open — guide | Targets as written in the SRS |
