"""Dask client factory: LocalCluster now, SLURMCluster on the HPC later (D-05)."""

from __future__ import annotations

import logging

from distributed import Client, LocalCluster

from daiff.config import RuntimeConfig


def make_client(rt: RuntimeConfig) -> Client:
    if rt.cluster == "slurm":
        try:
            from dask_jobqueue import SLURMCluster
        except ImportError as exc:
            raise ImportError(
                "SLURM support needs dask-jobqueue: install with `uv sync --extra hpc`"
            ) from exc
        cluster = SLURMCluster(cores=rt.threads_per_worker, processes=1, memory="8GB")
        cluster.scale(jobs=rt.n_workers)
        return Client(cluster)
    cluster = LocalCluster(
        n_workers=rt.n_workers,
        threads_per_worker=rt.threads_per_worker,
        processes=True,
        dashboard_address=None,
        silence_logs=logging.ERROR,
    )
    return Client(cluster)
