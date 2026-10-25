# DAIFF demo script (about 10 minutes)

Works offline except for the basemap. Use the **synthetic** basin if the Kopili run is not ready;
both use the same commands with a different config.

## 0. Before the demo (once)

```bash
uv sync --extra dev
cd web && npm ci && npm run build && cd ..      # build the dashboard (once)
uv run daiff synth -c configs/synthetic.yaml    # fake basin, ~20 s
uv run daiff run -c configs/synthetic.yaml      # full pipeline, ~1 min
```

Real data: `data/kopili/` must exist (it is not in git — copy the folder; see "Where the data lives").
Then `uv run daiff run -c configs/kopili.yaml` (about 30-40 min the first time).

## 1. The plan (1 min)
GitHub repo → `docs/srs/requirements.md` (every FR/NFR), `docs/verification_matrix.md` (status of
each), `docs/superpowers/specs/…design.md`, `docs/test_log.md` (what was actually run).

## 2. Real Earth Engine data (2 min)
Open in QGIS (or show screenshots): `data/kopili/raw/` — 41 sub-basins (`subbasins.geojson`),
10 m forest maps (`forest10m/forest10m_2018.tif` vs `…_2026.tif`), a Sentinel-1 flood map
(`floods/flood_kop_2022_06.tif`), land cover (`dw_class/`). Rainfall: `rainfall/*.csv`, 26 years.

## 3. The pipeline in one command (2 min)

```bash
uv run daiff run -c configs/synthetic.yaml
uv run daiff validate -c configs/synthetic.yaml --what flood
uv run daiff check-metadata -c configs/synthetic.yaml
```

Chain: terrain → forest loss → coupling C1–C3 → monotone flood model → ΔS → sub-basin tables/flags.
`validate` prints AUC vs the HAND baseline and the coupling ablation.

## 4. The dashboard (4 min)

```bash
uv run daiff serve -c configs/kopili.yaml        # or configs/synthetic.yaml
```

Open http://localhost:8000
- **Map:** switch layer and year; banner "Experimental decision support" (NFR-8); legend; opacity.
- **Click a land point:** forest fraction over time, susceptibility, risk class, ΔS, top 3 drivers.
- **Sub-basins:** sort by forest loss, search by name, download CSV / GeoTIFF.
- **Validation:** AUC, HAND baseline, per-event AUC, ablation, feature importance.
- **Labelling:** how the 600 reference points get labelled (two interpreters + adjudicator).

## 5. Honest status (1 min)
Passing on real Kopili data: FR-D2 (gaps), FR-D3, FR-D5. **FR-D4 fails (67.6 % vs 90 %, OI-11); FR-D2 visual 2018 fails (OI-13); flood AUC 0.762 vs 0.80 (OI-12)** —
needs the guide. Tier 1 accuracy (FR-F1/F2/R2) waits for the hand-labelled points (P4).
Tier 2 and Tier 3 are packaged for teammates in `docs/PARALLEL_WORK.md`.

## If something breaks
- Dashboard blank map: wait 5 s (basemap tiles), or refresh.
- "No published run": run `daiff run -c <config>` first.
- "Earth Engine login failed": only the ingest commands need it, not the demo.
- Port busy: `daiff serve -c <config> --port 8001`.

## Where the data lives
Code is on GitHub. **Data is only on this laptop's D: drive** (`D:\HPC\data`, ~7 GB, git-ignored).
Back it up before moving machines: copy `D:\HPC\data` to another drive or Google Drive.
Earth Engine login is in `C:\Users\<you>\.config\earthengine` (per machine; re-run
`uv run earthengine authenticate`).
