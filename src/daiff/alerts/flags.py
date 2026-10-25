"""FR-A1: flag every sub-basin whose risk class is high (4) or very high (5) (D-19)."""

from __future__ import annotations

import pandas as pd


def flags(table: pd.DataFrame) -> list[int]:
    return [int(i) for i in table.loc[table["risk_class"].isin([4, 5]), "subbasin_id"]]
