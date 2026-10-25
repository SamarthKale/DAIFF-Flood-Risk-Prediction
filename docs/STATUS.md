# DAIFF — Build Status

_Last updated: 2026-10-25 — Samarth's machine (Claude session)_

## Now

- **Phase:** P1 Science core — executing (native, in session)
- **Last done:** P0 complete (Tasks 1-10).
- **Next task:** P1 Task 1 (deps, config sections, Dask runtime).
- **Blockers:** none for P0–P2. P3 onward needs Earth Engine registration.
- **Remote:** https://github.com/SamarthKale/DAIFF-Flood-Risk-Prediction (public, `main`)
- **CI:** not set up yet.

## Phases

| Phase | Scope | Plan | Status |
|---|---|---|---|
| P0 Bootstrap | env, CI, config, grid, store, runner, synthetic skeleton, GEE setup guide | [plan](superpowers/plans/2026-10-25-p0-bootstrap.md) | **done** |
| P1 Science core | terrain, forest, coupling, flood model, tables, flags, run/watch (synthetic) | [plan](superpowers/plans/2026-10-25-p1-science-core.md) | not started |
| P2 API + dashboard | FastAPI + React/MapLibre, exports, labelling page (synthetic) | [plan](superpowers/plans/2026-10-25-p2-api-dashboard.md) | not started |
| P3 Kopili ingestion | GEE: AOI, S2 + RF, S1 floods, references, rainfall, rivers, event inventory | [plan](superpowers/plans/2026-10-25-p3-kopili-ingestion.md) | not started |
| P4 Tier 1 acceptance | real runs, validation, U-Net challenger, NFR checks, test log | [plan](superpowers/plans/2026-10-25-p4-p7-acceptance-tier2-tier3-closeout.md) | not started (refine at start) |
| P5 Tier 2 | monthly forest, rainfall risk, what-if, alerts | same file | not started (refine at start) |
| P6 Tier 3 | SAR–optical fusion, 1–7 day forecaster (Colab) | same file | not started (refine at start) |
| P7 Close-out | verification matrix, docs, handover | same file | not started |

## Waiting on humans

- [x] **Samarth:** create the public GitHub repository — done:
      `SamarthKale/DAIFF-Flood-Risk-Prediction`.
- [ ] **Every teammate:** register a free non-commercial Google Earth Engine project (steps:
      `docs/setup/gee.md`), put the project ID in `.env`, and run
      `earthengine authenticate` yourself.
- [ ] **Team:** choose a code licence (proposal: MIT) — needed for NFR-7.
- [ ] **Team (P4):** label 600 reference points on the Labelling page (two interpreters + one
      adjudicator).
- [ ] **Guide:** confirm OI-4 (HPC node type, GPU hours, NFR-1 budget) and OI-10 (Table 16
      targets); witness the FR-C2, FR-R1 and FR-V1 demos.
- [ ] **Team (P4):** recruit 5 non-team testers for NFR-6.
- [ ] **Optional (P5):** a Gmail app password for e-mail alerts; until then alerts go to
      `data/outbox/`.
- [ ] **Team:** share the team presentation so OI-9 (architecture / work-plan reconciliation) can
      be closed.

## Execution rulings

- P0 T3: synthetic grid bounds changed to [300000, 2899980, 306000, 2905980] so the northing is a multiple of 30 m (keeps 200x200) — cost if wrong: none.
- P0 T4: small_grid fixture bounds -> (300000, 2900010, 300120, 2900100) so it really is 4x3 (same 30 m multiple issue) — cost if wrong: none.

## Session log

| Date | Who | Summary |
|---|---|---|
| 2026-10-25 | Samarth + Claude | P0 bootstrap executed (10 tasks, 57 tests) |
| 2026-10-25 | Samarth + Claude | Read SRS and problem statement; brainstormed; approved design; wrote spec, CLAUDE.md and docs |
