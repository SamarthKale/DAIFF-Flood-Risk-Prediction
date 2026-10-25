from typer.testing import CliRunner

from daiff.bench import parse_perf_rows
from daiff.cli import app
from tests.conftest import SYN_CONFIG

runner = CliRunner()


def test_bench_writes_one_row_per_worker_count(tmp_path):
    env = {"DAIFF_DATA_ROOT": str(tmp_path)}
    runner.invoke(app, ["synth", "-c", str(SYN_CONFIG)], env=env)
    runner.invoke(app, ["run", "-c", str(SYN_CONFIG)], env=env)
    out = tmp_path / "perf.md"
    r = runner.invoke(
        app, ["bench", "-c", str(SYN_CONFIG), "--workers", "1,2", "--out", str(out)], env=env
    )
    assert r.exit_code == 0, r.stdout
    rows = parse_perf_rows(out)
    assert [row["workers"] for row in rows] == ["1", "2"]
    assert all(float(row["seconds"]) > 0 for row in rows)
    assert "speed-up" in r.stdout
