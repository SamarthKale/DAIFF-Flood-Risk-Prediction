"""Run store: Appendix C output paths, run metadata and the published-run pointer."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

RUN_METADATA_KEYS = (
    "run_id",
    "config",
    "config_hash",
    "code_commit",
    "data_versions",
    "inputs",
    "timings",
)


class RunStore:
    def __init__(self, data_root: Path, run_id: str) -> None:
        self.data_root = Path(data_root)
        self.run_id = run_id
        self.run_dir = self.data_root / "store" / run_id

    def _f(self, name: str) -> Path:
        return self.run_dir / name

    # Appendix C (SRS Table 24)
    def forest(self, year: int) -> Path:
        return self._f(f"forest_{year}.tif")

    def loss(self, t0: int, year: int) -> Path:
        return self._f(f"loss_{t0}_{year}.tif")

    def coupling(self, year: int) -> Path:
        return self._f(f"coupling_{year}.tif")

    def susceptibility(self, year: int) -> Path:
        return self._f(f"susceptibility_{year}.tif")

    def riskclass(self, year: int) -> Path:
        return self._f(f"riskclass_{year}.tif")

    def delta_s(self, year: int) -> Path:
        return self._f(f"delta_s_{year}.tif")

    def subbasin_csv(self, year: int) -> Path:
        return self._f(f"subbasin_{year}.csv")

    @property
    def run_metadata(self) -> Path:
        return self._f("run_metadata.json")

    # Extras (spec §9)
    def forest10m(self, year: int) -> Path:
        return self._f(f"forest10m_{year}.tif")

    def loss10m(self, t0: int, year: int) -> Path:
        return self._f(f"loss10m_{t0}_{year}.tif")

    def regrowth(self, t0: int, year: int) -> Path:
        return self._f(f"regrowth_{t0}_{year}.tif")

    def cn(self, year: int) -> Path:
        return self._f(f"cn_{year}.tif")

    def preview(self, year: int) -> Path:
        return self._f(f"preview_{year}.tif")

    @property
    def static_features(self) -> Path:
        return self._f("static_features.tif")

    @property
    def subbasins_geojson(self) -> Path:
        return self._f("subbasins.geojson")

    @property
    def metrics_dir(self) -> Path:
        return self._f("metrics")

    @property
    def model_id_file(self) -> Path:
        return self._f("model_id.txt")


def write_run_metadata(store: RunStore, payload: Mapping[str, object]) -> Path:
    store.run_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(payload), sort_keys=True, indent=2, default=str)
    store.run_metadata.write_text(text + "\n", encoding="utf-8", newline="\n")
    return store.run_metadata


def _pointer(data_root: Path) -> Path:
    return Path(data_root) / "store" / "CURRENT"


def publish(data_root: Path, run_id: str) -> None:
    run_dir = RunStore(data_root, run_id).run_dir
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run directory {run_dir} does not exist")
    _pointer(data_root).write_text(run_id + "\n", encoding="utf-8", newline="\n")


def current_run(data_root: Path) -> str | None:
    p = _pointer(data_root)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8").strip() or None
