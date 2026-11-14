"""Write the small JSON file the static page reads. No server, no secrets."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .calibrate import Calibration
from .indicators import Headline, weekly_curve

SOURCES = [
    "NASA FIRMS, MODIS Collection 6.1 active fire (Terra and Aqua), 2000 to present",
    "NASA FIRMS, VIIRS S-NPP 375 m active fire, 2012 to present",
]
TRUST_NOTE = (
    "Cloud and smoke can hide fire. A hotspot is a satellite pixel (about 1 km² for MODIS, "
    "0.14 km² for VIIRS), not a single fire or a burned area. Fire radiative power is an "
    "intensity proxy. Small or cool fires can be missed. The latest weeks are provisional."
)


def _clean(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def build_payload(
    series: pd.Series,
    headline: Headline,
    calibration: Calibration,
    error: dict[str, float],
    region: str,
    validation: str,
    synthetic: bool = False,
    now: datetime | None = None,
    checks: list[dict] | None = None,
) -> dict[str, Any]:
    curve = weekly_curve(series, headline.year)
    unit = "hotspots" if calibration.quantity == "count" else "fire radiative power (MW)"
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    last_monday = pd.Timestamp.fromisocalendar(headline.year, headline.last_week, 1)
    return {
        "synthetic": synthetic,
        "region": region,
        "unit": unit,
        "generated_on": stamp,
        "data_through": (last_monday + pd.Timedelta(days=6)).strftime("%Y-%m-%d"),
        "headline": {
            "text": headline.text(
                region,
                unit="hotspots" if calibration.quantity == "count" else "fire power",
                through=(last_monday + pd.Timedelta(days=6)).strftime("%B %-d, %Y"),
            ),
            "year": headline.year,
            "last_week": headline.last_week,
            "pct_vs_normal": _clean(round(headline.pct_vs_normal, 1)),
            "status": headline.status,
            "rank": headline.rank,
            "compared_years": headline.compared_years,
            "years_used": list(headline.years_used),
            "provisional": headline.provisional,
        },
        "curve": [
            {"week": int(week), **{k: _clean(None if pd.isna(v) else round(float(v), 1))
                                   for k, v in row.items()}}
            for week, row in curve.iterrows()
        ],
        "method": {
            "quantity": calibration.quantity,
            "fit": calibration.kind,
            "ratio_viirs_to_modis": round(calibration.single_ratio, 4),
            "monthly_ratio": {str(k): round(v, 4) for k, v in sorted(calibration.monthly_ratio.items())},
            "weekly_error_median": _clean(round(error["median_error"], 3)),
            "weekly_error_p90": _clean(round(error["p90_error"], 3)),
            "weeks_scored": int(error["weeks"]),
            "validation": validation,
        },
        "robustness": checks or [],
        "sources": SOURCES,
        "trust_note": TRUST_NOTE,
    }


def write_payload(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
