from dataclasses import replace

import pytest

from daiff.pipeline import PipelineError, Runner, Stage, StageContext


@pytest.fixture
def ctx(synthetic_cfg, tmp_path):
    return StageContext(cfg=synthetic_cfg, data_root=tmp_path, years=(2019, 2020))


def copy_stage(name, src, dst, calls, deps=(), version="1", boom=None):
    def run(_ctx):
        calls.append(name)
        if boom and boom["on"]:
            raise RuntimeError("boom")
        dst.write_text(src.read_text() + name)

    return Stage(
        name=name,
        run=run,
        inputs=lambda _c: [src],
        outputs=lambda _c: [dst],
        config_sections=("runtime",),
        deps=deps,
        version=version,
    )


@pytest.fixture
def chain(tmp_path):
    a_in = tmp_path / "a_in.txt"
    a_in.write_text("x")
    calls: list[str] = []
    a = copy_stage("a", a_in, tmp_path / "a.txt", calls)
    b = copy_stage("b", tmp_path / "a.txt", tmp_path / "b.txt", calls, deps=("a",))
    return a_in, calls, a, b


def test_runs_in_dependency_order(ctx, tmp_path, chain):
    _, calls, a, b = chain
    results = Runner([b, a], tmp_path / "state").run(ctx)
    assert calls == ["a", "b"] and [r.status for r in results] == ["ran", "ran"]


def test_cycle_and_unknown_dependency_raise(tmp_path, chain):
    _, calls, a, b = chain
    with pytest.raises(PipelineError):
        Runner([replace(a, deps=("b",)), b], tmp_path / "s").order()
    with pytest.raises(PipelineError):
        Runner([replace(a, deps=("zzz",))], tmp_path / "s").order()


def test_skips_when_unchanged(ctx, tmp_path, chain):
    _, calls, a, b = chain
    r = Runner([a, b], tmp_path / "state")
    r.run(ctx)
    assert [x.status for x in r.run(ctx)] == ["skipped", "skipped"] and calls == ["a", "b"]


def test_reruns_on_changed_input_missing_output_or_new_version(ctx, tmp_path, chain):
    a_in, calls, a, b = chain
    state = tmp_path / "state"
    Runner([a, b], state).run(ctx)
    a_in.write_text("y")
    Runner([a, b], state).run(ctx)
    assert calls == ["a", "b", "a", "b"]
    (tmp_path / "b.txt").unlink()
    Runner([a, b], state).run(ctx)
    assert calls[-1] == "b" and len(calls) == 5
    Runner([replace(a, version="2"), b], state).run(ctx)
    assert calls[-1] == "a" and len(calls) == 6  # b's input bytes unchanged, so b is skipped


def test_force_and_only(ctx, tmp_path, chain):
    _, calls, a, b = chain
    r = Runner([a, b], tmp_path / "state")
    r.run(ctx)
    r.run(ctx, force=True)
    assert calls == ["a", "b", "a", "b"]
    r.run(ctx, only={"b"}, force=True)
    assert calls[-1] == "b" and len(calls) == 5


def test_failed_stage_leaves_no_state_and_reruns(ctx, tmp_path):
    src = tmp_path / "in.txt"
    src.write_text("x")
    calls: list[str] = []
    boom = {"on": True}
    s = copy_stage("a", src, tmp_path / "out.txt", calls, boom=boom)
    with pytest.raises(PipelineError):
        Runner([s], tmp_path / "state").run(ctx)
    assert not (tmp_path / "state" / "a.json").exists()
    boom["on"] = False
    assert [x.status for x in Runner([s], tmp_path / "state").run(ctx)] == ["ran"]


def test_missing_input_is_a_pipeline_error(ctx, tmp_path):
    s = copy_stage("a", tmp_path / "absent.txt", tmp_path / "o.txt", [])
    with pytest.raises(PipelineError, match="absent.txt"):
        Runner([s], tmp_path / "state").run(ctx)
