"""The common project grid and the FR-D5 alignment check (spec §5, §6.2)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import rasterio
from affine import Affine
from rasterio.crs import CRS

if TYPE_CHECKING:
    from daiff.config import DaiffConfig


@dataclass(frozen=True)
class Grid:
    crs: str
    transform: Affine
    width: int
    height: int

    @classmethod
    def from_bounds(
        cls,
        crs: str,
        bounds: tuple[float, float, float, float],
        res: float,
        buffer_m: float = 0.0,
    ) -> Grid:
        xmin, ymin, xmax, ymax = bounds
        xmin, ymin, xmax, ymax = xmin - buffer_m, ymin - buffer_m, xmax + buffer_m, ymax + buffer_m
        x0 = math.floor(xmin / res) * res
        y0 = math.floor(ymin / res) * res
        x1 = math.ceil(xmax / res) * res
        y1 = math.ceil(ymax / res) * res
        width = round((x1 - x0) / res)
        height = round((y1 - y0) / res)
        return cls(crs, Affine(res, 0, x0, 0, -res, y1), width, height)

    @classmethod
    def from_config(cls, cfg: DaiffConfig) -> Grid:
        if cfg.grid.bounds is None:
            raise ValueError("grid.bounds is not set in the config — run the AOI step (P3) first")
        return cls.from_bounds(cfg.grid.crs, cfg.grid.bounds, cfg.grid.res, cfg.grid.buffer_m)

    @property
    def res(self) -> float:
        return self.transform.a

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        x0, y1 = self.transform.c, self.transform.f
        return (x0, y1 - self.height * self.res, x0 + self.width * self.res, y1)

    @property
    def cell_area_m2(self) -> float:
        return self.res * self.res

    def nested(self, factor: int) -> Grid:
        t = self.transform
        return Grid(
            self.crs,
            Affine(t.a / factor, 0, t.c, 0, t.e / factor, t.f),
            self.width * factor,
            self.height * factor,
        )

    def xy_to_rowcol(self, x: float, y: float) -> tuple[int, int]:
        col, row = ~self.transform @ (x, y)
        r, c = math.floor(row), math.floor(col)
        if not (0 <= r < self.height and 0 <= c < self.width):
            raise ValueError(f"point ({x}, {y}) is outside the grid")
        return r, c

    def to_dict(self) -> dict:
        t = self.transform
        return {
            "crs": self.crs,
            "transform": [t.a, t.b, t.c, t.d, t.e, t.f],
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Grid:
        return cls(d["crs"], Affine(*d["transform"]), int(d["width"]), int(d["height"]))


@dataclass(frozen=True)
class LayerProblem:
    path: Path
    field: Literal["missing", "crs", "transform", "shape"]
    expected: str
    actual: str


@dataclass
class AlignmentReport:
    checked: list[Path] = field(default_factory=list)
    problems: list[LayerProblem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def check_alignment(paths: Sequence[Path], grid: Grid, atol: float = 1e-6) -> AlignmentReport:
    """FR-D5: every layer must share the grid's CRS, transform and shape."""
    report = AlignmentReport()
    want_crs = CRS.from_user_input(grid.crs)
    for path in map(Path, paths):
        report.checked.append(path)
        if not path.exists():
            report.problems.append(LayerProblem(path, "missing", "file", "absent"))
            continue
        with rasterio.open(path) as src:
            if src.crs != want_crs:
                report.problems.append(LayerProblem(path, "crs", grid.crs, str(src.crs)))
            if (src.height, src.width) != grid.shape:
                report.problems.append(
                    LayerProblem(path, "shape", str(grid.shape), str((src.height, src.width)))
                )
            if not src.transform.almost_equals(grid.transform, precision=atol):
                report.problems.append(
                    LayerProblem(
                        path,
                        "transform",
                        str(tuple(grid.transform)[:6]),
                        str(tuple(src.transform)[:6]),
                    )
                )
    return report
