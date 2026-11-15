import json
import sys

import pandas as pd
import pytest

from fogo import cli
from fogo.cli import run
from fogo.load import BBox, TOCANTINS

HEADER = "latitude,longitude,acq_date,acq_time,satellite,frp,type\n"
ELSEWHERE = BBox(min_lat=10.0, max_lat=12.0, min_lon=20.0, max_lon=22.0)


def _write(path, first_year, rows_per_week, name, spots):
    """Every Monday, `rows_per_week` hotspots at each (lat, lon) of `spots`."""
    mondays = pd.date_range(f"{first_year}-01-02", "2025-10-13", freq="W-MON")
    lines = [f"{lat},{lon},{d:%Y-%m-%d},0100,{name},10,0"
             for d in mondays for lat, lon in spots for _ in range(rows_per_week)]
    path.write_text(HEADER + "\n".join(lines) + "\n")
    return path


def _world(tmp_path):
    """MODIS 20 and VIIRS 80 per week inside Tocantins, plus half that again far away in ELSEWHERE."""
    spots = [(-8.0, -48.0), (11.0, 21.0)]
    return (_write(tmp_path / "m.csv", 2000, 20, "Terra", spots),
            _write(tmp_path / "v.csv", 2012, 80, "SNPP", spots))


def test_default_region_is_tocantins_and_ignores_hotspots_elsewhere(tmp_path):
    modis, viirs = _world(tmp_path)
    run([modis], [viirs], tmp_path / "x.json", grid_out=tmp_path / "g.json")
    grid = json.loads((tmp_path / "g.json").read_text())
    assert grid["origin"] == {"lat": TOCANTINS.min_lat, "lon": TOCANTINS.min_lon}
    mondays = pd.date_range(grid["first_week"], periods=grid["n_weeks"], freq="W-MON")
    assert sum(grid["modis"]["n"]) == 20 * len(mondays)  # only the (-8, -48) spot


def test_another_box_reads_only_its_own_hotspots(tmp_path):
    modis, viirs = _world(tmp_path)
    payload = run([modis], [viirs], tmp_path / "x.json", region="Elsewhere", box=ELSEWHERE,
                  grid_out=tmp_path / "g.json", points_out=tmp_path / "pts")
    grid = json.loads((tmp_path / "g.json").read_text())
    index = json.loads((tmp_path / "pts" / "index.json").read_text())
    assert payload["region"] == "Elsewhere" and "Elsewhere" in payload["headline"]["text"]
    assert grid["origin"] == {"lat": 10.0, "lon": 20.0} and (grid["rows"], grid["cols"]) == (8, 8)
    assert index["origin"] == {"lat": 10.0, "lon": 20.0}
    assert payload["headline"]["status"] == "within"        # same constant world, same answer
    assert sum(y["n"] for y in index["years"]) > 0


def test_box_with_no_hotspots_stops_with_a_clear_message(tmp_path):
    modis, viirs = _world(tmp_path)
    empty = BBox(min_lat=40.0, max_lat=41.0, min_lon=40.0, max_lon=41.0)
    with pytest.raises(SystemExit, match="no hotspots"):
        run([modis], [viirs], tmp_path / "x.json", box=empty)


@pytest.mark.parametrize("values, message", [
    ((5.0, -5.0, 0.0, 1.0), "south"),
    ((0.0, 1.0, 5.0, -5.0), "west"),
    ((-91.0, 0.0, 0.0, 1.0), "latitude"),
    ((0.0, 91.0, 0.0, 1.0), "latitude"),
    ((0.0, 1.0, -181.0, 0.0), "longitude"),
    ((0.0, 1.0, 0.0, 181.0), "longitude"),
])
def test_an_impossible_box_is_rejected(values, message):
    with pytest.raises(ValueError, match=message):
        BBox(*values)


def test_command_line_accepts_a_region_name_and_a_box(tmp_path, monkeypatch, capsys):
    modis, viirs = _world(tmp_path)
    out = tmp_path / "e.json"
    monkeypatch.setattr(sys, "argv", [
        "fogo", "build", "--modis", str(modis), "--viirs", str(viirs), "--out", str(out),
        "--region", "Elsewhere", "--bbox", "10", "12", "20", "22"])
    cli.main()
    assert json.loads(out.read_text())["region"] == "Elsewhere"
    assert "Elsewhere" in capsys.readouterr().out


def test_command_line_rejects_a_bad_box_without_a_traceback(tmp_path, monkeypatch):
    modis, viirs = _world(tmp_path)
    monkeypatch.setattr(sys, "argv", [
        "fogo", "build", "--modis", str(modis), "--viirs", str(viirs), "--out", str(tmp_path / "e.json"),
        "--bbox", "12", "10", "20", "22"])
    with pytest.raises(SystemExit, match="south"):
        cli.main()
