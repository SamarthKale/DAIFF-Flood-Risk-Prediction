# Licences (NFR-7)

Only openly licensed data and open-source software are used. To be reviewed and accepted by the
project guide. Update this file in the same commit that adds a dataset or dependency.

**Project code licence:** pending team decision (proposal: MIT).

## Data

| Dataset | Access | Licence |
|---|---|---|
| Sentinel-2 L2A | GEE `COPERNICUS/S2_SR_HARMONIZED` | Copernicus open licence |
| Sentinel-1 GRD | GEE `COPERNICUS/S1_GRD` | Copernicus open licence |
| SRTM 1″ | GEE `USGS/SRTMGL1_003` | Public domain |
| Hansen Global Forest Change | GEE `UMD/hansen/global_forest_change_*` | CC BY 4.0 |
| JRC Global Surface Water | GEE `JRC/GSW1_4/GlobalSurfaceWater` | Copernicus open licence |
| Global Flood Database | GEE `GLOBAL_FLOOD_DB/MODIS_EVENTS/V1` | CC BY-NC 4.0 |
| CHIRPS daily | GEE `UCSB-CHG/CHIRPS/DAILY` | CC0 |
| NOAA CPC Global Unified Precipitation | NOAA PSL | Public domain |
| Dynamic World | GEE `GOOGLE/DYNAMICWORLD/V1` | CC BY 4.0 |
| ESA WorldCover | GEE `ESA/WorldCover/v200` | CC BY 4.0 |
| HydroBASINS | GEE `WWF/HydroSHEDS/v1/Basins/hybas_*` | HydroSHEDS licence (free, attribution) |
| HYSOGs250m | ORNL DAAC | Open, attribution |
| OpenStreetMap | Overpass API | ODbL |
| DFO, ReliefWeb, ASDMA, Copernicus EMS, NRSC Bhuvan | Web | Public reports |

## Python libraries

| Library | Licence |
|---|---|
| numpy | BSD-3-Clause |
| pandas | BSD-3-Clause |
| rasterio (with bundled GDAL, MIT/X) | BSD-3-Clause |
| pydantic | MIT |
| PyYAML | MIT |
| typer | MIT |
| python-dotenv | BSD-3-Clause |
| earthengine-api | Apache-2.0 |
| numba | BSD-2-Clause |
| scipy | BSD-3-Clause |
| scikit-learn | BSD-3-Clause |
| xgboost | Apache-2.0 |
| pyarrow | Apache-2.0 |
| dask, distributed | BSD-3-Clause |
| dask-jobqueue (optional, HPC) | BSD-3-Clause |
| fastapi | MIT |
| uvicorn | BSD-3-Clause |
| rio-tiler | BSD-3-Clause |
| httpx, pillow (tests) | BSD-3-Clause, MIT-CMU (HPND) |

## Web dashboard (npm)

| Library | Licence |
|---|---|
| react, react-dom | MIT |
| react-router-dom | MIT |
| maplibre-gl | BSD-3-Clause |
| @tanstack/react-table | MIT |
| recharts | MIT |
| vite, vitest, typescript | MIT / Apache-2.0 (typescript) |
| @testing-library/* | MIT |

## Map tiles shown in the dashboard

| Tiles | Terms |
|---|---|
| OpenStreetMap standard tiles (basemap) | ODbL data; OSM tile usage policy (attribution, light use) |
| Esri World Imagery (Labelling page only) | Esri terms of use, attribution required; non-commercial reference viewing |
| pytest, pytest-cov | MIT |
| ruff | MIT |
| hatchling (build) | MIT |
