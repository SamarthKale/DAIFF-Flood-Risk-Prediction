# Test Log (SRS 8.3)

Rules:
- **Acceptance entries** use Kopili data, the frozen test sets of SRS chapter 7, and record the
  config, `run_id` and code commit. Analysis results come from committed scripts
  (`daiff validate`), never hand calculations.
- **Dev checks** on the synthetic basin are allowed but must be marked "dev check — not acceptance".
- Add rows at the bottom; never edit past rows. `daiff validate` appends rows automatically.

| Date | Requirement | Method | Config / run_id / commit | Result | Evidence | By |
|---|---|---|---|---|---|---|
| 2026-10-25 | FR-D5 | T | synthetic.yaml / – / e940162 | PASS — dev check, not acceptance | `daiff check-grid`: "FR-D5 PASS: 15 layers aligned" | Claude (Samarth's session) |
| 2026-10-25 | FR-R2 | A | synthetic / 145aa28c8070 / 3ac12ffcc4d2 | PASS: AUC 0.999 (HAND 0.709); flooded in 4-5 0.98, area 0.11 — dev check, not acceptance | metrics/flood.json | daiff validate |
| 2026-10-25 | FR-R3 | A | synthetic / 145aa28c8070 / 3ac12ffcc4d2 | PASS: ablation dAUC 0.002 [0.002, 0.003] — dev check, not acceptance | metrics/flood.json | daiff validate |
| 2026-10-25 | NFR-2 | T | synthetic / 145aa28c8070 / 3ac12ff | PASS: 1->2 workers 42% less time (laptop) — dev check, not acceptance | docs/perf/ | daiff bench |
| 2026-10-25 | NFR-5 | T | synthetic / 145aa28c8070 | PASS server-side: 5 tiles 0.13-0.20 s, table 0.13 s — dev check, not acceptance | docs/perf/2026-10-25-nfr5.md | scripts/nfr5_timing.py |
| 2026-10-25 | FR-D3 | T | kopili / raw ingest / 604c825 | PASS: NOAA CPC 401,513 and CHIRPS 400,570 sub-basin-days (41 sub-basins, 2000-01-01..2026), 0 gaps > 3 days | data/kopili/raw/rainfall/gaps_cpc.csv; find_gaps on CHIRPS | daiff gee ingest --steps cpc,chirps |
