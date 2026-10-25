# Parallel work packages (started 2026-10-25)

Samarth's session is doing **P3 — Kopili ingestion with Earth Engine** (live). Three teammates can
work at the same time on the packages below. They use only the **synthetic basin**, so no Earth
Engine account is needed to start (but please register anyway — `docs/setup/gee.md` — P4 needs it).

## Rules for working in parallel

1. **Setup:** `git clone https://github.com/SamarthKale/DAIFF-Flood-Risk-Prediction.git`,
   `uv sync --extra dev`, then `uv run daiff synth -c configs/synthetic.yaml` and
   `uv run daiff run -c configs/synthetic.yaml`. `cd web && npm ci` if your package touches the UI.
2. **Read** `CLAUDE.md`, this file, then your package's section in
   `docs/superpowers/plans/2026-10-25-p4-p7-acceptance-tier2-tier3-closeout.md`.
   That plan is an outline: **first** refine your tasks into test-first steps in that file (only your
   section), commit, then build.
3. **Stay in your lane.** Only edit the files your package owns (below). Do **not** edit
   `src/daiff/gee/*`, `src/daiff/ingest/*`, `configs/kopili.yaml`, `reference/flood_events_kopili.csv`
   (owned by the P3 session).
4. **Shared files** (`src/daiff/cli.py`, `src/daiff/api/app.py`, `web/src/App.tsx`, `pyproject.toml`,
   `docs/verification_matrix.md`, `docs/STATUS.md`): keep edits tiny (one import + one line to
   register your command/router/route), and always `git pull --rebase` right before you commit.
   New CLI commands go in a typer sub-app inside your own module, registered with one line in `cli.py`.
5. **Commit small and push often** (`git pull --rebase && git push origin main`). On a rebase conflict
   in a shared file, keep both sides. No AI co-author trailers. CI is non-blocking.
6. **STATUS.md:** add/update only your own line under "Parallel packages" below the "Now" section.

---

## Package A — Tier 2 rainfall alerts (FR-R4, FR-A2, OI-8)

**Owner:** teammate 1 · **Owns:** `src/daiff/alerts/thresholds.py`, `src/daiff/alerts/engine.py`,
`src/daiff/alerts/notify.py`, `src/daiff/alerts/store.py`, `src/daiff/flood/rainfall_risk.py`,
`src/daiff/api/routers/alerts.py`, `web/src/pages/AlertsPage.tsx`, `tests/alerts/*`.

Build (spec §6.10 FR-R4, §6.12; plan P5.2 + P5.4):
- `wet_day_percentile(daily, q=99, wet_mm=1.0) -> pd.Series` per sub-basin (OI-8).
- `classify_subbasin_day(rain_mm, threshold, high_share) -> int` and `pod_far(pred, truth) -> dict`.
- Alert store `data/alerts.sqlite` (schema in the plan), `AlertEngine.poll(now)` with a pluggable
  rainfall source (synthetic CSV source now; GPM/GFS source added later by P3/P5 with Earth Engine).
- Notifier: SMTP+TLS from `SMTP_*` env vars; fallback writes `.eml` files to `data/outbox/`.
- `daiff alerts replay --event <id>` on synthetic events: alert issued ≤ 1 h after the day's rainfall
  becomes available (FR-A2 acceptance), `GET /api/alerts`, and an Alerts page (sub-basin, rainfall,
  time) with a nav link.
**Done when:** tests pass for thresholds, classification, POD/FAR, engine replay and the API;
verification-matrix rows FR-R4/FR-A2 → "passing (synthetic)".

## Package B — What-if scenarios + monthly forest (FR-R5, FR-F5)

**Owner:** teammate 2 · **Owns:** `src/daiff/flood/scenario.py`, `src/daiff/api/routers/scenarios.py`,
`web/src/components/ScenarioPanel.tsx`, `src/daiff/forest/monthly.py`, `tests/flood/test_scenario.py`,
`tests/forest/test_monthly.py`.

Build (spec §6.10 FR-R5; plan P5.1 + P5.3):
- `run_scenario(cfg, subbasin_id, extra_loss_pct, year) -> Path`: reduce forest fraction by
  `extra_loss_pct` of the remaining forest in that sub-basin, recompute dF/CN/Q there and U globally
  (reuse `daiff.coupling.features`, `daiff.terrain.flow`), predict with the published model
  (`daiff.flood.predict`), write `data/<project>/scenarios/<hash>/delta_s.tif`.
  Must be monotone (ΔS ≥ 0 everywhere) and finish **< 5 minutes** (time it on synthetic; scale note
  for Kopili's ~22 M cells: predict only the sub-basin + downstream cells).
- `POST /api/scenarios` → scenario id; tiles for the scenario ΔS; a Scenario panel on the Map page.
- Monthly forest (FR-F5): the comparison/report part only — `monthly_vs_annual_f1(monthly_maps,
  annual_map, reference) -> dict`; the Earth Engine monthly composites come later from P3.
**Done when:** tests pass (monotone ΔS, sub-basin+downstream only, timing logged in `docs/perf/`).

## Package C — Deep-learning model code for Colab (U-Net challenger + Tier 3)

**Owner:** teammate 3 · **Owns:** `src/daiff/forest/unet.py`, `src/daiff/research/*`,
`notebooks/colab/*`, `tests/research/*`, `tests/forest/test_unet.py`; adds the optional extra
`dl = ["torch>=2.4"]` to `pyproject.toml` (CPU build locally — **never use the local GPU**).

Build (spec §6.8 U-Net, §6.15; plan P4.3, P6.1, P6.2):
- `forest/unet.py`: small U-Net (4 levels, ~2 M params, 12 input bands, 2 classes); chip dataset
  reading `.npz` chips; training loop with checkpointing; `predict_tiles()`.
- `research/fusion.py`: two-branch S1+S2 CNN; `research/forecaster.py`: transformer encoder
  (≤ 1 M params) for 1–7 day flooded-fraction forecasts with persistence/climatology baselines.
- Synthetic chip/sequence generators so every model has a CPU unit test on tiny tensors
  (forward shape, one training step lowers loss, save/load round-trip).
- Colab notebooks (`unet_train.ipynb`, `fusion_train.ipynb`, `forecaster_train.ipynb`): install the
  package from GitHub at a pinned commit, mount Drive, train with Drive checkpoints. Real chips
  come from P3/P4 Earth Engine exports later.
**Done when:** CPU tests pass locally and in CI (mark anything GPU-only `@pytest.mark.colab`);
notebooks run end to end on Colab with synthetic chips.

## Also useful for anyone (no code)

- **Flood-event dates (OI-5):** confirm exact Kopili flood dates for 2017, 2019, 2020, 2023 from
  ASDMA daily flood reports / CWC bulletins / news; send them to Samarth (don't edit the CSV
  directly while P3 is running).
- **Earth Engine registration** for every teammate (`docs/setup/gee.md`, choose the free
  "Community" tier).
