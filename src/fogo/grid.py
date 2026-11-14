"""Pre-aggregate hotspots into a coarse grid so a static page can answer any region.

The page has no server, so it cannot query FIRMS. Instead the pipeline counts detections per
grid cell (0.25 degrees, about 28 km) and per week, for each sensor, in a compact sparse form.
The browser sums the cells inside the area the user selects and applies the MODIS/VIIRS
ratios, so any rectangle inside the covered box works.

Sparse encoding per sensor (parallel arrays, sorted by week then cell):
  w  week index, stored as the difference from the previous entry (first one from 0)
  c  cell id = row * cols + col, row 0 at the south edge, col 0 at the west edge
  n  number of hotspots
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .calibrate import Calibration
from .load import BBox
from .series import VIIRS_SNPP_START

CELL_DEGREES = 0.25
# Monday of the week that contains 2000-11-01, the first day of MODIS Collection 6.1.
FIRST_WEEK = pd.Timestamp("2000-10-30")


def grid_shape(box: BBox, cell: float = CELL_DEGREES) -> tuple[int, int]:
    rows = math.ceil(round((box.max_lat - box.min_lat) / cell, 9))
    cols = math.ceil(round((box.max_lon - box.min_lon) / cell, 9))
    return rows, cols


def week_index(day: pd.Series) -> np.ndarray:
    return ((day - FIRST_WEEK).dt.days // 7).to_numpy()


def _encode(detections: pd.DataFrame, box: BBox, cell: float, n_weeks: int) -> dict[str, list[int]]:
    rows, cols = grid_shape(box, cell)
    if detections.empty:
        return {"w": [], "c": [], "n": []}
    row = np.clip(np.floor((detections["lat"].to_numpy(float) - box.min_lat) / cell).astype(int), 0, rows - 1)
    col = np.clip(np.floor((detections["lon"].to_numpy(float) - box.min_lon) / cell).astype(int), 0, cols - 1)
    week = week_index(detections["day"])
    keep = (week >= 0) & (week < n_weeks)
    frame = pd.DataFrame({"w": week[keep], "c": (row * cols + col)[keep]})
    counts = frame.value_counts().rename("n").reset_index().sort_values(["w", "c"])
    weeks = counts["w"].to_numpy()
    return {
        "w": np.diff(weeks, prepend=0).tolist(),
        "c": counts["c"].tolist(),
        "n": counts["n"].tolist(),
    }


def build_grid(
    modis: pd.DataFrame,
    viirs: pd.DataFrame,
    box: BBox,
    last_week_start: pd.Timestamp,
    calibration: Calibration,
    cell: float = CELL_DEGREES,
) -> dict:
    """Grid payload covering weeks FIRST_WEEK .. last_week_start (both inclusive)."""
    n_weeks = int((last_week_start - FIRST_WEEK).days // 7) + 1
    rows, cols = grid_shape(box, cell)
    switch = VIIRS_SNPP_START + pd.offsets.Week(weekday=0) if VIIRS_SNPP_START.weekday() else VIIRS_SNPP_START
    return {
        "cell_degrees": cell,
        "origin": {"lat": box.min_lat, "lon": box.min_lon},
        "rows": rows,
        "cols": cols,
        "first_week": FIRST_WEEK.strftime("%Y-%m-%d"),
        "n_weeks": n_weeks,
        "viirs_from_week": int((switch - FIRST_WEEK).days // 7),
        "ratio": {
            "quantity": calibration.quantity,
            "fit": calibration.kind,
            "single": round(calibration.single_ratio, 5),
            "monthly": {str(k): round(v, 5) for k, v in sorted(calibration.monthly_ratio.items())},
        },
        "modis": _encode(modis, box, cell, n_weeks),
        "viirs": _encode(viirs, box, cell, n_weeks),
    }
