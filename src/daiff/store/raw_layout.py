"""Paths of raw inputs. The synthetic generator (P0) and the GEE stage (P3) write exactly this."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from daiff.grid import Grid

NESTED_FACTOR = 3


class RawLayout:
    def __init__(self, data_root: Path) -> None:
        self.data_root = Path(data_root)
        self.root = self.data_root / "raw"

    @property
    def grid_json(self) -> Path:
        return self.root / "grid.json"

    @property
    def dem(self) -> Path:
        return self.root / "dem.tif"

    @property
    def dem_hydro(self) -> Path:
        """Hydrologically conditioned elevation for flow routing (MERIT Hydro, D-30)."""
        return self.root / "dem_merit_hydro.tif"

    @property
    def hsg(self) -> Path:
        return self.root / "hsg.tif"

    @property
    def jrc_occurrence(self) -> Path:
        return self.root / "jrc_occurrence.tif"

    def forest10m(self, year: int) -> Path:
        return self.root / "forest10m" / f"forest10m_{year}.tif"

    def dw_class(self, year: int) -> Path:
        return self.root / "dw_class" / f"dw_class_{year}.tif"

    @property
    def chirps_daily_csv(self) -> Path:
        return self.root / "rainfall" / "chirps_subbasin_daily.csv"

    @property
    def subbasins(self) -> Path:
        return self.root / "subbasins.geojson"

    @property
    def flood_events_csv(self) -> Path:
        return self.root / "flood_events.csv"

    def flood_fraction(self, event_id: str) -> Path:
        return self.root / "floods" / f"flood_{event_id}.tif"

    def layers_30m(self, years: Sequence[int]) -> list[Path]:
        return [self.dem, self.hsg, self.jrc_occurrence, *(self.dw_class(y) for y in years)]

    def layers_10m(self, years: Sequence[int]) -> list[Path]:
        return [self.forest10m(y) for y in years]

    def write_grid(self, grid: Grid) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {**grid.to_dict(), "nested_factor": NESTED_FACTOR}
        self.grid_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return self.grid_json

    def read_grid(self) -> Grid:
        return Grid.from_dict(json.loads(self.grid_json.read_text(encoding="utf-8")))
