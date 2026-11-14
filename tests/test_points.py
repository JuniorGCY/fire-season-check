import json

import numpy as np
import pandas as pd
import pytest

from fogo.cli import run
from fogo.load import BBox, TOCANTINS as BOX_TOCANTINS
from fogo.points import MODIS, VIIRS, build_points, decode_year, encode_year

BOX = BBox(min_lat=-10.0, max_lat=-9.0, min_lon=-50.0, max_lon=-49.0)


def _detections(rows):
    """rows: (lat, lon, day, acq_time, frp)"""
    return pd.DataFrame({
        "lat": [r[0] for r in rows], "lon": [r[1] for r in rows],
        "day": pd.to_datetime([r[2] for r in rows]),
        "acq_time": [r[3] for r in rows], "frp": [r[4] for r in rows],
    })


def test_roundtrip_keeps_every_field_within_the_stated_precision():
    frame = _detections([(-9.12345, -49.54321, "2023-08-05", "0130", 12.34),
                         (-9.9, -49.1, "2023-09-17", "1325", 250.0)])
    out = decode_year(encode_year(frame, MODIS, BOX), BOX)
    assert len(out) == 2
    assert out["lat"].tolist() == pytest.approx([-9.12345, -9.9], abs=0.0006)
    assert out["lon"].tolist() == pytest.approx([-49.54321, -49.1], abs=0.0006)
    assert out["day"].dt.strftime("%Y-%m-%d").tolist() == ["2023-08-05", "2023-09-17"]
    assert out["time"].tolist() == [130, 1325]
    assert out["frp"].tolist() == pytest.approx([12.3, 250.0], abs=0.05)
    assert out["sensor"].tolist() == [MODIS, MODIS]


def test_missing_time_is_zero_and_missing_frp_is_zero():
    frame = pd.DataFrame({"lat": [-9.5], "lon": [-49.5], "day": pd.to_datetime(["2020-01-01"])})
    out = decode_year(encode_year(frame, VIIRS, BOX), BOX)
    assert out["time"].tolist() == [0] and out["frp"].tolist() == [0.0]
    assert out["sensor"].tolist() == [VIIRS]


def test_empty_year_encodes_to_a_valid_empty_file():
    assert len(decode_year(encode_year(_detections([]), MODIS, BOX), BOX)) == 0


def test_a_file_that_is_not_ours_is_rejected():
    with pytest.raises(ValueError, match="not a points file"):
        decode_year(b"nope" + bytes(20), BOX)


def test_a_point_outside_the_box_is_an_error_not_silent_garbage():
    far = _detections([(-20.0, -49.5, "2020-01-01", "0100", 1.0)])
    with pytest.raises(ValueError, match="outside"):
        encode_year(far, MODIS, BOX)


def test_huge_fire_power_is_capped_not_wrapped():
    huge = _detections([(-9.5, -49.5, "2020-01-01", "0100", 99999.0)])
    out = decode_year(encode_year(huge, MODIS, BOX), BOX)
    assert out["frp"].tolist() == [pytest.approx(6553.5)]


def test_build_splits_by_year_and_preserves_the_total(tmp_path):
    modis = _detections([(-9.5, -49.5, "2019-12-31", "0100", 5.0),
                         (-9.5, -49.5, "2020-01-01", "0100", 5.0),
                         (-9.5, -49.5, "2020-07-01", "0100", 5.0)])
    viirs = _detections([(-9.4, -49.4, "2020-07-02", "0200", 3.0)])
    index = build_points(modis, viirs, BOX, tmp_path / "pts", through=pd.Timestamp("2020-12-31"))
    years = {y["year"]: y for y in index["years"]}
    assert sorted(years) == [2019, 2020]
    assert years[2019]["n"] == 1 and years[2020]["n"] == 3
    assert sum(y["n"] for y in index["years"]) == 4
    for y in index["years"]:
        assert (tmp_path / "pts" / y["file"]).stat().st_size == y["bytes"]
    both = decode_year((tmp_path / "pts" / years[2020]["file"]).read_bytes(), BOX)
    assert sorted(both["sensor"].tolist()) == [MODIS, MODIS, VIIRS]
    assert both["day"].is_monotonic_increasing


def test_days_after_the_cutoff_are_not_exported(tmp_path):
    modis = _detections([(-9.5, -49.5, "2020-07-01", "0100", 5.0),
                         (-9.5, -49.5, "2020-07-20", "0100", 5.0)])
    index = build_points(modis, _detections([]), BOX, tmp_path, through=pd.Timestamp("2020-07-05"))
    assert sum(y["n"] for y in index["years"]) == 1


def test_index_describes_how_to_read_the_files(tmp_path):
    index = build_points(_detections([]), _detections([]), BOX, tmp_path, through=pd.Timestamp("2020-01-01"))
    assert index["origin"] == {"lat": -10.0, "lon": -50.0}
    assert index["scale"] == 1000 and index["frp_scale"] == 10
    assert index["epoch"] == "2000-01-01" and index["sensors"] == {"modis": 0, "viirs": 1}
    assert json.loads((tmp_path / "index.json").read_text()) == index


def test_cli_writes_points_that_match_the_grid_totals(tmp_path):
    header = "latitude,longitude,acq_date,acq_time,satellite,frp,type\n"

    def sensor(path, first_year, rows_per_week, name):
        mondays = pd.date_range(f"{first_year}-01-02", "2025-10-13", freq="W-MON")
        lines = [f"-8,-48,{d:%Y-%m-%d},0100,{name},10,0" for d in mondays for _ in range(rows_per_week)]
        path.write_text(header + "\n".join(lines) + "\n")
        return path

    modis, viirs = sensor(tmp_path / "m.csv", 2000, 20, "Terra"), sensor(tmp_path / "v.csv", 2012, 80, "SNPP")
    points_dir = tmp_path / "pts"
    run([modis], [viirs], tmp_path / "x.json", grid_out=tmp_path / "g.json", points_out=points_dir)
    grid = json.loads((tmp_path / "g.json").read_text())
    index = json.loads((points_dir / "index.json").read_text())
    frames = [decode_year((points_dir / y["file"]).read_bytes(), BOX_TOCANTINS) for y in index["years"]]
    points = pd.concat(frames)
    assert len(points) == sum(y["n"] for y in index["years"])
    # The grid starts at the first week of MODIS C6.1 (2000-10-30); the synthetic files start earlier.
    after_start = points[points["day"] >= grid["first_week"]]
    assert len(after_start) == sum(grid["modis"]["n"]) + sum(grid["viirs"]["n"])
    assert np.isclose(points["lat"].mean(), -8, atol=0.001)
