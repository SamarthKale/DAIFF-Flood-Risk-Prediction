"""Design rainfall (Gumbel, OI-3) and rainfall climatology per sub-basin (D-16)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

EULER = 0.5772


def gumbel_design_rainfall(annual_max: np.ndarray, T: int = 10) -> float:
    """Method-of-moments Gumbel quantile: mean + K_T · std (sample std)."""
    x = np.asarray(annual_max, dtype=np.float64)
    k = -(math.sqrt(6) / math.pi) * (EULER + math.log(math.log(T / (T - 1))))
    return float(x.mean() + k * x.std(ddof=1))


def _with_year(daily: pd.DataFrame) -> pd.DataFrame:
    df = daily.copy()
    df["year"] = pd.to_datetime(df["date"]).dt.year
    return df


def design_rainfall_by_subbasin(daily: pd.DataFrame, T: int) -> pd.Series:
    df = _with_year(daily)
    maxima = df.groupby(["subbasin_id", "year"])["precip_mm"].max()
    return maxima.groupby(level=0).apply(lambda s: gumbel_design_rainfall(s.to_numpy(), T))


def mean_annual_rainfall(daily: pd.DataFrame) -> pd.Series:
    df = _with_year(daily)
    totals = df.groupby(["subbasin_id", "year"])["precip_mm"].sum()
    return totals.groupby(level=0).mean()
