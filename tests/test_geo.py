import json

import pytest

from fogo.geo import build_geo, polygon_centroid

SQUARE = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]


def _feature(code, ring):
    return {"type": "Feature", "properties": {"codarea": code},
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def _collection(*features):
    return {"type": "FeatureCollection", "features": list(features)}


def test_centroid_of_a_square_is_its_middle_whatever_the_direction():
    assert polygon_centroid(SQUARE) == pytest.approx((2, 2))
    assert polygon_centroid(SQUARE[::-1]) == pytest.approx((2, 2))


def test_centroid_of_an_l_shape_is_pulled_towards_the_heavy_arm():
    l_shape = [[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2], [0, 0]]
    x, y = polygon_centroid(l_shape)
    assert (x, y) == pytest.approx((5 / 6, 5 / 6))


def test_outline_is_rounded_and_keeps_every_ring():
    state = _collection({"type": "Feature", "properties": {}, "geometry": {
        "type": "MultiPolygon", "coordinates": [[SQUARE], [[[10.123456, 10.1], [11, 10.1], [11, 11], [10.123456, 10.1]]]]}})
    geo = build_geo(state, _collection(), [], [])
    assert len(geo["outline"]) == 2
    assert geo["outline"][1][0] == [10.123, 10.1]


def test_places_are_named_after_the_registry_and_placed_at_the_centroid():
    towns = _collection(_feature("1", SQUARE), _feature("2", [[10, 10], [12, 10], [12, 12], [10, 12], [10, 10]]))
    registry = [{"id": 1, "nome": "Alpha"}, {"id": 2, "nome": "Beta"}]
    geo = build_geo(_collection(_feature("0", SQUARE)), towns, registry, ["Beta"])
    assert geo["places"] == [{"name": "Beta", "lat": 11.0, "lon": 11.0}]


def test_a_misspelled_place_is_an_error_not_a_silent_gap():
    registry = [{"id": 1, "nome": "Alpha"}]
    with pytest.raises(ValueError, match="Alfa"):
        build_geo(_collection(_feature("0", SQUARE)), _collection(_feature("1", SQUARE)), registry, ["Alfa"])


def test_a_place_without_a_shape_is_an_error():
    registry = [{"id": 1, "nome": "Alpha"}]
    with pytest.raises(ValueError, match="Alpha"):
        build_geo(_collection(_feature("0", SQUARE)), _collection(), registry, ["Alpha"])


def test_result_is_plain_json_and_small():
    geo = build_geo(_collection(_feature("0", SQUARE)), _collection(_feature("1", SQUARE)),
                    [{"id": 1, "nome": "Alpha"}], ["Alpha"])
    assert json.loads(json.dumps(geo)) == geo
    assert geo["source"].startswith("IBGE")
