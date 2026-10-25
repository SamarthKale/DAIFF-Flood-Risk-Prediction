#!/bin/bash
# DAIFF pipeline run on a SLURM cluster (D-05). Adjust the resources to the internship allocation (OI-4).
#SBATCH --job-name=daiff-run
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=daiff-%j.log

set -euo pipefail
CONFIG=${CONFIG:-configs/kopili.yaml}
cd "${SLURM_SUBMIT_DIR}"
uv sync --extra hpc
uv run daiff run -c "${CONFIG}" --log-perf
