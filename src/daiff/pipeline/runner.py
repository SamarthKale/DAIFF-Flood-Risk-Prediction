"""Fingerprinted stage-DAG runner (spec §6.4, D-11).

A stage is skipped when its fingerprint (code version + config sections + input checksums)
matches the stored state and all its outputs exist. State is written only after a stage
returns, so a session that dies mid-stage leaves nothing marked done.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from daiff.config import DaiffConfig, section_hash
from daiff.store.provenance import sha256_file


class PipelineError(RuntimeError):
    pass


@dataclass(frozen=True)
class StageContext:
    cfg: DaiffConfig
    data_root: Path
    years: tuple[int, ...]


@dataclass(frozen=True)
class Stage:
    name: str
    run: Callable[[StageContext], None]
    inputs: Callable[[StageContext], list[Path]]
    outputs: Callable[[StageContext], list[Path]]
    config_sections: tuple[str, ...] = ()
    deps: tuple[str, ...] = ()
    version: str = "1"


@dataclass(frozen=True)
class StageResult:
    name: str
    status: Literal["ran", "skipped"]
    seconds: float = field(compare=False)


def _rel(path: Path, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def fingerprint(stage: Stage, ctx: StageContext) -> str:
    h = hashlib.sha256()
    h.update(f"version={stage.version}\n".encode())
    h.update(f"years={','.join(map(str, ctx.years))}\n".encode())
    for section in stage.config_sections:
        h.update(f"{section}={section_hash(ctx.cfg, section)}\n".encode())
    for path in sorted(stage.inputs(ctx), key=lambda p: _rel(p, ctx.data_root)):
        if not Path(path).exists():
            raise PipelineError(f"stage '{stage.name}': missing input {path}")
        h.update(f"{_rel(path, ctx.data_root)}={sha256_file(path)}\n".encode())
    return h.hexdigest()


class Runner:
    def __init__(self, stages: Sequence[Stage], state_dir: Path) -> None:
        self.stages = {s.name: s for s in stages}
        self._declared = [s.name for s in stages]
        self.state_dir = Path(state_dir)

    def order(self) -> list[str]:
        for s in self.stages.values():
            for d in s.deps:
                if d not in self.stages:
                    raise PipelineError(f"stage '{s.name}' depends on unknown stage '{d}'")
        done: list[str] = []
        visiting: set[str] = set()

        def visit(name: str) -> None:
            if name in done:
                return
            if name in visiting:
                raise PipelineError(f"dependency cycle through stage '{name}'")
            visiting.add(name)
            for d in self.stages[name].deps:
                visit(d)
            visiting.discard(name)
            done.append(name)

        for name in self._declared:
            visit(name)
        return done

    def _state_path(self, name: str) -> Path:
        return self.state_dir / f"{name}.json"

    def _is_current(self, stage: Stage, fp: str, ctx: StageContext) -> bool:
        p = self._state_path(stage.name)
        if not p.exists():
            return False
        state = json.loads(p.read_text(encoding="utf-8"))
        return state.get("fingerprint") == fp and all(Path(o).exists() for o in stage.outputs(ctx))

    def run(
        self,
        ctx: StageContext,
        *,
        only: Collection[str] | None = None,
        force: bool = False,
    ) -> list[StageResult]:
        results: list[StageResult] = []
        for name in self.order():
            if only is not None and name not in only:
                continue
            stage = self.stages[name]
            start = time.perf_counter()
            fp = fingerprint(stage, ctx)
            if not force and self._is_current(stage, fp, ctx):
                results.append(StageResult(name, "skipped", time.perf_counter() - start))
                continue
            state = self._state_path(name)
            state.unlink(missing_ok=True)
            try:
                stage.run(ctx)
            except Exception as exc:
                raise PipelineError(f"stage '{name}' failed: {exc}") from exc
            self.state_dir.mkdir(parents=True, exist_ok=True)
            outputs = [_rel(o, ctx.data_root) for o in stage.outputs(ctx)]
            state.write_text(
                json.dumps({"fingerprint": fp, "outputs": outputs}, indent=2), encoding="utf-8"
            )
            results.append(StageResult(name, "ran", time.perf_counter() - start))
        return results
