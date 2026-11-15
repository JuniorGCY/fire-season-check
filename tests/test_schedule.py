import pandas as pd
import pytest

from fogo.schedule import day_or_night, observation_summary


def _detections(rows):
    """rows: (day, acq_time HHMM, lon, daynight or None)"""
    frame = pd.DataFrame({
        "day": pd.to_datetime([r[0] for r in rows]),
        "acq_time": [r[1] for r in rows],
        "lon": [r[2] for r in rows],
        "lat": [-10.0] * len(rows),
    })
    if any(r[3] is not None for r in rows):
        frame["daynight"] = [r[3] for r in rows]
    return frame


def test_daynight_column_is_used_when_present():
    frame = _detections([("2020-01-01", "0400", -48.0, "D"), ("2020-01-01", "1600", -48.0, "N")])
    assert day_or_night(frame).tolist() == ["D", "N"]  # the column wins over the clock


def test_without_the_column_local_solar_time_decides():
    # at 48 degrees west, local solar time is UTC - 3.2 h
    frame = _detections([("2020-01-01", "1630", -48.0, None),    # 13:18 local -> day
                         ("2020-01-01", "0430", -48.0, None),    # 01:18 local -> night
                         ("2020-01-01", "0900", -48.0, None)])   # 05:48 local -> night
    assert day_or_night(frame).tolist() == ["D", "N", "N"]


def test_summary_gives_shares_and_a_ratio_for_day_and_for_night():
    modis = _detections([("2015-08-01", "1630", -48.0, "D")] * 30 + [("2015-08-01", "0430", -48.0, "N")] * 10)
    viirs = _detections([("2015-08-01", "1630", -48.0, "D")] * 100 + [("2015-08-01", "0430", -48.0, "N")] * 100)
    summary = observation_summary(modis, viirs, start=pd.Timestamp("2012-01-20"), end=pd.Timestamp("2026-01-01"))
    assert summary["modis_day_share"] == pytest.approx(0.75)
    assert summary["viirs_day_share"] == pytest.approx(0.5)
    assert summary["ratio_day"] == pytest.approx(0.30)
    assert summary["ratio_night"] == pytest.approx(0.10)
    assert summary["modis_detections"] == 40 and summary["viirs_detections"] == 200


def test_only_the_overlap_period_counts():
    modis = _detections([("2005-08-01", "1630", -48.0, "D"), ("2015-08-01", "1630", -48.0, "D")])
    viirs = _detections([("2015-08-01", "1630", -48.0, "D")])
    summary = observation_summary(modis, viirs, start=pd.Timestamp("2012-01-20"), end=pd.Timestamp("2026-01-01"))
    assert summary["modis_detections"] == 1


def test_no_night_detections_gives_no_night_ratio():
    modis = _detections([("2015-08-01", "1630", -48.0, "D")])
    viirs = _detections([("2015-08-01", "1630", -48.0, "D")])
    summary = observation_summary(modis, viirs, start=pd.Timestamp("2012-01-20"), end=pd.Timestamp("2026-01-01"))
    assert summary["ratio_night"] is None and summary["ratio_day"] == pytest.approx(1.0)
