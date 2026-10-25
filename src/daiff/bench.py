"""NFR-2 benchmark: tiled susceptibility prediction with 1, 2, … Dask workers."""

from __future__ import annotations

import os
import platform
import time
from pathlib import Path

import numpy as np

from daiff.config import DaiffConfig, RuntimeConfig
from daiff.flood.model import load_model
from daiff.flood.predict import assemble_features
from daiff.pipeline.stages import features_for, plan_for_run
from daiff.runtime import make_client
from daiff.store.run_store import current_run

HEADER = (
    "| machine | cores | RAM GB | workers | stage | seconds | run_id | commit |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def _predict_chunk(model, chunk: np.ndarray) -> np.ndarray:
    return model.predict_proba(chunk)[:, 1]


def bench(cfg: DaiffConfig, workers: list[int], out: Path, repeat: int = 20) -> list[float]:
    run_id = current_run(cfg.data_root)
    if run_id is None:
        raise FileNotFoundError("no published run — run the pipeline first")
    p = plan_for_run(cfg, run_id)
    model, feats = load_model(p.models_dir / p.store.model_id_file.read_text().strip())
    stack, valid = assemble_features(features_for(p, max(p.years)), feats)
    data = np.tile(stack[valid], (repeat, 1))  # enlarge so the benchmark measures compute
    times = []
    for n in workers:
        rt = RuntimeConfig(n_workers=n, threads_per_worker=1)
        with make_client(rt) as client:
            # Tiles live on the workers before timing (as when each worker reads its own tiles).
            remote_model = client.scatter(model, broadcast=True)
            chunks = client.scatter(np.array_split(data, n * 4))
            client.gather(client.map(_predict_chunk, [remote_model] * len(chunks), chunks))
            t = time.perf_counter()
            client.gather(
                client.map(_predict_chunk, [remote_model] * len(chunks), chunks, pure=False)
            )
            times.append(time.perf_counter() - t)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        out.write_text(HEADER, encoding="utf-8")
    with out.open("a", encoding="utf-8") as f:
        for n, sec in zip(workers, times, strict=True):
            f.write(
                f"| {platform.node()} | {os.cpu_count()} | – | {n} | predict(bench) | "
                f"{sec:.3f} | {run_id} | {p.commit[:12]} |\n"
            )
    return times


def parse_perf_rows(path: Path) -> list[dict[str, str]]:
    lines = [ln for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.startswith("|")]
    keys = [c.strip() for c in lines[0].strip("|").split("|")]
    return [
        dict(zip(keys, [c.strip() for c in ln.strip("|").split("|")], strict=True))
        for ln in lines[2:]
    ]
