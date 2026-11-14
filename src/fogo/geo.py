"""State outline and place names for the map, from IBGE open data.

The page draws no basemap tiles (no external services), so the pipeline writes the state outline
and a few city labels into a tiny JSON. Inputs are IBGE API answers saved by hand (see README):
  - state mesh   https://servicodados.ibge.gov.br/api/v3/malhas/estados/17
  - town shapes  the same URL with intrarregiao=municipio
  - town names   https://servicodados.ibge.gov.br/api/v1/localidades/estados/17/municipios
A label sits at the centroid of its municipality, which is close to the town but not exact.
"""

from __future__ import annotations

# Municipalities labelled on the map: the capital and the towns users are most likely to look for.
# Chosen by hand for coverage across the state, not by a ranking.
DEFAULT_PLACES = [
    "Palmas", "Araguaína", "Gurupi", "Porto Nacional", "Paraíso do Tocantins", "Colinas do Tocantins",
    "Guaraí", "Tocantinópolis", "Dianópolis", "Araguatins", "Miracema do Tocantins",
    "Formoso do Araguaia", "Pedro Afonso", "Arraias", "Augustinópolis",
]
PRECISION = 3  # decimal degrees, about 110 m: invisible on a map 440 px wide
SOURCE = "IBGE, malhas territoriais (state and municipal meshes), minimum quality"


def polygon_centroid(ring: list[list[float]]) -> tuple[float, float]:
    """Area-weighted centroid of a closed ring, in either winding direction."""
    area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if area == 0:
        raise ValueError("ring has no area")
    return cx / (3 * area), cy / (3 * area)


def _rings(geometry: dict) -> list[list[list[float]]]:
    """Outer rings only, for Polygon and MultiPolygon."""
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    if geometry["type"] == "MultiPolygon":
        return [polygon[0] for polygon in geometry["coordinates"]]
    raise ValueError(f"unsupported geometry {geometry['type']}")


def _round(ring: list[list[float]]) -> list[list[float]]:
    return [[round(x, PRECISION), round(y, PRECISION)] for x, y in ring]


def _largest(rings: list[list[list[float]]]) -> list[list[float]]:
    return max(rings, key=lambda r: abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(r, r[1:]))))


def build_geo(state: dict, towns: dict, registry: list[dict], place_names: list[str]) -> dict:
    """`state` and `towns` are GeoJSON collections, `registry` the IBGE list of id and name."""
    outline = [_round(ring) for feature in state["features"] for ring in _rings(feature["geometry"])]
    shapes = {str(f["properties"]["codarea"]): f["geometry"] for f in towns["features"]}
    ids = {entry["nome"]: str(entry["id"]) for entry in registry}
    places = []
    for name in place_names:
        if name not in ids:
            raise ValueError(f"place not in the IBGE registry: {name}")
        if ids[name] not in shapes:
            raise ValueError(f"no shape for {name}")
        x, y = polygon_centroid(_largest(_rings(shapes[ids[name]])))
        places.append({"name": name, "lat": round(y, PRECISION), "lon": round(x, PRECISION)})
    return {"source": SOURCE, "outline": outline, "places": places}
