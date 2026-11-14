"""One weekly series on the MODIS ruler: MODIS before VIIRS exists, scaled VIIRS after."""

from __future__ import annotations

import pandas as pd

from .calibrate import Calibration, apply

VIIRS_SNPP_START = pd.Timestamp("2012-01-20")


def harmonize(
    modis: pd.DataFrame,
    viirs: pd.DataFrame,
    calibration: Calibration,
    viirs_start: pd.Timestamp = VIIRS_SNPP_START,
) -> pd.DataFrame:
    """Return `value` and `source` ("MODIS" or "VIIRS scaled") per week.

    The switch happens at the first Monday on or after `viirs_start`, so no week mixes
    sensors. Weeks with no detections are zero.
    """
    quantity = calibration.quantity
    first = min(modis.index.min(), viirs.index.min())
    last = max(modis.index.max(), viirs.index.max())
    weeks = pd.date_range(first, last, freq="W-MON", name="week")

    switch = viirs_start + pd.offsets.Week(weekday=0) if viirs_start.weekday() else viirs_start
    from_modis = modis[quantity].reindex(weeks, fill_value=0.0)
    from_viirs = apply(calibration, viirs).reindex(weeks, fill_value=0.0)

    use_viirs = weeks >= switch
    value = from_modis.where(~use_viirs, from_viirs)
    source = pd.Series("MODIS", index=weeks).where(~use_viirs, "VIIRS scaled")
    return pd.DataFrame({"value": value, "source": source})
