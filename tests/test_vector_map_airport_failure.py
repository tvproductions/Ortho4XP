import unittest
import warnings
from types import SimpleNamespace
from unittest import mock

import numpy
from shapely import geometry, ops

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Vector_Map as VMAP
from tests import _vector_map_airport_helpers as HELP


class AirportQueryFailureTests(unittest.TestCase):
    def test_failed_query_returns_typed_empty_airport_data_and_preserves_patches(self):
        tile = HELP.airport_tile()
        vector_map = object()
        patch_area = geometry.box(0.1, 0.1, 0.2, 0.2)

        with HELP.failed_airport_mocks(patch_area) as calls:
            result = VMAP.include_airports(vector_map, tile)

        self.assertEqual(len(result), 3)
        airport_mask, airport_area, returned_patch_area = result
        self.assertEqual(airport_mask.shape, (1001, 1001))
        self.assertEqual(airport_mask.dtype, numpy.dtype(bool))
        self.assertFalse(airport_mask.any())
        self.assertIsInstance(airport_area, geometry.Polygon)
        self.assertTrue(airport_area.is_empty)
        self.assertTrue(returned_patch_area.equals(patch_area))
        calls.include_patches.assert_called_once_with(vector_map, tile)
        calls.discover.assert_not_called()
        calls.vprint.assert_any_call(1, HELP.WARNING)
        self.assertEqual(calls.order, ["warning", "patches"])
        calls.log_event.assert_called_once_with(
            "Airport OSM query failed",
            level="WARNING",
            context={
                "lat": 12,
                "lon": -123,
                "action": "continue_without_airport_data",
            },
        )
        self._assert_empty_area_is_safe_for_roads(airport_area)

    def test_successful_query_reuses_dem_and_preserves_patch_order(self):
        tile = HELP.airport_tile()
        vector_map = object()
        fixture = SimpleNamespace(
            airport_mask=numpy.eye(1001, dtype=bool),
            airport_area=geometry.box(0.4, 0.4, 0.6, 0.6),
            patch_area=geometry.box(0.1, 0.1, 0.2, 0.2),
        )

        with HELP.successful_airport_mocks(fixture) as calls:
            result = VMAP.include_airports(vector_map, tile)

        self.assertEqual(len(result), 3)
        returned_mask, returned_airport_area, returned_patch_area = result
        self.assertIs(returned_mask, fixture.airport_mask)
        self.assertTrue(returned_airport_area.equals(fixture.airport_area))
        self.assertTrue(returned_patch_area.equals(fixture.patch_area))
        self.assertEqual(calls.order, ["smooth", "patches"])
        calls.dem_constructor.assert_not_called()
        calls.include_patches.assert_called_once_with(vector_map, tile)
        calls.encode_airports.assert_called_once_with(
            tile,
            calls.airport_layer,
            mock.ANY,
            vector_map,
            calls.patch_names,
        )
        expected_union = ops.unary_union([fixture.patch_area, fixture.airport_area])
        self.assertTrue(
            calls.flatten_helipads.call_args.args[-1].equals(expected_union)
        )

    def _assert_empty_area_is_safe_for_roads(self, airport_area):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            excluded = VMAP.VECT.improved_buffer(airport_area, 15, 0, 0)
        self.assertFalse(
            any(issubclass(item.category, DeprecationWarning) for item in caught)
        )
        road = geometry.LineString([(0, 0), (1, 1)])
        self.assertTrue(excluded.is_empty)
        self.assertTrue(road.difference(excluded).equals(road))


if __name__ == "__main__":
    unittest.main()
