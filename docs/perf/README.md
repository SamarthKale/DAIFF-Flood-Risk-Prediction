# Performance logs (NFR-1, NFR-2)

`daiff run --log-perf` and `daiff bench` append Markdown tables here, one file per date and
machine (`<YYYY-MM-DD>-<machine>.md`), with columns:

| machine | cores | RAM GB | workers | stage | seconds | run_id | commit |
|---|---|---|---|---|---|---|---|

NFR-1: a full annual Kopili update (raw imagery → published maps) must take ≤ 6 hours on the HPC
allocation (laptop timings are recorded until HPC access exists, D-05). NFR-2: doubling workers must
cut wall time by ≥ 40% on the benchmark run.
