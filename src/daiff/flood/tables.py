"""Sub-basin summary table — SRS Appendix C Table 25 (+ name, risk_class; D-19)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from daiff.flood.predict import NODATA_CLASS, risk_classes
from daiff.zones import zonal_mean

TABLE_COLUMNS = [
    "subbasin_id",
    "name",
    "area_km2",
    "forest_loss_ha",
    "forest_fraction",
    "mean_s",
    "mean_delta_s",
    *[f"area_class_{i}" for i in range(1, 6)],
    "area_moved_up_km2",
    "risk_class",
    "risk_flag",
]


def subbasin_table(
    zones: np.ndarray,
    names: pd.DataFrame,
    loss_ha: pd.Series,
    f: np.ndarray,
    S: np.ndarray,
    dS: np.ndarray,
    cls_t: np.ndarray,
    cls_t0: np.ndarray,
    breaks: Sequence[float],
    cell_area: float,
) -> pd.DataFrame:
    ids = [int(i) for i in names["subbasin_id"]]
    km2 = cell_area / 1e6
    mean_s = zonal_mean(S, zones, ids)
    rows = []
    moved = (cls_t != NODATA_CLASS) & (cls_t0 != NODATA_CLASS) & (cls_t > cls_t0)
    for sid, name in zip(ids, names["name"], strict=True):
        sel = zones == sid
        row = {
            "subbasin_id": sid,
            "name": name,
            "area_km2": sel.sum() * km2,
            "forest_loss_ha": float(loss_ha.get(sid, 0.0)),
            "forest_fraction": zonal_mean(f, zones, [sid]).iloc[0],
            "mean_s": mean_s.loc[sid],
            "mean_delta_s": zonal_mean(dS, zones, [sid]).iloc[0],
        }
        for c in range(1, 6):
            row[f"area_class_{c}"] = (sel & (cls_t == c)).sum() * km2
        row["area_moved_up_km2"] = (sel & moved).sum() * km2
        cls = int(risk_classes(np.array([mean_s.loc[sid]]), breaks)[0])
        row["risk_class"] = cls
        row["risk_flag"] = "yes" if cls in (4, 5) else "no"
        rows.append(row)
    table = pd.DataFrame(rows, columns=TABLE_COLUMNS)
    float_cols = table.select_dtypes("float").columns
    table[float_cols] = table[float_cols].round(6)
    return table.sort_values("subbasin_id").reset_index(drop=True)


def write_table(table: pd.DataFrame, path) -> None:
    table.to_csv(path, index=False, lineterminator="\n", encoding="utf-8")
