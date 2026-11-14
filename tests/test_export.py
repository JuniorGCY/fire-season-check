import json
from datetime import datetime, timezone

import pandas as pd

from fogo.calibrate import Calibration
from fogo.export import build_payload, write_payload
from fogo.indicators import headline
from test_series_and_indicators import PRIOR, weekly_for_years


def _payload(synthetic=False):
    series = weekly_for_years({**PRIOR, 2025: 250.0}, last_year_weeks=30)
    head = headline(series, 2025, 30)
    cal = Calibration("monthly", "count", 0.25, {6: 0.2, 7: 0.3})
    error = {"median_error": 0.06, "p90_error": float("nan"), "weeks": 120}
    return build_payload(series, head, cal, error, "Tocantins", "fit on 2012-2013, tested on 2014",
                         synthetic=synthetic, now=datetime(2026, 11, 14, tzinfo=timezone.utc))


def test_payload_has_headline_curve_method_and_sources():
    payload = _payload()
    assert payload["headline"]["status"] == "above"
    assert len(payload["curve"]) == 52
    assert payload["curve"][29]["current"] == 250.0 and payload["curve"][30]["current"] is None
    assert payload["method"]["validation"].startswith("fit on")
    assert payload["data_through"] == "2025-07-27"
    assert payload["sources"] and payload["trust_note"]


def test_nan_becomes_null_in_json(tmp_path):
    path = tmp_path / "out" / "tocantins.json"
    write_payload(_payload(), path)
    loaded = json.loads(path.read_text())
    assert loaded["method"]["weekly_error_p90"] is None
    assert loaded["synthetic"] is False


def test_synthetic_flag_is_carried():
    assert _payload(synthetic=True)["synthetic"] is True
