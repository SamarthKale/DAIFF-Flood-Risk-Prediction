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
