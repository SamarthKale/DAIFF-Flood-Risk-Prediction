"""Flood training data: event sampling and time-matched feature rows (SRS 3.4, 7.4)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from daiff.config import DaiffConfig
from daiff.coupling.compute import coupling_for_year, forest_for_year, mmu_pixels, rain_rasters
from daiff.grid import Grid
from daiff.store.cog import read_raster
from daiff.store.raw_layout import RawLayout
from daiff.terrain.derive import Terrain, build_static_features
from daiff.zones import rasterize_subbasins

FEATURES: tuple[str, ...] = (
    "elevation",
    "slope",
    "twi",
    "hand",
    "dist_river",
    "hsg",
    "rain_mean_annual",
    "rain_p10y_1d",
    "f",
    "dF",
    "U",
    "CN",
    "Q",
)
COUPLING_FEATURES: tuple[str, ...] = ("f", "dF", "U", "CN", "Q")
MONOTONE: dict[str, int] = {"dF": 1, "U": 1, "CN": 1, "Q": 1, "f": -1}


def sample_event(
    flooded: np.ndarray, valid: np.ndarray, cap: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Flat indices of up to `cap` flooded cells and the same number of non-flooded cells."""
    pos_all = np.flatnonzero(valid & flooded)
    neg_all = np.flatnonzero(valid & ~flooded)
    n = min(len(pos_all), len(neg_all), cap)
    if n == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    pos = np.sort(rng.choice(pos_all, size=n, replace=False))
    neg = np.sort(rng.choice(neg_all, size=n, replace=False))
    return pos, neg


def year_features(
    terrain: Terrain, rain: dict[str, np.ndarray], coupling: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    src = {**terrain.bands, **rain, **coupling}
    return {name: np.asarray(src[name], dtype=np.float64) for name in FEATURES}


def build_dataset(
    events: pd.DataFrame,
    features_for_year: Callable[[int], dict[str, np.ndarray]],
    flood_mask: Callable[[str], np.ndarray],
    grid: Grid,
    cfg: DaiffConfig,
) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.runtime.seed)
    rows = np.arange(grid.height * grid.width)
    r, c = np.divmod(rows, grid.width)
    x = grid.transform.c + (c + 0.5) * grid.res
    y = grid.transform.f - (r + 0.5) * grid.res
    bs = cfg.flood.block_size_m
    frames = []
    for ev in events[events["usable"].astype(bool)].itertuples():
        feats = features_for_year(int(ev.year))
        stack = np.stack([feats[n].ravel() for n in FEATURES], axis=1)
        mask = flood_mask(ev.event_id).ravel()
        valid = np.isfinite(stack).all(axis=1) & np.isfinite(mask)
        flooded = mask >= cfg.flood.flooded_fraction_threshold
        pos, neg = sample_event(flooded, valid, cfg.flood.sample_cap_per_class, rng)
        idx = np.concatenate([pos, neg])
        if idx.size == 0:
            continue
        df = pd.DataFrame(stack[idx], columns=list(FEATURES))
        df.insert(0, "label", np.r_[np.ones(len(pos), int), np.zeros(len(neg), int)])
        df.insert(
            0,
            "block",
            [f"{int(a // bs)}_{int(b // bs)}" for a, b in zip(x[idx], y[idx], strict=True)],
        )
        df.insert(0, "y", y[idx])
        df.insert(0, "x", x[idx])
        df.insert(0, "cell", idx)
        df.insert(0, "split", ev.split)
        df.insert(0, "event_id", ev.event_id)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


@dataclass
class FloodContext:
    cfg: DaiffConfig
    raw: RawLayout
    grid: Grid
    terrain: Terrain
    rain: dict[str, np.ndarray]
    zones: np.ndarray
    names: pd.DataFrame
    dataset: pd.DataFrame = field(default_factory=pd.DataFrame)
    _cache: dict[int, dict[str, np.ndarray]] = field(default_factory=dict)

    def features_for_year(self, year: int) -> dict[str, np.ndarray]:
        if year not in self._cache:
            t0 = self.cfg.years.t0
            yf = forest_for_year(self.raw, self.grid, t0, year, mmu_pixels(self.cfg.forest.mmu_ha))
            cf = coupling_for_year(
                self.raw, self.grid, self.terrain, self.rain["rain_p10y_1d"], yf, year
            )
            self._cache[year] = year_features(self.terrain, self.rain, cf)
        return self._cache[year]


def flood_context(cfg: DaiffConfig, raw: RawLayout) -> FloodContext:
    grid = raw.read_grid()
    terrain = build_static_features(raw, grid, cfg.terrain.stream_threshold_km2)
    zones, names = rasterize_subbasins(raw.subbasins, grid)
    rain = rain_rasters(raw, zones, list(names["subbasin_id"]), cfg.coupling.return_period_years)
    return FloodContext(cfg, raw, grid, terrain, rain, zones, names)


def build_dataset_from_raw(cfg: DaiffConfig, raw: RawLayout) -> FloodContext:
    ctx = flood_context(cfg, raw)
    events = pd.read_csv(raw.flood_events_csv)
    ctx.dataset = build_dataset(
        events,
        ctx.features_for_year,
        lambda eid: read_raster(raw.flood_fraction(eid), ctx.grid),
        ctx.grid,
        cfg,
    )
    return ctx
