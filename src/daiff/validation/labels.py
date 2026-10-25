"""Reference-label store for the Labelling page (SRS 7.3; committed under reference/)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd

COLUMNS = ["point_id", "interpreter", "label_t0", "label_t", "note"]


class LabelStore:
    def __init__(self, csv_path: Path) -> None:
        self.path = Path(csv_path)

    def all(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame(columns=COLUMNS)
        return pd.read_csv(self.path, dtype=str, keep_default_na=False, encoding="utf-8")

    def upsert(
        self, point_id: str, interpreter: str, label_t0: str, label_t: str, note: str = ""
    ) -> None:
        df = self.all()
        df = df[~((df.point_id == point_id) & (df.interpreter == interpreter))]
        row = pd.DataFrame([[point_id, interpreter, label_t0, label_t, note]], columns=COLUMNS)
        df = pd.concat([df, row], ignore_index=True).sort_values(["point_id", "interpreter"])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        os.close(fd)
        df.to_csv(tmp, index=False, lineterminator="\n", encoding="utf-8")
        os.replace(tmp, self.path)
