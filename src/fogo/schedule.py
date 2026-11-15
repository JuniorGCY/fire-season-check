"""When each sensor looks: day and night passes.

MODIS (Terra about 10:30 and 22:30, Aqua about 13:30 and 01:30 local time) and VIIRS S-NPP (about
13:30 and 01:30) do not observe at the same hours, and fire has a daily cycle, so their counts
differ partly because of the schedule. This module measures, over the years both sensors fly,
what share of each sensor's hotspots is seen by day, and the MODIS/VIIRS ratio separately for
day and night passes. It is a diagnostic shown on the page; the harmonized series still uses
one monthly ratio for all passes.

FIRMS archive and NRT files carry a `daynight` column (D/N). If it is missing, local solar time
from the UTC acquisition time and the longitude decides (day = 06:00 to 18:00).
"""

from __future__ import annotations

import pandas as pd


def day_or_night(detections: pd.DataFrame) -> pd.Series:
    if "daynight" in detections.columns:
        return detections["daynight"].astype(str).str.upper().str[0]
    hhmm = pd.to_numeric(detections["acq_time"], errors="coerce").fillna(0)
    utc_hours = (hhmm // 100) + (hhmm % 100) / 60
    local = (utc_hours + detections["lon"].astype(float) / 15) % 24
    return local.between(6, 18, inclusive="left").map({True: "D", False: "N"})


def _counts(detections: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    inside = detections[(detections["day"] >= start) & (detections["day"] <= end)]
    return day_or_night(inside).value_counts().reindex(["D", "N"], fill_value=0)


def observation_summary(modis: pd.DataFrame, viirs: pd.DataFrame,
                        start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """Day shares and day/night MODIS-to-VIIRS ratios over `start`..`end` (both inclusive)."""
    m, v = _counts(modis, start, end), _counts(viirs, start, end)
    ratio = lambda kind: round(float(m[kind] / v[kind]), 4) if m[kind] and v[kind] else None  # noqa: E731
    share = lambda c: round(float(c["D"] / c.sum()), 4) if c.sum() else None  # noqa: E731
    return {
        "from": start.strftime("%Y-%m-%d"), "to": end.strftime("%Y-%m-%d"),
        "modis_detections": int(m.sum()), "viirs_detections": int(v.sum()),
        "modis_day_share": share(m), "viirs_day_share": share(v),
        "ratio_day": ratio("D"), "ratio_night": ratio("N"),
    }
