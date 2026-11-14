"""Common ruler between MODIS and VIIRS, with an honest out-of-sample error.

MODIS (1 km pixels, since 2000) sees fewer, larger hotspots than VIIRS (375 m, since 2012).
To compare years before and after VIIRS, we scale VIIRS to the MODIS ruler using the weeks
where both sensors exist, and measure how wrong that scaling is on years it did not see.

Two quantities are scaled: hotspot `count` and fire radiative power `frp` (a proxy for
intensity). Two fits exist: one ratio for the whole year ("single") or one per calendar
month ("monthly"), because the ratio can change with the season.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

import numpy as np
import pandas as pd

Quantity = Literal["count", "frp"]
Kind = Literal["single", "monthly"]
SEASON_MONTHS = (6, 7, 8, 9, 10, 11)


class CalibrationError(ValueError):
    """Not enough overlap between the two sensors to fit a ratio."""


@dataclass(frozen=True)
class Calibration:
    kind: Kind
    quantity: Quantity
    single_ratio: float
    monthly_ratio: dict[int, float]

    def ratio_for(self, month: int) -> float:
        if self.kind == "monthly":
            return self.monthly_ratio.get(month, self.single_ratio)
        return self.single_ratio


def _week_month(index: pd.DatetimeIndex) -> pd.Index:
    """Calendar month of the Thursday of each ISO week (the week's majority month)."""
    return (index + pd.Timedelta(days=3)).month


def _overlap(modis: pd.DataFrame, viirs: pd.DataFrame, years: Iterable[int] | None) -> pd.DataFrame:
    joined = modis.join(viirs, how="inner", lsuffix="_m", rsuffix="_v")
    if years is not None:
        joined = joined[(joined.index + pd.Timedelta(days=3)).year.isin(list(years))]
    return joined


def fit(
    modis: pd.DataFrame,
    viirs: pd.DataFrame,
    quantity: Quantity,
    kind: Kind,
    years: Iterable[int] | None = None,
) -> Calibration:
    """Fit MODIS ≈ ratio × VIIRS on the weeks both sensors cover (optionally only `years`)."""
    both = _overlap(modis, viirs, years)
    m, v = both[f"{quantity}_m"], both[f"{quantity}_v"]
    if both.empty or v.sum() <= 0 or m.sum() <= 0:
        raise CalibrationError("no usable overlap between MODIS and VIIRS")
    single = float(m.sum() / v.sum())
    monthly: dict[int, float] = {}
    months = _week_month(both.index)
    for month in sorted(set(months)):
        pick = months == month
        if v[pick].sum() > 0 and m[pick].sum() > 0:
            monthly[int(month)] = float(m[pick].sum() / v[pick].sum())
    return Calibration(kind, quantity, single, monthly)


def apply(calibration: Calibration, viirs: pd.DataFrame) -> pd.Series:
    """VIIRS weekly values expressed on the MODIS ruler."""
    ratios = pd.Series(
        [calibration.ratio_for(int(m)) for m in _week_month(viirs.index)], index=viirs.index
    )
    return viirs[calibration.quantity] * ratios


def evaluate(
    modis: pd.DataFrame,
    viirs: pd.DataFrame,
    calibration: Calibration,
    years: Iterable[int],
    min_actual: float,
    season_months: Iterable[int] = SEASON_MONTHS,
) -> dict[str, float]:
    """Relative weekly error of the scaled VIIRS against real MODIS, on `years` only.

    Only weeks in `season_months` where MODIS has at least `min_actual` are scored, so a
    tiny off-season week cannot dominate the percentage.
    """
    both = _overlap(modis, viirs, years)
    month = pd.Series(_week_month(both.index), index=both.index)
    both = both[month.isin(list(season_months))]
    actual = both[f"{calibration.quantity}_m"]
    predicted = apply(calibration, both[[f"{calibration.quantity}_v"]].rename(
        columns={f"{calibration.quantity}_v": calibration.quantity}))
    scored = actual >= min_actual
    if not scored.any():
        return {"weeks": 0, "median_error": float("nan"), "p90_error": float("nan")}
    error = ((predicted[scored] - actual[scored]).abs() / actual[scored]).to_numpy()
    return {
        "weeks": int(scored.sum()),
        "median_error": float(np.median(error)),
        "p90_error": float(np.percentile(error, 90)),
    }


def compare_methods(
    modis: pd.DataFrame,
    viirs: pd.DataFrame,
    train_years: Iterable[int],
    test_years: Iterable[int],
    min_count: float = 20,
    min_frp: float = 500,
) -> pd.DataFrame:
    """Fit on `train_years`, score on `test_years`, for every quantity and kind."""
    rows = []
    for quantity, min_actual in (("count", min_count), ("frp", min_frp)):
        for kind in ("single", "monthly"):
            cal = fit(modis, viirs, quantity, kind, years=train_years)
            rows.append({"quantity": quantity, "kind": kind,
                         **evaluate(modis, viirs, cal, test_years, min_actual)})
    return pd.DataFrame(rows)
