"""The `daiff` command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from daiff import __version__

app = typer.Typer(no_args_is_help=True, add_completion=False)

ConfigOpt = typer.Option(..., "-c", "--config", help="Path to a YAML config in configs/.")


def _version(value: bool) -> None:
    if value:
        typer.echo(f"daiff {__version__}")
        raise typer.Exit(0)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version, is_eager=True, help="Show version and exit."
    ),
) -> None:
    """DAIFF pipeline, checks and dashboard server."""


def _load(config: Path):
    from daiff.config import load_config

    return load_config(config)


def _grid(cfg):
    from daiff.grid import Grid
    from daiff.store.raw_layout import RawLayout

    if cfg.grid.bounds is not None:
        return Grid.from_config(cfg)
    return RawLayout(cfg.data_root).read_grid()


@app.command()
def synth(config: Path = ConfigOpt) -> None:
    """Generate the synthetic basin's raw inputs."""
    from daiff.synthetic import make_basin

    raw = make_basin(_load(config))
    typer.echo(f"wrote synthetic raw inputs to {raw.root}")


@app.command("check-grid")
def check_grid(config: Path = ConfigOpt) -> None:
    """FR-D5: check every raw layer is on the common grid."""
    from daiff.grid import check_alignment
    from daiff.store.raw_layout import RawLayout

    cfg = _load(config)
    raw = RawLayout(cfg.data_root)
    years = cfg.years.years
    l30 = [p for p in raw.layers_30m(years) if p.exists()]
    l10 = [p for p in raw.layers_10m(years) if p.exists()]
    if not (l30 or l10) or not (raw.grid_json.exists() or cfg.grid.bounds):
        typer.echo(f"FR-D5 FAIL: no raw layers found under {raw.root}")
        raise typer.Exit(1)
    grid = _grid(cfg)
    problems = check_alignment(l30, grid).problems + check_alignment(l10, grid.nested(3)).problems
    if problems:
        typer.echo("FR-D5 FAIL")
        for p in problems:
            typer.echo(f"{p.field} {p.path} expected={p.expected} actual={p.actual}")
        raise typer.Exit(1)
    typer.echo(f"FR-D5 PASS: {len(l30) + len(l10)} layers aligned")


@app.command("check-metadata")
def check_metadata_cmd(
    config: Path = ConfigOpt,
    run_id: str | None = typer.Option(None, "--run-id", help="Defaults to the published run."),
) -> None:
    """NFR-4: check provenance tags and run metadata of a run."""
    from daiff.store.check import check_metadata
    from daiff.store.run_store import RunStore, current_run

    cfg = _load(config)
    run_id = run_id or current_run(cfg.data_root)
    if run_id is None:
        typer.echo(f"no published run under {cfg.data_root / 'store'} — run the pipeline first")
        raise typer.Exit(2)
    problems = check_metadata(RunStore(cfg.data_root, run_id).run_dir)
    if problems:
        typer.echo("NFR-4 FAIL")
        for p in problems:
            typer.echo(f"{p.path}: {p.problem}")
        raise typer.Exit(1)
    typer.echo(f"NFR-4 PASS: {run_id}")
