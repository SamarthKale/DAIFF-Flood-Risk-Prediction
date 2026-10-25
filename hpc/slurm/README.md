# Running DAIFF on the HPC cluster (SLURM)

DAIFF is developed on laptops; the cluster is a configuration change, not a code change (D-05).

1. Clone the repo on the cluster and install uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
2. Copy `.env` (your `DAIFF_GEE_PROJECT`; `DAIFF_DATA_ROOT` pointing at scratch storage).
3. Single-node run: `sbatch --export=CONFIG=configs/kopili.yaml hpc/slurm/daiff_run.sbatch`.
4. Multi-node tiled stages: set `runtime: {cluster: slurm, n_workers: <jobs>, threads_per_worker: <cores>}`
   in the config. `daiff run` then starts a `dask_jobqueue.SLURMCluster` from the login node
   (needs `uv sync --extra hpc`).

Resource values (`--cpus-per-task`, `--mem`, `--time`) are placeholders until the guide confirms
the allocation (OI-4). Record timings with `--log-perf` for NFR-1/NFR-2.
