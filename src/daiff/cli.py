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


def _csv_ints(value: str | None) -> list[int] | None:
    return [int(v) for v in value.split(",")] if value else None


@app.command()
def run(
    config: Path = ConfigOpt,
    stages: str | None = typer.Option(None, help="Comma-separated subset, e.g. terrain,forest"),
    years: str | None = typer.Option(None, help="Comma-separated years (default: config years)"),
    force: bool = typer.Option(False, help="Re-run stages even if unchanged"),
    log_perf: bool = typer.Option(False, "--log-perf", help="Append timings to docs/perf/"),
) -> None:
    """Run the pipeline (terrain → forest → coupling → train → predict → tables) and publish."""
    from daiff.pipeline.stages import run_pipeline

    cfg = _load(config)
    run_id = run_pipeline(
        cfg,
        stages=stages.split(",") if stages else None,
        years=_csv_ints(years),
        force=force,
        log_perf=log_perf,
    )
    typer.echo(f"published run {run_id} under {cfg.data_root / 'store'}")


@app.command()
def train(config: Path = ConfigOpt) -> None:
    """FR-R1: build features and train the susceptibility model from the config."""
    from daiff.pipeline.stages import run_pipeline

    run_id = run_pipeline(_load(config), stages=["terrain", "forest", "coupling", "train"])
    typer.echo(f"trained model for run {run_id}")


@app.command()
def watch(
    config: Path = ConfigOpt,
    interval: float = typer.Option(30.0, help="Polling interval in seconds"),
    once: bool = typer.Option(False, help="Check once and exit"),
) -> None:
    """FR-C2: re-run coupling and susceptibility whenever a new forest map appears."""
    from daiff.pipeline.watch import watch as watch_loop

    new = watch_loop(_load(config), interval_s=interval, once=once)
    typer.echo(f"processed new forest years: {new}" if new else "no new forest maps")


@app.command("sample-points")
def sample_points_cmd(
    config: Path = ConfigOpt,
    reference_dir: Path | None = typer.Option(None, help="Default: <repo>/reference"),
) -> None:
    """SRS 7.3: draw the stratified reference sample (≥600 points, ≥150 loss)."""
    from daiff.validation.run import DEFAULT_REFERENCE_DIR, sample_points

    out = sample_points(_load(config), reference_dir or DEFAULT_REFERENCE_DIR)
    typer.echo(f"wrote {out}")


@app.command()
def validate(
    config: Path = ConfigOpt,
    what: str = typer.Option(..., help="forest or flood"),
    n_boot: int = typer.Option(1000, help="Bootstrap samples for the ablation CI"),
    reference_dir: Path | None = typer.Option(None, help="Default: <repo>/reference"),
    log: bool = typer.Option(True, "--log/--no-log", help="Append results to docs/test_log.md"),
) -> None:
    """Compute SRS chapter 7 metrics for the published run (FR-F1/F2, FR-R2/R3)."""
    from daiff.validation import run as v

    cfg = _load(config)
    if what == "forest":
        try:
            m = v.validate_forest(cfg, reference_dir or v.DEFAULT_REFERENCE_DIR)
        except v.MissingLabels as exc:
            typer.echo(str(exc))
            raise typer.Exit(2) from exc
        typer.echo(
            f"FR-F1 OA {m['fr_f1']['overall_accuracy']:.3f}, forest F1 "
            f"{m['fr_f1']['forest_f1']:.3f}; FR-F2 loss F1 {m['fr_f2']['loss_f1']:.3f}"
        )
    elif what == "flood":
        m = v.validate_flood(cfg, n_boot=n_boot)
        typer.echo(
            f"FR-R2 AUC {m['auc']:.3f} (HAND baseline {m['hand_baseline_auc_binary']:.3f}); "
            f"FR-R3 ablation dAUC {m['ablation']['delta']:.3f}"
        )
    else:
        typer.echo("--what must be 'forest' or 'flood'")
        raise typer.Exit(2)
    if log:
        v.log_results(cfg, what, m)


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
