"""Prepare required and optional inputs for vector-map construction."""

from math import cos, pi

import numpy
from shapely import geometry

import O4_DEM_Utils as DEM
import O4_UI_Utils as UI
import O4_Vector_Utils as VECT

AIRPORT_QUERY_WARNING = (
    "WARNING: Airport OSM query failed; continuing vector construction "
    "without airport data."
)


def prepare(tile):
    tile.iterate = 0
    VECT.scalx = cos((tile.lat + 0.5) * pi / 180)
    tile.dem = load_dem(tile)
    return VECT.Vector_Map()


def load_dem(tile):
    UI.vprint(1, "   Loading elevation data.")
    return DEM.DEM(
        tile.lat,
        tile.lon,
        tile.custom_dem,
        tile.fill_nodata or "to zero",
        info_only=False,
    )


def report_airport_query_failure(tile):
    UI.vprint(1, AIRPORT_QUERY_WARNING)
    UI.log_event(
        "Airport OSM query failed",
        level="WARNING",
        context={
            "lat": tile.lat,
            "lon": tile.lon,
            "action": "continue_without_airport_data",
        },
    )
    return (numpy.zeros((1001, 1001), dtype=bool), geometry.Polygon())
