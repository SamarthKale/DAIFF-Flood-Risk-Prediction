# CLAUDE.md — DAIFF

**DAIFF** — AI-Based Deforestation Monitoring and Flood Risk Prediction (HPC Research Internship,
Problem Statement 3). Sentinel-2 forest change → coupling features C1–C3 → flood-susceptibility
model → dashboard and alerts, for the **Kopili basin, Assam**.

Sources of truth, in order:
1. [`docs/srs/requirements.md`](docs/srs/requirements.md) — every requirement ID (FR-*, NFR-*) with
   its acceptance criterion. Never weaken a criterion. If one cannot be met, log why in
   `docs/decisions.md`.
2. [`docs/superpowers/specs/2026-10-25-daiff-system-design.md`](docs/superpowers/specs/2026-10-25-daiff-system-design.md)
   — architecture, interfaces, conventions. It wins over this file on conflict.
3. [`docs/STATUS.md`](docs/STATUS.md) — where the build is right now and what comes next.

## Session protocol (mandatory — the build is a relay between teammates)

This project is built continuously by several people's Claude sessions; any session may end
without warning (usage limits). The repository must always say exactly where things stand.

- **Start:** `git pull --rebase` → read this file → `docs/STATUS.md` → the active plan in
  `docs/superpowers/plans/` → continue from the first unchecked task. Do not redo checked tasks.
- **Work:** one plan task = one test-first cycle (failing test → minimal code → passing test) =
  one commit. If a task is long, make `wip:` commits so little is lost if the session dies.
- **End of every task:** tick its checkbox in the plan → update `docs/STATUS.md` (last done, next
  task, blockers, CI note) → commit → `git push origin main`.
- **No plan for the current phase yet?** Write it first (superpowers `writing-plans` skill if
  installed; otherwise copy the structure of an existing plan), commit it, then execute.
- **Several people at once?** Follow `docs/PARALLEL_WORK.md`: work only in your package's files,
  `git pull --rebase` before every commit, keep shared-file edits to one-line registrations.
- **Ending a session deliberately:** make sure STATUS.md's "Next task" is precise enough for a
  stranger to continue.

## Hard rules

- **Commits:** conventional messages (`feat(coupling): …`, `fix(api): …`, `test: …`, `docs: …`,
  `wip: …`). **Never add AI co-author trailers** (`Co-Authored-By: Claude …`) or "Generated with
  Claude Code" lines — not in commits, not in PRs, on any machine. Never change git `user.name` or
  `user.email`.
- **Push to `main` after every completed task without asking.** Trunk-based; no feature branches.
- **CI is non-blocking.** Never wait for CI, and never stop because CI is red. Note the failure in
  STATUS.md and fix it later. Local tests for the code you changed must still pass before you commit.
- **Free only.** Open data, open-source libraries, free tiers. No paid APIs, cloud billing or
  hosting.
- **Never use the local GPU.** Do not install CUDA builds or train on the local GPU. Local PyTorch is
  CPU-only (tiny tests). All GPU work runs on Google Colab notebooks in `notebooks/colab/`.
- **Never commit** `data/`, `.env`, credentials, tokens, or large binaries. Small irreplaceable files
  (reference labels, flood-event inventory, sub-basin names) live in `reference/` and are committed.
- **No machine-specific paths** (`D:\…`, `/home/…`) in code, config or tests. Use config and
  `DAIFF_DATA_ROOT`.
- **Traceability:** name tests `test_<req>_<behaviour>` (e.g.
  `test_fr_c1_upstream_loss_matches_hand_computed`). Keep `docs/verification_matrix.md` current.
- **Coupling is the only bridge** from forest outputs to the flood model (SRS 3.1). Never feed forest
  rasters to the flood model any other way.
- **Human-only work is never faked**: Earth Engine sign-up, labelling the 600 reference points,
  guide sign-offs, the NFR-6 user test. List them under "Waiting on humans" in STATUS.md.
- **Every decision that interprets or deviates from the SRS** goes in `docs/decisions.md` (D-xx,
  OI-x status).

## Decisions so far (full log: `docs/decisions.md`)

| Topic | Decision |
|---|---|
| Data | Google Earth Engine (free non-commercial project); products exported as EE assets, downloaded with `getPixels` |
| Basin | Kopili, Assam; EPSG:32646 (UTM 46N); HydroBASINS sub-basins |
| Scope | All tiers, in order (Tier 1 → 2 → 3) |
| Compute | Laptop CPU now; SLURM-ready via dask-jobqueue; GPU only on Colab |
| Forest | Random Forest in GEE (primary), U-Net on Colab (challenger) |
| Flood | XGBoost, monotone (+ΔF, +U, +CN, +Q, −f); fixed breaks 0.2/0.4/0.6/0.8 until OI-7 |
| Dashboard | FastAPI + rio-tiler; React + TypeScript + Vite + MapLibre GL |
| Repo | Public GitHub, `main` only, push per task, CI non-blocking |
| Python | 3.12, uv, `.venv`, link-mode copy |

