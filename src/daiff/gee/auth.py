"""Earth Engine initialisation with actionable errors."""

from __future__ import annotations

from daiff.config import DaiffConfig

GUIDE = "docs/setup/gee.md"


class GeeAuthError(RuntimeError):
    pass


def init_ee(cfg: DaiffConfig, ee_module=None):
    """Initialise Earth Engine for the config's project and return the `ee` module."""
    if ee_module is None:
        import ee as ee_module
    if not cfg.gee.project:
        raise GeeAuthError(
            f"DAIFF_GEE_PROJECT is not set: put your Earth Engine project ID in .env (see {GUIDE})"
        )
    try:
        ee_module.Initialize(project=cfg.gee.project)
    except Exception as exc:  # the ee client raises several exception types
        raise GeeAuthError(
            f"Earth Engine login failed for project '{cfg.gee.project}': {exc}. "
            "Run `uv run earthengine authenticate` with the account that owns the project "
            f"({GUIDE})."
        ) from exc
    return ee_module
