"""Read NASA FIRMS hotspot CSVs (MODIS and VIIRS) for one region.

Columns used: latitude, longitude, acq_date (UTC), frp. If a `type` column exists
(archive files), only type "0" (presumed vegetation fire) is kept; NRT files have no
`type` and are not filtered. Several files from the same sensor can be read together
(e.g. archive + near-real-time): a row identical to a row of an earlier file is
ignored so it is not counted twice. Repeated rows inside one file are kept.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

REQUIRED_COLUMNS = ("latitude", "longitude", "acq_date")
KEY_COLUMNS = ("latitude", "longitude", "acq_date", "acq_time", "satellite")
VEGETATION_FIRE_TYPE = "0"


class FireCsvError(ValueError):
    """A FIRMS CSV is missing a required column or has an unreadable value."""


@dataclass(frozen=True)
class BBox:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def __post_init__(self) -> None:
        # Boxes crossing the antimeridian (min_lon > max_lon) are not supported.
        if not (-90 <= self.min_lat <= 90 and -90 <= self.max_lat <= 90):
            raise ValueError("latitude must be between -90 and 90 degrees")
        if not (-180 <= self.min_lon <= 180 and -180 <= self.max_lon <= 180):
            raise ValueError("longitude must be between -180 and 180 degrees")
        if self.min_lat >= self.max_lat:
            raise ValueError(f"south ({self.min_lat}) must be below north ({self.max_lat})")
        if self.min_lon >= self.max_lon:
            raise ValueError(f"west ({self.min_lon}) must be left of east ({self.max_lon})")

    def mask(self, lat: pd.Series, lon: pd.Series) -> pd.Series:
        return (
            lat.between(self.min_lat, self.max_lat) & lon.between(self.min_lon, self.max_lon)
        )


# Bounding box around Tocantins, Brazil. It also covers slivers of neighbouring states:
# a known limitation until municipal polygons are used.
TOCANTINS = BBox(min_lat=-13.5, max_lat=-5.1, min_lon=-50.8, max_lon=-45.6)


def read_firms_csv(path: Path, box: BBox) -> pd.DataFrame:
    """Return one row per detection inside `box`: key columns, `day` (datetime) and `frp`."""
    wanted = {*REQUIRED_COLUMNS, *KEY_COLUMNS, "type", "frp", "daynight"}  # skip the others: files are large
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, usecols=lambda name: name in wanted)
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise FireCsvError(f"{path.name}: missing columns {missing}")
    try:
        lat = pd.to_numeric(frame["latitude"])
        lon = pd.to_numeric(frame["longitude"])
        day = pd.to_datetime(frame["acq_date"], format="%Y-%m-%d")
    except (ValueError, TypeError) as error:
        raise FireCsvError(f"{path.name}: {error}") from error

    keep = box.mask(lat, lon)
    if "type" in frame.columns:
        keep &= frame["type"] == VEGETATION_FIRE_TYPE

    key_columns = [c for c in KEY_COLUMNS if c in frame.columns]
    result = frame.loc[keep, key_columns].copy()
    if "daynight" in frame.columns:
        result["daynight"] = frame.loc[keep, "daynight"]
    result["day"] = day[keep]
    result["lat"] = lat[keep]
    result["lon"] = lon[keep]
    if "frp" in frame.columns:
        result["frp"] = pd.to_numeric(frame.loc[keep, "frp"], errors="coerce").fillna(0.0)
    else:
        result["frp"] = 0.0
    return result.reset_index(drop=True)


def read_firms(paths: Iterable[Path | str], box: BBox) -> pd.DataFrame:
    """Read and merge several CSVs of one sensor without double counting across files."""
    frames: list[pd.DataFrame] = []
    seen: set[tuple[str, ...]] = set()
    for path in paths:
        frame = read_firms_csv(Path(path), box)
        key_columns = [c for c in KEY_COLUMNS if c in frame.columns]
        keys = list(frame[key_columns].itertuples(index=False, name=None))
        is_new = [key not in seen for key in keys]
        frames.append(frame[is_new])
        seen.update(keys)
    if not frames:
        return pd.DataFrame(columns=[*KEY_COLUMNS, "day", "lat", "lon", "frp"])
    return pd.concat(frames, ignore_index=True)
