"""Typed project configuration loaded from YAML (spec §6.1).

Machine- or person-specific settings (data root, Earth Engine project) are excluded from
the config hash so that two teammates running the same config get the same run ids.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectConfig(_Model):
    name: str = Field(pattern=r"^[a-z0-9_-]+$")
    basin: str
    aoi_hybas_id: int | None = None  # HydroBASINS basin that is the AOI (P3)
    aoi_hybas_level: int = Field(default=6, ge=1, le=12)
    subbasin_level: int = Field(default=8, ge=1, le=12)


class GridConfig(_Model):
    crs: str = "EPSG:32646"
    res: float = Field(default=30.0, gt=0)
    bounds: tuple[float, float, float, float] | None = None
    buffer_m: float = Field(default=1000.0, ge=0)

    @field_validator("bounds")
    @classmethod
    def _ordered(cls, v):
        if v is not None and not (v[0] < v[2] and v[1] < v[3]):
            raise ValueError("bounds must be (xmin, ymin, xmax, ymax) with min < max")
        return v


class YearsConfig(_Model):
    t0: int
    years: list[int]
    season_start_month: int = Field(default=11, ge=1, le=12)
    season_end_month: int = Field(default=3, ge=1, le=12)

    @model_validator(mode="after")
    def _check(self):
        ys = self.years
        if not ys or any(b <= a for a, b in zip(ys, ys[1:], strict=False)):
            raise ValueError("years must be non-empty and strictly increasing")
        if min(ys) < 2015:
            raise ValueError("years must be >= 2015")
        if self.t0 not in ys:
            raise ValueError("t0 must be one of years")
        return self


class GeeConfig(_Model):
    project: str | None = None
    asset_root: str | None = None


class RuntimeConfig(_Model):
    seed: int = 42
    cluster: Literal["local", "slurm"] = "local"
    n_workers: int = Field(default=2, ge=1)
    threads_per_worker: int = Field(default=2, ge=1)
    tile_size: int = Field(default=1024, ge=16)


class ForestConfig(_Model):
    mmu_ha: float = Field(default=0.5, gt=0)


class TerrainConfig(_Model):
    stream_threshold_km2: float = Field(default=1.0, gt=0)
    major_stream_km2: float = Field(default=50.0, gt=0)
    routing_dem: Literal["srtm", "merit"] = "srtm"


class CouplingConfig(_Model):
    return_period_years: int = Field(default=10, ge=2)
    dual_hsg: Literal["D"] = "D"


class FloodConfig(_Model):
    sample_cap_per_class: int = Field(default=50000, ge=10)
    train_until: int = 2021
    block_size_m: float = Field(default=10000.0, gt=0)
    class_breaks: list[float] = [0.2, 0.4, 0.6, 0.8]
    n_estimators: int = Field(default=400, ge=1)
    max_depth: int = Field(default=6, ge=1)
    learning_rate: float = Field(default=0.05, gt=0)
    min_child_weight: float = Field(default=1.0, ge=0)
    subsample: float = Field(default=1.0, gt=0, le=1)
    colsample_bytree: float = Field(default=1.0, gt=0, le=1)
    flooded_fraction_threshold: float = Field(default=0.5, gt=0, le=1)
    # "temporal": SRS 7.4 split (train <= train_until, test after). "loeo": leave-one-event-out,
    # for when too few events fall before the split (Kopili: D-32).
    strategy: Literal["temporal", "loeo"] = "temporal"

    @field_validator("class_breaks")
    @classmethod
    def _four_increasing(cls, v):
        if len(v) != 4 or any(b <= a for a, b in zip(v, v[1:], strict=False)):
            raise ValueError("class_breaks must be 4 strictly increasing values")
        return v


class PathsConfig(_Model):
    data_root: Path = Path("../data")


class SyntheticConfig(_Model):
    size: int = Field(default=200, ge=20)
    subbasin_split: int = Field(default=2, ge=1)


class DaiffConfig(_Model):
    project: ProjectConfig
    grid: GridConfig = GridConfig()
    years: YearsConfig
    gee: GeeConfig = GeeConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    forest: ForestConfig = ForestConfig()
    terrain: TerrainConfig = TerrainConfig()
    coupling: CouplingConfig = CouplingConfig()
    flood: FloodConfig = FloodConfig()
    paths: PathsConfig = PathsConfig()
    synthetic: SyntheticConfig | None = None

    _data_root: Path = PrivateAttr(default=Path("data"))
    _config_path: Path | None = PrivateAttr(default=None)

    @property
    def data_root(self) -> Path:
        return self._data_root

    @property
    def config_path(self) -> Path | None:
        return self._config_path


# Excluded from hashes: they differ between machines/people, not between experiments.
_MACHINE_SPECIFIC: dict[str, Any] = {"paths": True, "gee": {"project", "asset_root"}}


def _env_for(path: Path) -> dict[str, str]:
    dotenv = {k: v for k, v in dotenv_values(path.parent.parent / ".env").items() if v}
    return {**dotenv, **os.environ}


def load_config(path: str | Path, env: Mapping[str, str] | None = None) -> DaiffConfig:
    path = Path(path).resolve()
    env = _env_for(path) if env is None else dict(env)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if env.get("DAIFF_GEE_PROJECT"):
        raw.setdefault("gee", {})
        raw["gee"] = {**(raw["gee"] or {}), "project": env["DAIFF_GEE_PROJECT"]}
    cfg = DaiffConfig.model_validate(raw)
    base = Path(env["DAIFF_DATA_ROOT"]) if env.get("DAIFF_DATA_ROOT") else None
    if base is None:
        base = cfg.paths.data_root
        if not base.is_absolute():
            base = path.parent / base
    cfg._data_root = (base / cfg.project.name).resolve()
    cfg._config_path = path
    return cfg


def _digest(obj: Any) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def config_hash(cfg: DaiffConfig) -> str:
    return _digest(cfg.model_dump(mode="json", exclude=_MACHINE_SPECIFIC))


def section_hash(cfg: DaiffConfig, name: str) -> str:
    dumped = cfg.model_dump(mode="json", exclude=_MACHINE_SPECIFIC)
    return _digest(dumped.get(name))
