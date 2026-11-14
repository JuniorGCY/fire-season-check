import json

import pandas as pd
import pytest

from fogo.cli import run

HEADER = "latitude,longitude,acq_date,acq_time,satellite,frp,type\n"


def _write_sensor(path, first_year, last_day, rows_per_week, name):
    mondays = pd.date_range(f"{first_year}-01-02", last_day, freq="W-MON")
    lines = [f"-8,-48,{d:%Y-%m-%d},0100,{name},10,0" for d in mondays for _ in range(rows_per_week)]
    path.write_text(HEADER + "\n".join(lines) + "\n")
    return path


def test_end_to_end_on_a_constant_world(tmp_path):
    # MODIS sees 20 hotspots per week, VIIRS sees 80, every week of every year.
    modis = _write_sensor(tmp_path / "m.csv", 2000, "2025-10-13", 20, "Terra")
    viirs = _write_sensor(tmp_path / "v.csv", 2012, "2025-10-13", 80, "SNPP")
    out = tmp_path / "web" / "data" / "tocantins.json"

    payload = run([modis], [viirs], out)
    loaded = json.loads(out.read_text())

    assert loaded == payload
    assert payload["synthetic"] is False
    assert payload["headline"]["year"] == 2025 and payload["headline"]["last_week"] == 41
    assert payload["headline"]["status"] == "within"
    assert payload["headline"]["pct_vs_normal"] == pytest.approx(0, abs=0.2)
    assert payload["method"]["ratio_viirs_to_modis"] == pytest.approx(0.25, abs=0.01)
    assert payload["method"]["weekly_error_median"] == pytest.approx(0, abs=0.01)
    assert len(payload["curve"]) == 52
    assert len(payload["robustness"]) == 4
    assert all(abs(c["pct_vs_normal"]) < 1 for c in payload["robustness"])


def test_data_end_is_where_both_sensors_reach(tmp_path):
    # MODIS runs 12 days longer than VIIRS: the headline must stop where VIIRS stops.
    modis = _write_sensor(tmp_path / "m.csv", 2000, "2025-10-27", 20, "Terra")
    viirs = _write_sensor(tmp_path / "v.csv", 2012, "2025-10-13", 80, "SNPP")
    payload = run([modis], [viirs], tmp_path / "x.json")
    assert payload["headline"]["last_week"] == 41
    assert payload["data_through"] == "2025-10-12"
    # weeks after the last complete common week must be empty, not a false drop to zero
    assert payload["curve"][40]["current"] is not None
    assert payload["curve"][41]["current"] is None


def test_too_few_overlap_years_stops_with_a_clear_message(tmp_path):
    modis = _write_sensor(tmp_path / "m.csv", 2020, "2025-10-13", 20, "Terra")
    viirs = _write_sensor(tmp_path / "v.csv", 2024, "2025-10-13", 80, "SNPP")
    with pytest.raises(SystemExit, match="overlapping years"):
        run([modis], [viirs], tmp_path / "x.json")


def test_grid_file_is_written_and_matches_totals(tmp_path):
    modis = _write_sensor(tmp_path / "m.csv", 2000, "2025-10-13", 20, "Terra")
    viirs = _write_sensor(tmp_path / "v.csv", 2012, "2025-10-13", 80, "SNPP")
    grid_path = tmp_path / "g" / "grid.json"
    run([modis], [viirs], tmp_path / "x.json", grid_out=grid_path)
    grid = json.loads(grid_path.read_text())
    first_week = pd.Timestamp(grid["first_week"])
    mondays = pd.date_range(first_week, first_week + pd.Timedelta(weeks=grid["n_weeks"] - 1), freq="W-MON")
    assert sum(grid["modis"]["n"]) == 20 * len(mondays)
    assert grid["n_weeks"] > 1300
