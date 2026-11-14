from pathlib import Path

import pandas as pd
import pytest

from fogo.load import BBox, FireCsvError, TOCANTINS, read_firms, read_firms_csv
from fogo.weekly import weekly_series

BOX = BBox(min_lat=-10, max_lat=-5, min_lon=-50, max_lon=-45)
HEADER = "latitude,longitude,acq_date,acq_time,satellite,frp\n"
TYPED_HEADER = "latitude,longitude,acq_date,acq_time,satellite,frp,type\n"


def write_csv(path: Path, rows: list[str], header: str = HEADER) -> Path:
    path.write_text(header + "\n".join(rows) + ("\n" if rows else ""))
    return path


# ---------- reading ----------
def test_keeps_only_points_inside_region(tmp_path):
    csv_path = write_csv(tmp_path / "a.csv", [
        "-7,-48,2020-09-01,1200,Terra,10",
        "-20,-48,2020-09-01,1200,Terra,10",  # outside (lat)
        "-7,-30,2020-09-01,1200,Terra,10",   # outside (lon)
    ])
    assert len(read_firms_csv(csv_path, BOX)) == 1


def test_region_edges_are_inclusive(tmp_path):
    csv_path = write_csv(tmp_path / "e.csv", [
        "-10,-50,2020-01-01,0100,T,1", "-5,-45,2020-01-01,0100,T,1", "-4.99,-45,2020-01-01,0100,T,1",
    ])
    assert len(read_firms_csv(csv_path, BOX)) == 2


def test_type_column_keeps_only_vegetation_fires(tmp_path):
    csv_path = write_csv(tmp_path / "t.csv", [
        "-7,-48,2023-08-01,0100,SNPP,5,0",
        "-7,-48,2023-08-01,0200,SNPP,5,2",  # static land source
        "-7,-48,2023-08-01,0300,SNPP,5,3",  # offshore
    ], header=TYPED_HEADER)
    assert len(read_firms_csv(csv_path, BOX)) == 1


def test_files_without_type_column_are_not_filtered(tmp_path):
    csv_path = write_csv(tmp_path / "n.csv", ["-7,-48,2026-09-01,0100,Terra,5"])
    assert len(read_firms_csv(csv_path, BOX)) == 1


def test_leading_zero_times_survive(tmp_path):
    csv_path = write_csv(tmp_path / "z.csv", ["-7,-48,2026-09-01,0024,Terra,5"])
    assert read_firms_csv(csv_path, BOX).loc[0, "acq_time"] == "0024"


def test_missing_column_raises(tmp_path):
    bad = write_csv(tmp_path / "b.csv", ["-7,-48"], header="latitude,longitude\n")
    with pytest.raises(FireCsvError, match="missing columns"):
        read_firms_csv(bad, BOX)


def test_bad_date_raises(tmp_path):
    bad = write_csv(tmp_path / "c.csv", ["-7,-48,not-a-date,1200,Terra,5"])
    with pytest.raises(FireCsvError):
        read_firms_csv(bad, BOX)


def test_empty_csv_gives_empty_frame(tmp_path):
    assert read_firms_csv(write_csv(tmp_path / "e.csv", []), BOX).empty


def test_multiple_files_do_not_double_count(tmp_path):
    first = write_csv(tmp_path / "a.csv", ["-7,-48,2026-08-31,0100,Terra,5"])
    second = write_csv(tmp_path / "b.csv", [
        "-7,-48,2026-08-31,0100,Terra,5",  # same as first file: ignored
        "-7,-47,2026-08-31,0100,Terra,5",  # new
    ])
    assert len(read_firms([first, second], BOX)) == 2


def test_repeated_rows_inside_one_file_are_kept(tmp_path):
    csv_path = write_csv(tmp_path / "r.csv", ["-7,-48,2020-01-01,0100,T,1"] * 2)
    assert len(read_firms([csv_path], BOX)) == 2


def test_tocantins_box_contains_palmas():
    inside = TOCANTINS.mask(pd.Series([-10.18]), pd.Series([-48.33]))
    assert bool(inside.iloc[0])


# ---------- weekly ----------
def _detections(rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame({"day": pd.to_datetime([r[0] for r in rows]), "frp": [r[1] for r in rows]})


def test_weeks_start_on_monday_and_sum_frp():
    # 2020-09-02 is a Wednesday, 2020-09-06 a Sunday (same week), 2020-09-07 a Monday (next)
    weekly = weekly_series(_detections([("2020-09-02", 10), ("2020-09-06", 5), ("2020-09-07", 1)]))
    assert list(weekly.index) == [pd.Timestamp("2020-08-31"), pd.Timestamp("2020-09-07")]
    assert list(weekly["count"]) == [2, 1]
    assert list(weekly["frp"]) == [15, 1]


def test_empty_weeks_are_zero_filled():
    weekly = weekly_series(_detections([("2020-09-01", 1), ("2020-09-22", 1)]))
    assert list(weekly["count"]) == [1, 0, 0, 1]


def test_week_crossing_new_year_stays_together():
    weekly = weekly_series(_detections([("2020-12-30", 1), ("2021-01-02", 1)]))
    assert list(weekly["count"]) == [2]


def test_empty_input_gives_empty_series():
    assert weekly_series(_detections([])).empty
