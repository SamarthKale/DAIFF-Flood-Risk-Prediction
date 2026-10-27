# NFR-6 user test protocol (human-only: 5 non-team testers)

**Criterion (SRS NFR-6):** 5 non-team users each complete the three tasks below without help.
Record results in `docs/test_log.md` (never fabricate them).

Setup: run `uv run daiff serve -c configs/kopili.yaml`, open http://localhost:8000 on a laptop
(or the demo machine). Do not explain the page; read each task aloud and start a timer.

| # | Task | Done when | Max time |
|---|---|---|---|
| 1 | Find where forest loss since 2018 is highest | Tester names a sub-basin from the Sub-basins page or the loss layer | 3 min |
| 2 | Find the flood risk class at a place they choose and what drives it | Tester clicks the map and reads the class and top drivers | 3 min |
| 3 | Download the sub-basin table for one year | A CSV is saved | 2 min |

Record per tester: name or ID, role (not team), task times, pass/fail, where they hesitated, and
anything they misread. Ask: "Did you notice this is experimental decision support?" (NFR-8).