## Architecture in one paragraph

GEE does the pixel work: S2 dry-season composites, Random-Forest forest/non-forest at 10 m,
Sentinel-1 flood masks (Otsu) and clipped reference layers. These are exported as EE assets and
downloaded in tiles onto the common grid in `data/raw/`. Local CPU Python (`src/daiff/`) does
terrain (numba D8/HAND), forest loss + MMU, coupling C1–C3, XGBoost susceptibility, ΔS, sub-basin
tables, flags, validation, and publishes to `data/store/<run_id>/` with Appendix C file names, with
`data/store/CURRENT` naming the published run. FastAPI (`daiff serve`) reads only the published
run; the React app lives in `web/`. Colab runs the U-Net and Tier 3 via Google Drive. The synthetic
basin (`configs/synthetic.yaml`) runs the whole local pipeline without GEE — use it for tests, CI,
demos and dashboard work.

## Layout (details in the spec §4)

`configs/` · `src/daiff/{config,grid,store,pipeline,gee,ingest,terrain,forest,coupling,flood,validation,alerts,api,research}` ·
`web/` · `notebooks/colab/` · `hpc/slurm/` · `tests/` · `reference/` · `docs/` · `data/` (gitignored)

## Commands (target interface — created in P0/P1; check STATUS.md if one is missing)

```bash
uv sync --extra dev                           # create .venv (Python 3.12)
uv run pytest -m "not gee and not slow"       # fast test suite
uv run ruff check . && uv run ruff format .   # lint + format
uv run daiff run -c configs/synthetic.yaml    # full local pipeline on the fake basin (no GEE)
uv run daiff run -c configs/kopili.yaml       # real pipeline (needs GEE + .env)
uv run daiff watch -c configs/kopili.yaml     # FR-C2: auto re-run when a new forest map appears
uv run daiff validate -c configs/kopili.yaml --what flood
uv run daiff check-grid -c configs/kopili.yaml      # FR-D5
uv run daiff check-metadata -c configs/kopili.yaml  # NFR-4
uv run daiff serve -c configs/synthetic.yaml  # API on http://localhost:8000
cd web && npm ci && npm run dev               # dashboard on http://localhost:5173
```

## Conventions

- **Grid:** EPSG:32646, 30 m cells, origin on multiples of 30 m; 10 m pixels nest 3×3 per cell.
  Resample only during ingestion; readers raise on misalignment.
- **Years:** forest map *t* = dry season 1 Nov (t−1) – 31 Mar t. A flood in the monsoon of year Y
  pairs with forest map Y. t₀ comes from config, set by rule D-24 (2018, or 2019 if S2 L2A
  coverage of the 2017/2018 dry seasons is below 90%).
- **Nodata:** float32 → NaN; uint8 classes → 255. Permanent water (JRC > 90%) excluded from flood
  labels.
- **Rasters:** COG (DEFLATE, 512 blocks, overviews) with `DAIFF_*` provenance tags and no
  timestamps in tags, so runs are byte-reproducible. Timings go to `run_metadata.json` and
  `docs/perf/`.
- **Config:** pydantic models over YAML in `configs/`. Secrets and machine settings go in `.env`
  (`DAIFF_GEE_PROJECT`, `DAIFF_DATA_ROOT`, `SMTP_*`). Seeds are fixed in config.
- **Python:** 3.12, type hints, ruff, small focused modules, numba for grid algorithms, no
  notebooks in `src/`.
- **Tests:** pytest; markers `gee` (live Earth Engine, off by default), `slow`, `colab`. Use the
  synthetic basin for anything end to end.
- **Web:** TypeScript strict, function components, Vitest; the API base URL comes from env.

## Where things live

- **Git (GitHub):** code, docs, configs, tests, `reference/`. 
- **`data/` (NOT in git, ~7 GB for Kopili):** raw downloads, run outputs, models. Back it up
  (copy the folder) before changing machines; regenerating costs Earth Engine quota.
- **Per machine:** Earth Engine login (`~/.config/earthengine`), `.env` (your project ID), `.venv`.
- **Earth Engine quota** (Community: 150 EECU-h/month): measure cost on one sub-basin before any
  full-basin job. Never use `stratifiedSample` over the whole basin (D-29).

## Machine notes

- On Samarth's laptop the repo lives on an **exFAT external drive (D:)**. Git needs
  `git config --global --add safe.directory D:/HPC` (already set). uv uses `link-mode = "copy"`
  (set in `pyproject.toml`). Always use "Safely Remove" before unplugging.
- Windows shells: the Bash tool is Git Bash; PowerShell is also available. Use forward slashes in
  code.
- **New teammate machine:** `git clone` → `uv sync --extra dev` → copy `.env.example` to `.env` and
  fill in your own Earth Engine project → `earthengine authenticate` (you run this yourself) →
  read STATUS.md.
