"""FR-C2: when a new forest map appears, recompute coupling and susceptibility automatically."""

from __future__ import annotations

import re
import time

from daiff.config import DaiffConfig
from daiff.pipeline.stages import published_years, run_pipeline
from daiff.store.raw_layout import RawLayout
from daiff.store.run_store import RunStore, current_run

_YEAR = re.compile(r"forest10m_(\d{4})\.tif$")


def available_forest_years(raw: RawLayout) -> list[int]:
    folder = raw.forest10m(0).parent
    if not folder.exists():
        return []
    return sorted(int(m.group(1)) for p in folder.iterdir() if (m := _YEAR.search(p.name)))


def watch(cfg: DaiffConfig, interval_s: float = 30.0, once: bool = False) -> list[int]:
    """Process forest years present in the raw layout but missing from the published run,
    reusing the published run's trained model (no retraining, no manual step)."""
    raw = RawLayout(cfg.data_root)
    while True:
        run_id = current_run(cfg.data_root)
        done = published_years(cfg, run_id) if run_id else []
        new = [y for y in available_forest_years(raw) if y not in done and y > cfg.years.t0]
        if new and run_id:
            model_id = RunStore(cfg.data_root, run_id).model_id_file.read_text().strip()
            run_pipeline(cfg, years=sorted(set(done) | set(new)), model_id=model_id)
        if once:
            return new
        time.sleep(interval_s)
