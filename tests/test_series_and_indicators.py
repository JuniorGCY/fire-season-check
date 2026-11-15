import pandas as pd
import pytest

from fogo.calibrate import Calibration
from fogo.indicators import InsufficientHistory, headline, weekly_curve
from fogo.series import harmonize


def weekly_for_years(values_by_year: dict[int, float], last_year_weeks: int | None = None) -> pd.Series:
    """Constant weekly value per ISO year; the last year may be cut at `last_year_weeks`."""
    pieces = []
    years = sorted(values_by_year)
    for year in years:
        weeks = 52 if (year != years[-1] or last_year_weeks is None) else last_year_weeks
        index = [pd.Timestamp.fromisocalendar(year, w, 1) for w in range(1, weeks + 1)]
        pieces.append(pd.Series(values_by_year[year], index=index))
    return pd.concat(pieces)


PRIOR = {2015 + i: 100.0 + 10 * i for i in range(10)}  # 2015..2024: 100, 110, ... 190


# ---------- headline ----------
def test_above_normal_percent_and_status():
    series = weekly_for_years({**PRIOR, 2025: 250.0}, last_year_weeks=30)
    result = headline(series, year=2025, last_week=30)
    assert result.normal_ytd == pytest.approx(145.0 * 30)
    assert result.pct_vs_normal == pytest.approx((250 / 145 - 1) * 100)
    assert result.status == "above" and result.rank == 1 and result.compared_years == 11


def test_median_of_previous_years_is_reported_next_to_the_mean():
    # one extreme year pulls the mean up but not the median
    prior = {2015 + i: 100.0 for i in range(9)} | {2024: 1000.0}
    result = headline(weekly_for_years({**prior, 2025: 100.0}, 30), 2025, 30)
    assert result.normal_ytd == pytest.approx(190.0 * 30)
    assert result.median_ytd == pytest.approx(100.0 * 30)
    assert result.pct_vs_median == pytest.approx(0.0)
    assert result.pct_vs_normal == pytest.approx((100 / 190 - 1) * 100)


def test_below_and_within_status():
    low = headline(weekly_for_years({**PRIOR, 2025: 50.0}, 30), 2025, 30)
    mid = headline(weekly_for_years({**PRIOR, 2025: 145.0}, 30), 2025, 30)
    assert low.status == "below" and low.pct_vs_normal < 0
    assert mid.status == "within" and mid.pct_vs_normal == pytest.approx(0)


def test_only_the_last_ten_complete_years_are_used():
    series = weekly_for_years({2010: 1000.0, **PRIOR, 2025: 145.0}, 30)
    assert headline(series, 2025, 30).years_used == tuple(range(2015, 2025))


def test_incomplete_prior_year_is_excluded():
    prior = dict(PRIOR)
    series = weekly_for_years({**prior, 2025: 145.0}, 30)
    broken = series[series.index != pd.Timestamp.fromisocalendar(2020, 10, 1)]
    assert 2020 not in headline(broken, 2025, 30).years_used


def test_too_little_history_raises():
    series = weekly_for_years({2023: 100.0, 2024: 100.0, 2025: 100.0}, 30)
    with pytest.raises(InsufficientHistory):
        headline(series, 2025, 30)


def test_week_53_is_ignored():
    series = weekly_for_years({**PRIOR, 2025: 145.0}, 30)
    extra = pd.Series([9999.0], index=[pd.Timestamp.fromisocalendar(2020, 53, 1)])  # 2020 has a week 53
    assert headline(pd.concat([series, extra]).sort_index(), 2025, 30).normal_ytd == pytest.approx(145.0 * 30)


def test_provisional_flag_follows_final_cutoff():
    series = weekly_for_years({**PRIOR, 2025: 145.0}, 30)
    cutoff = pd.Timestamp.fromisocalendar(2025, 28, 7)
    assert headline(series, 2025, 30, final_until=cutoff).provisional
    assert not headline(series, 2025, 20, final_until=cutoff).provisional


def test_text_contains_number_and_direction():
    text = headline(weekly_for_years({**PRIOR, 2025: 50.0}, 30), 2025, 30).text("Tocantins")
    assert "Tocantins" in text and "fewer" in text and "week 30 of 2025" in text


# ---------- curve ----------
def test_curve_has_52_weeks_and_a_band():
    curve = weekly_curve(weekly_for_years({**PRIOR, 2025: 145.0}, 30), 2025)
    assert len(curve) == 52
    assert curve.loc[1, "low"] == 100 and curve.loc[1, "high"] == 190 and curve.loc[1, "normal"] == 145
    assert curve.loc[30, "current"] == 145 and pd.isna(curve.loc[31, "current"])


# ---------- harmonize ----------
def test_switches_from_modis_to_scaled_viirs_on_a_monday():
    weeks = pd.date_range("2012-01-02", periods=6, freq="W-MON", name="week")
    modis = pd.DataFrame({"count": [10.0] * 6, "frp": [0.0] * 6}, index=weeks)
    viirs = pd.DataFrame({"count": [100.0] * 6, "frp": [0.0] * 6}, index=weeks)
    cal = Calibration("single", "count", 0.5, {})
    result = harmonize(modis, viirs, cal, viirs_start=pd.Timestamp("2012-01-20"))
    # 2012-01-20 is a Friday, so VIIRS starts on Monday 2012-01-23
    assert list(result["source"]) == ["MODIS", "MODIS", "MODIS", "VIIRS scaled", "VIIRS scaled", "VIIRS scaled"]
    assert list(result["value"]) == [10, 10, 10, 50, 50, 50]
