# P3 Kopili Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. CLAUDE.md protocol applies. **Needs a registered Earth Engine project** in `.env` (`DAIFF_GEE_PROJECT`) and `earthengine authenticate` done by the human. Live-GEE tests carry `@pytest.mark.gee`.

**Goal:** Produce the real Kopili raw layout (exactly P0's `RawLayout`: grid.json, dem, hsg, jrc,
forest10m per year, dw_class per year, CHIRPS sub-basin CSV, sub-basins, flood events + masks) from
Earth Engine and NOAA, satisfying FR-D1–FR-D5, so `daiff run -c configs/kopili.yaml` works unchanged.

**Architecture:** `daiff.gee` builds `ee.Image`s with pure, unit-testable parameter helpers; heavy
images are exported as EE assets (batch) and downloaded with `ee.data.getPixels` tiles onto the grid
(D-10). Non-GEE sources (NOAA CPC, OSM) in `daiff.ingest`.

**Tech Stack:** earthengine-api, requests, xarray + netCDF4 (CPC), shapely, rasterio.

**Spec:** §6.5, §6.6, §7, decisions D-10, D-12, D-14, D-16, D-18, D-24.

## Global Constraints

- Pinned dataset IDs live in `configs/kopili.yaml → gee.datasets` (S2 `COPERNICUS/S2_SR_HARMONIZED`, S1 `COPERNICUS/S1_GRD`, SRTM `USGS/SRTMGL1_003`, Hansen `UMD/hansen/global_forest_change_2024_v1_12` or latest available, JRC `JRC/GSW1_4/GlobalSurfaceWater`, GFD `GLOBAL_FLOOD_DB/MODIS_EVENTS/V1`, CHIRPS `UCSB-CHG/CHIRPS/DAILY`, DW `GOOGLE/DYNAMICWORLD/V1`, WorldCover `ESA/WorldCover/v200`, HydroBASINS `WWF/HydroSHEDS/v1/Basins/hybas_<level>`, HYSOGs asset ID verified at Task 4).
- SCL mask removes classes 0, 1, 3, 8, 9, 10. Dry season Nov(t−1)–Mar(t).
- All downloads snap to the grid (`crsTransform` = grid transform; 10 m for forest10m).
- Asset root: `projects/<DAIFF_GEE_PROJECT>/assets/daiff/<asset_version>/`.
- Every downloaded raster records `DAIFF_SOURCE` (dataset ID + version) and `DAIFF_ASSET` tags.

## Review Focus

1. **Auth missing/expired** — any `daiff gee …` command prints the fix and points to `docs/setup/gee.md` (exit 3), no traceback; Task 1.
2. **getPixels tile at the grid edge** — partial tiles mosaic without seams or off-by-one; Task 2 (offline test with a fake fetcher).
3. **Re-running an export that already exists** — idempotent skip, no duplicate EE tasks; Task 2.
4. **Year with < 90% clear L2A coverage** — reported, gaps filled from the previous year, residual gap share in the FR-D2 report; Task 5.
5. **Event whose S1 window has no scene** — marked `usable = false` with reason, never silently dropped; Task 7.

---

### Task 1: GEE auth and `daiff gee check`
`src/daiff/gee/auth.py`: `init_ee(cfg) -> None` (raises `GeeAuthError` with guidance). CLI `daiff gee check -c CFG` prints project + `ee.Number(1).add(1).getInfo()`. Offline test: monkeypatched `ee.Initialize` raising → exit 3 and message contains `docs/setup/gee.md`. Live `gee` test: returns 2.

### Task 2: Export and tiled download machinery
`src/daiff/gee/export.py`: `asset_id(cfg, name) -> str`; `submit_asset_export(image, name, grid, cfg) -> str | None` (skip if asset exists); `wait_for_tasks(ids, poll_s=30)`; `tile_windows(grid, tile=2048) -> list[Window]`; `download_asset(asset, grid, path, *, fetch=getpixels_fetch, tile=2048, dtype, nodata)` mosaics tiles into a COG via `write_cog`. Offline tests with a fake `fetch` returning known arrays: mosaic equals expected for a 5000×3000 grid (edge tiles, Review 2); second call skips (Review 3).

### Task 3: AOI, grid and sub-basins (OI-1, FR-D5)
`src/daiff/gee/aoi.py`: Kopili outlet point (config `project.outlet_lonlat`, set from the Kopili–Brahmaputra confluence near Jagiroad, ~92.12°E 26.2°N — verify on the map), select HydroBASINS level-`project.subbasin_level` polygons whose `NEXT_DOWN` chain reaches the outlet basin; export union as AOI and members as `raw/subbasins.geojson` (`subbasin_id = HYBAS_ID`). Write grid bounds (AOI bounds + 1 km) to `raw/grid.json` and print them for `configs/kopili.yaml → grid.bounds`. Choose level giving 20–60 sub-basins; record area (km²) and count in `docs/decisions.md` (close OI-1 detail). `src/daiff/ingest/names.py` builds `reference/subbasin_names_kopili.csv` suggestions from OSM river names (Task 8) — human edits.

