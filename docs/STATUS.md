# DAIFF — Build Status

_Last updated: 2026-10-25 — Samarth's machine (Claude session)_

## Now

- **Phase:** P0 Bootstrap — not started
- **Last done:** Brainstorming finished; design approved. Written: system spec, CLAUDE.md,
  requirement register, problem statement, decisions log, this file.
- **Next task:** Get the written spec reviewed by Samarth, then write the P0 plan at
  `docs/superpowers/plans/2026-10-25-p0-bootstrap.md` and execute it task by task.
- **Blockers:** none for P0–P2. P3 onward needs Earth Engine registration.
- **Remote:** https://github.com/SamarthKale/DAIFF-Flood-Risk-Prediction (public, `main`)
- **CI:** not set up yet.

## Phases

| Phase | Scope | Plan | Status |
|---|---|---|---|
| P0 Bootstrap | env, CI, config, grid, store, runner, synthetic skeleton, GEE setup guide | — | not started |
| P1 Science core | terrain, forest, coupling, flood model, tables, flags, run/watch (synthetic) | — | not started |
| P2 API + dashboard | FastAPI + React/MapLibre, exports, labelling page (synthetic) | — | not started |
| P3 Kopili ingestion | GEE: AOI, S2 + RF, S1 floods, references, rainfall, rivers, event inventory | — | not started |
| P4 Tier 1 acceptance | real runs, validation, U-Net challenger, NFR checks, test log | — | not started |
| P5 Tier 2 | monthly forest, rainfall risk, what-if, alerts | — | not started |
| P6 Tier 3 | SAR–optical fusion, 1–7 day forecaster (Colab) | — | not started |
| P7 Close-out | verification matrix, docs, handover | — | not started |

## Waiting on humans

- [x] **Samarth:** create the public GitHub repository — done:
      `SamarthKale/DAIFF-Flood-Risk-Prediction`.
- [ ] **Every teammate:** register a free non-commercial Google Earth Engine project (steps will
      be in `docs/setup/gee.md`, written in P0), put the project ID in `.env`, and run
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

## Session log

| Date | Who | Summary |
|---|---|---|
| 2026-10-25 | Samarth + Claude | Read SRS and problem statement; brainstormed; approved design; wrote spec, CLAUDE.md and docs |
