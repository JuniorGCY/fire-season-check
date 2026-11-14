"""Aggregate detections into a continuous weekly series (weeks start on Monday)."""

from __future__ import annotations

import pandas as pd


def weekly_series(detections: pd.DataFrame) -> pd.DataFrame:
    """Return `count` and `frp` (sum) per week, with zero-filled weeks in between.

    The index is the Monday of each week and is named `week`.
    """
    empty_index = pd.DatetimeIndex([], name="week")
    if detections.empty:
        return pd.DataFrame({"count": [], "frp": []}, index=empty_index)

    week = detections["day"].dt.to_period("W-SUN").dt.start_time
    grouped = detections.groupby(week).agg(count=("day", "size"), frp=("frp", "sum"))
    all_weeks = pd.date_range(grouped.index.min(), grouped.index.max(), freq="W-MON")
    return grouped.reindex(all_weeks, fill_value=0).rename_axis("week")