### Task 4: Static reference layers
`src/daiff/gee/refdata.py`: `dem_image` (SRTM bilinear), `hsg_image` (HYSOGs → 1–4, duals → 4 per D-23), `jrc_image`, `hansen_images` (treecover2000, lossyear), `dw_mode_image(year)` (dry-season mode label), `worldcover_image`. Export + download into `RawLayout` (+ `raw/hansen_treecover2000.tif`, `raw/hansen_lossyear.tif`, `raw/worldcover.tif`). Unit tests on HSG remap table and band selection; live `gee` test on a 2×2 km box.

### Task 5: Sentinel-2 composites, inventory, t₀ check (FR-D1, FR-D2, OI-2)
`src/daiff/gee/s2.py`: `season_window(year) -> (start, end)` (D-18); `masked_collection(aoi, year)`; `composite(year)` (median + NDVI + NBR); `s2_inventory(year) -> pd.DataFrame` (scene id, MGRS tile, date, cloud %) → `raw/s2_inventory_<year>.csv` and FR-D1 comparison vs. a plain catalogue query; `coverage_fraction(year) -> float`. `daiff gee t0-check` applies D-24 and writes the decision to `docs/decisions.md`. `preview_<year>` (30 m RGB uint8) exported for the dashboard. FR-D2 report `raw/fr_d2_<year>.json` (gap share; list of 20 random 1 km windows as lon/lat for the visual check — the visual check itself is human, logged in the test log). Unit tests: season windows, SCL class list.

### Task 6: Random-forest forest classification (FR-F1 inputs)
`src/daiff/gee/forest_rf.py`: `training_points(year)` per spec §6.5 (Hansen ∧ DW agreement), pooled across years, 5000/class/year, seeded; `classifier()` = `smileRandomForest(300, seed)`; `classify(year)` → 10 m uint8 with gap-fill from previous year; export + download `forest10m_<year>.tif` on the 10 m nested grid. Record classifier id (hash of params + training-point asset) in raw tags (`DAIFF_SOURCE=forest:gee-rf-<id>`). Unit tests on label rules expressed as pure functions over numbers (thresholds 30/10, DW 0.6/0.2).

### Task 7: Flood-event inventory and Sentinel-1 flood maps (OI-5)
`reference/flood_events.csv` researched from DFO, ReliefWeb, ASDMA daily reports, Copernicus EMS (Claude does web research; every row cites sources). `src/daiff/gee/s1_flood.py`: `event_windows(row)`; `flood_fraction(event)` (pre median VV, event min VV, 50 m focal mean, Otsu on difference within AOI, exclude JRC>90 and slope>5°, 10 m → 30 m fraction); `otsu_threshold(hist_counts, bin_edges) -> float` pure function (unit-tested on a bimodal histogram). Events without S1 coverage → `usable=false, reason` (Review 5). GFD/EMS agreement metric where available → `raw/flood_label_checks.csv`. ≥ 6 usable events or log the shortfall in decisions.

### Task 8: Rainfall (FR-D3) and rivers (FR-D4)
`src/daiff/ingest/rainfall.py`: CHIRPS daily sub-basin means via `reduceRegions` per year → `raw/rainfall/chirps_subbasin_daily.csv`; NOAA CPC Global Unified daily NetCDF (`https://downloads.psl.noaa.gov/Datasets/cpc_global_precip/precip.<year>.nc`, 2000–present) cached in `raw/cpc/`, area-weighted to sub-basins → `raw/rainfall/cpc_subbasin_daily.csv`; `gaps(df, max_gap_days=3) -> DataFrame` → `raw/rainfall/gaps.csv`. `src/daiff/ingest/rivers.py`: Overpass query for `waterway=river|canal` in AOI bbox → `raw/osm_rivers.gpkg`; `daiff check-streams` = share of derived major-stream length within 60 m of OSM rivers (≥ 0.90). Unit tests: gap finder; area weights sum to 1; stream-distance metric on a synthetic line pair.

### Task 9: `daiff gee ingest` orchestration and P3 close-out
One command running Tasks 3–8 in order with idempotent skips; then `daiff check-grid -c configs/kopili.yaml` (FR-D5) and `daiff run -c configs/kopili.yaml --stages terrain,forest` smoke. Update test log (FR-D1–D5 results with evidence files), verification matrix, decisions (OI-1, OI-2, OI-5), STATUS → P4. Commit + push.
