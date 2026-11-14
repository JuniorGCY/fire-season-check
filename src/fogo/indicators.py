"""The question a fire manager already asks: is this season above or below normal?

"Normal" is the average of the previous N complete years (default 10) for the same
weeks, the same yardstick Tocantins uses in its state fire plan (goal: below the 10-year
average). The comparison is cumulative, year to date, so one noisy week cannot flip it.
ISO week 53 is ignored so every year has 52 comparable weeks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

WEEKS = range(1, 53)
Status = Literal["below", "within", "above"]


class InsufficientHistory(ValueError):
    """Fewer complete prior years than needed for a meaningful normal."""


def pivot_by_year(series: pd.Series) -> pd.DataFrame:
    """Rows = ISO year, columns = weeks 1..52, NaN where the series has no week."""
    iso = series.index.isocalendar()
    frame = pd.DataFrame({"year": iso.year.to_numpy(), "week": iso.week.to_numpy(),
                          "value": series.to_numpy()})
    frame = frame[frame["week"] <= 52]
    return frame.pivot(index="year", columns="week", values="value").reindex(columns=list(WEEKS))


def complete_years(table: pd.DataFrame) -> list[int]:
    return [int(year) for year, row in table.iterrows() if not row.isna().any()]


@dataclass(frozen=True)
class Headline:
    year: int
    last_week: int
    ytd: float
    normal_ytd: float
    pct_vs_normal: float
    status: Status
    rank: int            # 1 = highest of the compared years (including this one)
    compared_years: int  # number of years in the comparison, including this one
    years_used: tuple[int, ...]
    provisional: bool

    def text(self, region: str, unit: str = "hotspots", through: str | None = None) -> str:
        direction = "more" if self.pct_vs_normal >= 0 else "fewer"
        where = {
            "below": "below the range of the last years",
            "within": "within the range of the last years",
            "above": "above the range of the last years",
        }[self.status]
        period = through if through else f"week {self.last_week} of {self.year}"
        sentence = (
            f"Through {period}, {region} had "
            f"{abs(self.pct_vs_normal):.0f}% {direction} {unit} than the average of the "
            f"previous {len(self.years_used)} years ({where})."
        )
        return sentence + (" Latest weeks are provisional." if self.provisional else "")


def headline(
    series: pd.Series,
    year: int,
    last_week: int,
    n_years: int = 10,
    min_years: int = 5,
    final_until: pd.Timestamp | None = None,
) -> Headline:
    """Compare weeks 1..`last_week` of `year` with the same weeks of the previous years."""
    table = pivot_by_year(series)
    prior = [y for y in complete_years(table) if y < year][-n_years:]
    if len(prior) < min_years:
        raise InsufficientHistory(f"need at least {min_years} complete prior years, have {len(prior)}")
    weeks = list(range(1, last_week + 1))
    current = table.loc[year, weeks]
    if current.isna().any():
        raise InsufficientHistory(f"{year} has missing weeks before week {last_week}")

    cumulative = table.loc[prior, weeks].sum(axis=1)
    ytd = float(current.sum())
    normal = float(cumulative.mean())
    pct = (ytd / normal - 1.0) * 100.0 if normal > 0 else float("nan")
    status: Status = "below" if ytd < cumulative.min() else "above" if ytd > cumulative.max() else "within"
    rank = 1 + int((cumulative > ytd).sum())

    last_monday = pd.Timestamp.fromisocalendar(year, last_week, 1)
    provisional = final_until is not None and last_monday + pd.Timedelta(days=6) > final_until
    return Headline(year, last_week, ytd, normal, pct, status, rank, len(prior) + 1,
                    tuple(prior), provisional)


def weekly_curve(series: pd.Series, year: int, n_years: int = 10, min_years: int = 5) -> pd.DataFrame:
    """Per week 1..52: this year, the normal (mean), and the lowest/highest prior year."""
    table = pivot_by_year(series)
    prior = [y for y in complete_years(table) if y < year][-n_years:]
    if len(prior) < min_years:
        raise InsufficientHistory(f"need at least {min_years} complete prior years, have {len(prior)}")
    history = table.loc[prior]
    current = table.loc[year] if year in table.index else pd.Series(np.nan, index=list(WEEKS))
    return pd.DataFrame({
        "current": current,
        "normal": history.mean(),
        "low": history.min(),
        "high": history.max(),
    }).rename_axis("week")
