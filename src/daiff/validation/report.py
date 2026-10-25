"""Append rows to the SRS 8.3 test log."""

from __future__ import annotations

from datetime import date
from pathlib import Path


def write_test_log_entry(
    path: Path, *, requirement: str, method: str, run_ref: str, result: str, evidence: str, by: str
) -> None:
    cells = [date.today().isoformat(), requirement, method, run_ref, result, evidence, by]
    clean = [str(c).replace("|", "/").replace("\n", " ") for c in cells]
    text = Path(path).read_text(encoding="utf-8")
    sep = "" if text.endswith("\n") else "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(sep + "| " + " | ".join(clean) + " |\n")
