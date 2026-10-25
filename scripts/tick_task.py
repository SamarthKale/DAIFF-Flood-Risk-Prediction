"""Tick every checkbox of one task in a plan file.

Usage: uv run python scripts/tick_task.py docs/superpowers/plans/<plan>.md <task-number>
"""

import re
import sys
from pathlib import Path


def tick(plan: Path, task: str) -> int:
    text = plan.read_text(encoding="utf-8")
    pattern = re.compile(rf"(^### Task {re.escape(task)}:.*?)(?=^### |\Z)", re.S | re.M)
    match = pattern.search(text)
    if not match:
        raise SystemExit(f"task {task} not found in {plan}")
    section = match.group(1)
    ticked = section.replace("- [ ]", "- [x]")
    plan.write_text(text.replace(section, ticked), encoding="utf-8")
    return section.count("- [ ]")


if __name__ == "__main__":
    print(f"ticked {tick(Path(sys.argv[1]), sys.argv[2])} steps")
