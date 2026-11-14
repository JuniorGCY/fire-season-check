import numpy as np
import pandas as pd

from fogo.calibrate import Calibration
from fogo.grid import FIRST_WEEK, build_grid, grid_shape
from fogo.load import BBox, TOCANTINS

BOX = BBox(min_lat=-10.0, max_lat=-9.0, min_lon=-50.0, max_lon=-49.0)  # 4 x 4 cells of 0.25 degrees
CAL = Calibration("monthly", "count", 0.25, {6: 0.2})


def _detections(rows):
    return pd.DataFrame({
        "lat": [r[0] for r in rows], "lon": [r[1] for r in rows], "day": pd.to_datetime([r[2] for r in rows]),
    })


def _decode(part):
    weeks = np.cumsum(part["w"]).tolist()
    return {(w, c): n for w, c, n in zip(weeks, part["c"], part["n"])}


def test_grid_shape_of_tocantins_box():
    assert grid_shape(TOCANTINS) == (34, 21)
    assert grid_shape(BOX) == (4, 4)


def test_cells_weeks_and_counts_roundtrip():
    modis = _detections([
        (-9.9, -49.9, "2000-11-01"),   # SW cell (row 0, col 0), first week
        (-9.9, -49.9, "2000-11-03"),   # same cell and week
        (-9.1, -49.1, "2000-11-08"),   # NE cell (row 3, col 3), second week
    ])
    grid = build_grid(modis, _detections([]), BOX, FIRST_WEEK + pd.Timedelta(weeks=5), CAL)
    assert grid["rows"] == 4 and grid["cols"] == 4 and grid["n_weeks"] == 6
    assert _decode(grid["modis"]) == {(0, 0): 2, (1, 15): 1}


def test_points_on_the_far_edge_stay_in_the_last_cell():
    grid = build_grid(_detections([(-9.0, -49.0, "2000-11-01")]), _detections([]), BOX, FIRST_WEEK, CAL)
    assert _decode(grid["modis"]) == {(0, 15): 1}


def test_weeks_after_the_cutoff_are_dropped():
    late = _detections([(-9.5, -49.5, "2001-06-01")])
    grid = build_grid(late, _detections([]), BOX, FIRST_WEEK + pd.Timedelta(weeks=2), CAL)
    assert grid["modis"] == {"w": [], "c": [], "n": []}


def test_viirs_switch_and_ratios_are_exported():
    grid = build_grid(_detections([]), _detections([]), BOX, pd.Timestamp("2012-03-05"), CAL)
    switch = FIRST_WEEK + pd.Timedelta(weeks=grid["viirs_from_week"])
    assert switch == pd.Timestamp("2012-01-23")  # first Monday on or after 2012-01-20
    assert grid["ratio"]["monthly"] == {"6": 0.2} and grid["ratio"]["single"] == 0.25


def test_total_is_preserved():
    rows = [(-9.5, -49.5, "2005-07-04")] * 3 + [(-9.4, -49.6, "2005-07-12")] * 2
    grid = build_grid(_detections(rows), _detections([]), BOX, pd.Timestamp("2005-12-26"), CAL)
    assert sum(grid["modis"]["n"]) == 5
