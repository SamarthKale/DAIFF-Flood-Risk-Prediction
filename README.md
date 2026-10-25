# DAIFF — AI-Based Deforestation Monitoring and Flood Risk Prediction

DAIFF is a decision-support prototype for the **Kopili basin, Assam**. It maps annual forest loss
from Sentinel-2, turns that loss into a change in flood susceptibility through three coupling
features (C1–C3), and presents maps, sub-basin statistics, flags and alerts in a web dashboard.
HPC Research Internship, Problem Statement 3.

## Quick start

```bash
uv sync --extra dev
uv run pytest -m "not gee and not slow"
```

- Contributors (and Claude sessions): read [`CLAUDE.md`](CLAUDE.md), then [`docs/STATUS.md`](docs/STATUS.md).
- Design: [`docs/superpowers/specs/2026-10-25-daiff-system-design.md`](docs/superpowers/specs/2026-10-25-daiff-system-design.md).
- Requirements: [`docs/srs/requirements.md`](docs/srs/requirements.md).

Licence: to be decided by the team (see `docs/STATUS.md`).
