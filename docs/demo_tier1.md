# Tier 1 witnessed demos (guide sign-off: FR-C2, FR-R1, FR-V1)

Each demo is run with the guide watching; the guide's initials and date go in `docs/test_log.md`.
Use `configs/kopili.yaml` (or `synthetic.yaml` if the data drive is missing).

**FR-C2: a new forest map triggers a coupling re-run automatically**
1. `uv run daiff watch -c configs/synthetic.yaml` (leave running).
2. Copy a new `forest10m_<year>.tif` into the raw forest folder (or touch an existing one).
3. Show the log: the watcher notices it and re-runs coupling, forest and the dependent stages.

**FR-R1: train the susceptibility model from the config**
1. `uv run daiff train -c configs/kopili.yaml`
2. Show the model id, `metrics/flood.json` and that the config alone controlled the run.

**FR-V1: view forest-loss and risk maps in the dashboard**
1. `uv run daiff serve -c configs/kopili.yaml`, open http://localhost:8000.
2. Switch layers (forest, loss, susceptibility, risk class, change in susceptibility) and years;
   show the legend, the experimental-use banner and the model AUC beside the map.
