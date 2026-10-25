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
from typing import Any

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectConfig(_Model):
    name: str = Field(pattern=r"^[a-z0-9_-]+$")
    basin: str


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
