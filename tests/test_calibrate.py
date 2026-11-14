import pandas as pd
import pytest

from fogo.calibrate import CalibrationError, apply, compare_methods, evaluate, fit


def _weekly(start: str, weeks: int, count, frp=None) -> pd.DataFrame:
    index = pd.date_range(start, periods=weeks, freq="W-MON", name="week")
    counts = [count(i) for i in range(weeks)] if callable(count) else [count] * weeks
    frps = [frp(i) for i in range(weeks)] if callable(frp) else [frp or 0.0] * weeks
    return pd.DataFrame({"count": counts, "frp": frps}, index=index)


def test_known_ratio_is_recovered_and_applied():
    viirs = _weekly("2020-06-01", 20, 400, 1000)
    modis = viirs * 0.25
    cal = fit(modis, viirs, "count", "single")
    assert cal.single_ratio == pytest.approx(0.25)
    assert apply(cal, viirs).iloc[0] == pytest.approx(100)


def test_exact_ratio_gives_zero_out_of_sample_error():
    viirs = _weekly("2012-06-04", 52 * 8, 400, 1000)
    modis = viirs * 0.25
    train, test = range(2012, 2016), range(2016, 2020)
    cal = fit(modis, viirs, "count", "single", years=train)
    result = evaluate(modis, viirs, cal, test, min_actual=20)
    assert result["weeks"] > 0 and result["median_error"] == pytest.approx(0, abs=1e-9)


def test_monthly_fit_beats_single_when_ratio_changes_with_season():
    viirs = _weekly("2012-01-02", 52 * 8, 400, 1000)
    month = pd.Series((viirs.index + pd.Timedelta(days=3)).month, index=viirs.index)
    modis = viirs.copy()
    seasonal = month.map(lambda m: 0.4 if m >= 8 else 0.2)
    modis["count"] = viirs["count"] * seasonal
    modis["frp"] = viirs["frp"] * seasonal
    table = compare_methods(modis, viirs, train_years=range(2012, 2016), test_years=range(2016, 2020))
    errors = table[table.quantity == "count"].set_index("kind")["median_error"]
    assert errors["monthly"] < errors["single"]


def test_low_weeks_are_not_scored():
    viirs = _weekly("2020-06-01", 10, 40)
    modis = viirs * 0.25  # 10 per week, below min_actual
    cal = fit(modis, viirs, "count", "single")
    assert evaluate(modis, viirs, cal, [2020], min_actual=20)["weeks"] == 0


def test_no_overlap_raises():
    modis = _weekly("2005-01-03", 10, 50)
    viirs = _weekly("2020-01-06", 10, 50)
    with pytest.raises(CalibrationError):
        fit(modis, viirs, "count", "single")


def test_month_without_overlap_falls_back_to_single_ratio():
    viirs = _weekly("2020-06-01", 4, 400)  # only June
    cal = fit(viirs * 0.25, viirs, "count", "monthly")
    assert cal.ratio_for(11) == pytest.approx(0.25)
