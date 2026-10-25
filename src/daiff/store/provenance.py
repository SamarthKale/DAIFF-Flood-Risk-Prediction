"""Provenance tags and deterministic run ids (NFR-3, NFR-4)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

REQUIRED_TAGS: tuple[str, ...] = (
    "DAIFF_RUN_ID",
    "DAIFF_CONFIG_HASH",
    "DAIFF_CODE_COMMIT",
    "DAIFF_MODEL_ID",
    "DAIFF_INPUTS",
    "DAIFF_DATA_VERSIONS",
    "DAIFF_YEAR",
    "DAIFF_T0",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(repo_dir: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_dir), *args], capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def code_commit(repo_dir: Path) -> str:
    """HEAD sha, with `-dirty` when the working tree has changes; `unknown` outside git."""
    if not Path(repo_dir).is_dir():
        return "unknown"
    sha = _git(repo_dir, "rev-parse", "HEAD")
    if not sha:
        return "unknown"
    status = _git(repo_dir, "status", "--porcelain")
    return f"{sha}-dirty" if status else sha


def compute_run_id(config_hash: str, commit: str, input_checksums: Sequence[str]) -> str:
    payload = "|".join([config_hash, commit, *sorted(input_checksums)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _relative(path: Path, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(path).name


def build_tags(
    *,
    run_id: str,
    config_hash: str,
    code_commit: str,
    model_id: str,
    inputs: Sequence[Path],
    data_root: Path,
    data_versions: Mapping[str, str],
    year: int | None,
    t0: int,
) -> dict[str, str]:
    records = sorted(
        ({"path": _relative(p, data_root), "sha256": sha256_file(p)} for p in inputs),
        key=lambda r: r["path"],
    )
    return {
        "DAIFF_RUN_ID": run_id,
        "DAIFF_CONFIG_HASH": config_hash,
        "DAIFF_CODE_COMMIT": code_commit,
        "DAIFF_MODEL_ID": model_id,
        "DAIFF_INPUTS": _canonical(records),
        "DAIFF_DATA_VERSIONS": _canonical(dict(data_versions)),
        "DAIFF_YEAR": "n/a" if year is None else str(year),
        "DAIFF_T0": str(t0),
    }
