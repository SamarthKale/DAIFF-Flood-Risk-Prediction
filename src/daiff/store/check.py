"""NFR-4 metadata check over a run directory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from daiff.store.cog import read_tags
from daiff.store.provenance import REQUIRED_TAGS
from daiff.store.run_store import RUN_METADATA_KEYS


@dataclass(frozen=True)
class MetadataProblem:
    path: Path
    problem: str


def check_metadata(run_dir: Path) -> list[MetadataProblem]:
    run_dir = Path(run_dir)
    problems: list[MetadataProblem] = []
    for tif in sorted(run_dir.rglob("*.tif")):
        tags = read_tags(tif)
        for key in REQUIRED_TAGS:
            if not tags.get(key):
                problems.append(MetadataProblem(tif, f"missing tag {key}"))
    meta_path = run_dir / "run_metadata.json"
    if not meta_path.exists():
        problems.append(MetadataProblem(meta_path, "run_metadata.json is missing"))
    else:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        missing = [k for k in RUN_METADATA_KEYS if k not in meta]
        if missing:
            problems.append(MetadataProblem(meta_path, f"missing keys: {', '.join(missing)}"))
    return problems
