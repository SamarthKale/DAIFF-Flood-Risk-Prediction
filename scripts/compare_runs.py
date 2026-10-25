"""NFR-3 check: the published runs under two data roots have byte-identical rasters.

Usage: uv run python scripts/compare_runs.py <data_root_a> <data_root_b>
"""

import hashlib
import sys
from pathlib import Path


def hashes(root: Path) -> dict[str, str]:
    run_id = (root / "store" / "CURRENT").read_text().strip()
    run = root / "store" / run_id
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(run.glob("*.tif"))}


if __name__ == "__main__":
    a, b = hashes(Path(sys.argv[1])), hashes(Path(sys.argv[2]))
    diff = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
    if diff:
        print("NFR-3 FAIL:", ", ".join(diff))
        sys.exit(1)
    print(f"NFR-3 PASS: {len(a)} rasters identical")
