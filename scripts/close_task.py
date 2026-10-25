"""Close a plan task: tick its checkboxes and update docs/STATUS.md "Last done" / "Next task".

Usage: uv run python scripts/close_task.py <plan.md> <task> "<label>" "<next task text>"
Commit and push afterwards (see CLAUDE.md).
"""

import re
import sys
from pathlib import Path

from tick_task import tick

STATUS = Path(__file__).resolve().parents[1] / "docs" / "STATUS.md"


def update_status(done: str, nxt: str) -> None:
    text = STATUS.read_text(encoding="utf-8")
    text = re.sub(r"- \*\*Last done:\*\* .*", lambda _: f"- **Last done:** {done}", text)
    text = re.sub(r"- \*\*Next task:\*\* .*", lambda _: f"- **Next task:** {nxt}", text)
    STATUS.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    plan, task, done, nxt = sys.argv[1:5]
    tick(Path(plan), task)
    update_status(done, nxt)
