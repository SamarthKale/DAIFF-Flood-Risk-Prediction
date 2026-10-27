"""Bring U-Net class maps (written by the Colab notebook) onto the raw layout (D-14)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import rasterio

from daiff.grid import Grid, check_alignment
from daiff.store.cog import write_cog

NAME = re.compile(r"forest10m_(\d{4})\.tif$")


def import_unet(grid10: Grid, src_dir: Path, raw_root: Path) -> list[Path]:
    """Validate each `forest10m_<year>.tif` against the nested 10 m grid and write it as a COG
    under `<raw_root>/forest10m_unet/`. Raises ValueError naming the year if misaligned."""
    out: list[Path] = []
    for path in sorted(Path(src_dir).glob("forest10m_*.tif")):
        m = NAME.search(path.name)
        if not m:
            continue
        report = check_alignment([path], grid10)
        if not report.ok:
            raise ValueError(f"{m.group(1)}: not on the 10 m grid ({report.problems[0].field})")
        with rasterio.open(path) as src:
            arr = src.read(1).astype(np.uint8)
        dest = Path(raw_root) / "forest10m_unet" / path.name
        write_cog(dest, arr, grid10, nodata=255, tags={"DAIFF_SOURCE": "forest:unet-colab"})
        out.append(dest)
    return out
