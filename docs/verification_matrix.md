# Verification Matrix

One row per requirement in [`srs/requirements.md`](srs/requirements.md). Status values:
`not started` · `partial` · `passing (synthetic)` · `accepted` (passed on Kopili, logged in
[`test_log.md`](test_log.md)). Update the row in the same commit that changes its status.

| Requirement | Tier | Method | Artifact | Phase | Status |
|---|---|---|---|---|---|
| FR-D1 | 1 | T | `raw/s2_inventory_<year>.csv` vs catalogue query (`daiff gee`) | P3 | not started |
| FR-D2 | 1 | I, T | `raw/fr_d2_<year>.json` gap share + 20-window visual check | P3 | not started |
| FR-D3 | 1 | T | `raw/rainfall/gaps.csv` (CPC + CHIRPS) | P3 | not started |
| FR-D4 | 1 | A | `daiff check-streams` (≥ 90% within 60 m of OSM rivers) | P1/P3 | not started |
| FR-D5 | 1 | T | `tests/test_grid.py::test_fr_d5_*`, `daiff check-grid` | P0/P3 | partial (synthetic passes; Kopili in P3) |
| FR-F1 | 1 | A | `daiff validate --what forest` (OA ≥ 90%, forest F1 ≥ 0.85) | P4 | not started |
| FR-F2 | 1 | A | `daiff validate --what forest` (loss F1 ≥ 0.70) | P1/P4 | not started |
| FR-F3 | 1 | T, A | `tests/forest/test_change.py::test_fr_f3_*` + Hansen comparison | P1/P4 | partial (sum rule passing; Hansen comparison in P4) |
| FR-F4 | 1 | I | `tests/forest/test_change.py::test_fr_f4_*` | P1 | passing (synthetic) |
| FR-F5 | 2 | A | monthly vs annual loss F1 report | P5 | not started |
| FR-C1 | 1 | T | `tests/coupling/test_features.py::test_fr_c1_*` | P1 | passing (synthetic) |
| FR-C2 | 1 | D | `daiff watch` + `tests/integration/test_end_to_end.py::test_fr_c2_*` | P1/P4 | passing (synthetic); demo in P4 |
| FR-C3 | 1 | T | `tests/flood/test_predict.py::test_fr_c3_*` | P1 | passing (synthetic) |
| FR-C4 | 1 | T | `tests/flood/test_predict.py::test_fr_c4_*` | P1 | passing (synthetic) |
| FR-R1 | 1 | D | `daiff train`, `tests/flood/test_model.py::test_fr_r1_*` | P1/P4 | passing (synthetic); demo in P4 |
| FR-R2 | 1 | A | `daiff validate --what flood` (AUC ≥ 0.80, ≥ HAND + 0.05) | P4 | not started |
| FR-R3 | 1 | A | ablation + permutation importance in `metrics/flood.json` | P1/P4 | passing (synthetic) |
| FR-R4 | 2 | A | POD/FAR on held-out event days | P5 | not started |
| FR-R5 | 2 | T | 10% scenario < 5 min | P5 | not started |
| FR-R6 | 3 | A | `docs/results/tier3_fusion.md` | P6 | not started |
| FR-V1 | 1 | D | recorded walkthrough (all layers × years) | P2/P4 | not started |
| FR-V2 | 1 | T | `tests/api/test_subbasins.py::test_fr_v2_*` | P2 | not started |
| FR-V3 | 1 | T | `tests/api/test_point.py::test_fr_v3_*` | P2 | not started |
| FR-A1 | 1 | T | `tests/flood/test_tables.py::test_fr_a1_*` | P1 | passing (synthetic) |
| FR-A2 | 2 | D | `daiff alerts replay` ≤ 1 h | P5 | not started |
| FR-A3 | 3 | A | `docs/results/tier3_forecast.md` | P6 | not started |
| NFR-1 | 1 | T | `docs/perf/` timed annual update ≤ 6 h | P4 | not started |
| NFR-2 | 1 | T | `daiff bench` (2× workers → ≥ 40% faster) | P1/P4 | passing on laptop (1→2 workers: 42% less time); HPC in P4 |
| NFR-3 | 1 | T | `tests/integration/test_end_to_end.py::test_nfr_3_*`, CI double run | P0/P1 | passing (synthetic) |
| NFR-4 | 1 | I | `daiff check-metadata`, `tests/store/test_check.py` | P0 | passing (synthetic) |
| NFR-5 | 1 | T | `scripts/nfr5_timing.py` | P2/P4 | not started |
| NFR-6 | 1 | D | 5 non-team users (`docs/nfr6_protocol.md`) | P4 | not started |
| NFR-7 | 1 | I | [`LICENSES.md`](LICENSES.md) reviewed by guide | P0/P4 | partial (list started) |
| NFR-8 | 1 | I | dashboard banner + metrics on every map view | P2 | not started |
| NFR-9 | 1 | T | CI on every push; coupling coverage ≥ 80% | P0/P1 | passing (coupling coverage 100%) |
| NFR-10 | 1 | I | gitleaks job in CI | P0 | partial (scan in CI) |
