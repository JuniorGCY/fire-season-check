"""Export individual hotspots as small binary files, one per year, for the static page.

The page has no server, so the pipeline writes every detection once and the browser downloads
only the years the user asks for, then builds a CSV of single detections for the selected area.

File layout (little endian), one file per calendar year, rows sorted by day:
  bytes 0-3   magic "FP1\\0"
  bytes 4-7   n, number of detections (uint32)
  then six columns of n values each, in this order:
    lat    uint16  (latitude  - origin.lat) * 1000, so about 110 m steps
    lon    uint16  (longitude - origin.lon) * 1000
    day    uint16  days since 2000-01-01 (UTC acquisition date)
    time   uint16  acquisition time HHMM (UTC), 0 when the source file has none
    frp    uint16  fire radiative power in tenths of MW, capped at 6553.5
    sensor uint8   0 = MODIS, 1 = VIIRS
`index.json` next to the files gives the origin, scales, epoch and the list of years.

The MODIS/VIIRS ratio is not stored per point: the page applies the monthly ratio from grid.json,
so the sum of weights equals the harmonized count shown on the page.
"""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path

import numpy as np
import pandas as pd

from .load import BBox

MODIS, VIIRS = 0, 1
MAGIC = b"FP1\x00"
HEADER = struct.Struct("<4sI")
COORD_SCALE = 1000
FRP_SCALE = 10
EPOCH = pd.Timestamp("2000-01-01")
U16_MAX = 65535
TOLERANCE = 0.5 / COORD_SCALE  # rounding slack at the box edge


def _offset(values: np.ndarray, origin: float, low: float, high: float, name: str) -> np.ndarray:
    if len(values) and (values.min() < low - TOLERANCE or values.max() > high + TOLERANCE):
        raise ValueError(f"{name} outside the region box: {values.min()}..{values.max()}")
    return np.clip(np.rint((values - origin) * COORD_SCALE), 0, U16_MAX).astype("<u2")


def encode_year(frame: pd.DataFrame, sensor: int | None, box: BBox) -> bytes:
    """Encode detections of one year. `sensor` is 0/1, or None to read the frame's `sensor` column."""
    n = len(frame)
    frame = frame.sort_values("day", kind="stable")
    lat = _offset(frame["lat"].to_numpy(float), box.min_lat, box.min_lat, box.max_lat, "latitude")
    lon = _offset(frame["lon"].to_numpy(float), box.min_lon, box.min_lon, box.max_lon, "longitude")
    day = ((frame["day"] - EPOCH).dt.days.to_numpy()).clip(0, U16_MAX).astype("<u2")
    if "acq_time" in frame.columns:
        time = pd.to_numeric(frame["acq_time"], errors="coerce").fillna(0).clip(0, 2359).to_numpy()
    else:
        time = np.zeros(n)
    frp_source = frame["frp"] if "frp" in frame.columns else pd.Series(0.0, index=frame.index)
    frp = np.clip(np.rint(pd.to_numeric(frp_source, errors="coerce").fillna(0).to_numpy() * FRP_SCALE), 0, U16_MAX)
    kinds = np.full(n, sensor, dtype="u1") if sensor is not None else frame["sensor"].to_numpy("u1")
    return b"".join([
        HEADER.pack(MAGIC, n), lat.tobytes(), lon.tobytes(), day.tobytes(),
        time.astype("<u2").tobytes(), frp.astype("<u2").tobytes(), kinds.tobytes(),
    ])


def decode_year(data: bytes, box: BBox) -> pd.DataFrame:
    """Inverse of `encode_year` (used by tests; the page has its own JavaScript decoder)."""
    if len(data) < HEADER.size or data[:4] != MAGIC:
        raise ValueError("not a points file")
    n = HEADER.unpack_from(data)[1]
    if len(data) != HEADER.size + 11 * n:
        raise ValueError("points file has the wrong size")
    columns = [np.frombuffer(data, "<u2", n, HEADER.size + 2 * n * i) for i in range(5)]
    sensor = np.frombuffer(data, "u1", n, HEADER.size + 10 * n)
    lat, lon, day, time, frp = columns
    return pd.DataFrame({
        "lat": lat / COORD_SCALE + box.min_lat,
        "lon": lon / COORD_SCALE + box.min_lon,
        "day": EPOCH + pd.to_timedelta(day.astype("int64"), unit="D"),
        "time": time.astype(int),
        "frp": frp / FRP_SCALE,
        "sensor": sensor.astype(int),
    })


def build_points(modis: pd.DataFrame, viirs: pd.DataFrame, box: BBox, out_dir: Path,
                 through: pd.Timestamp) -> dict:
    """Write one file per year (days up to and including `through`) plus `index.json`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.bin"):
        if re.fullmatch(r"\d{4}\.bin", stale.name):
            stale.unlink()
    parts = [frame.assign(sensor=kind) for frame, kind in ((modis, MODIS), (viirs, VIIRS)) if len(frame)]
    everything = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        {"lat": [], "lon": [], "day": pd.to_datetime([]), "sensor": []})
    everything = everything[everything["day"] <= through]
    years = []
    for year, frame in everything.groupby(everything["day"].dt.year):
        data = encode_year(frame, None, box)
        name = f"{year}.bin"
        (out_dir / name).write_bytes(data)
        years.append({"year": int(year), "file": name, "n": len(frame), "bytes": len(data)})
    index = {
        "format": 1,
        "origin": {"lat": box.min_lat, "lon": box.min_lon},
        "scale": COORD_SCALE, "frp_scale": FRP_SCALE, "epoch": "2000-01-01",
        "sensors": {"modis": MODIS, "viirs": VIIRS},
        "through": through.strftime("%Y-%m-%d"),
        "years": years,
    }
    (out_dir / "index.json").write_text(json.dumps(index, separators=(",", ":")))
    return index
