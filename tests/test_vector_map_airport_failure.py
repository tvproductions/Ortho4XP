import os
import unittest
import warnings
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

import numpy
from shapely import geometry, ops

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Vector_Map as VMAP

WARNING = (
    "WARNING: Airport OSM query failed; continuing vector construction "
    "without airport data."
)


class AirportQueryFailureTests(unittest.TestCase):
    def test_failed_query_returns_typed_empty_airport_data_and_preserves_patches(self):
        tile = SimpleNamespace(
            lat=12,
            lon=-123,
            dem=object(),
            custom_dem="custom-dem.tif",
            fill_nodata=None,
        )
        vector_map = object()
        patch_area = geometry.box(0.1, 0.1, 0.2, 0.2)

        with (
            mock.patch.object(VMAP.OSM, "OSM_layer", return_value=object()),
            mock.patch.object(VMAP.OSM, "OSM_queries_to_OSM_layer", return_value=False),
            mock.patch.object(
                VMAP, "include_patches", return_value=(patch_area, ["custom"])
            ) as include_patches,
            mock.patch.object(VMAP.APT_DISC, "discover_airport_names") as discover,
            mock.patch.object(VMAP.UI, "vprint") as vprint,
            mock.patch.object(VMAP.UI, "log_event") as log_event,
        ):
            result = VMAP.include_airports(vector_map, tile)

        self.assertEqual(len(result), 3)
        airport_mask, airport_area, returned_patch_area = result

        self.assertEqual(airport_mask.shape, (1001, 1001))
        self.assertEqual(airport_mask.dtype, numpy.dtype(bool))
        self.assertFalse(airport_mask.any())
        self.assertIsInstance(airport_area, geometry.Polygon)
        self.assertTrue(airport_area.is_empty)
        self.assertTrue(returned_patch_area.equals(patch_area))
        include_patches.assert_called_once_with(vector_map, tile)
        discover.assert_not_called()
        vprint.assert_any_call(1, WARNING)
        log_event.assert_called_once_with(
            "Airport OSM query failed",
            level="WARNING",
            context={
                "lat": 12,
                "lon": -123,
                "action": "continue_without_airport_data",
            },
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            excluded = VMAP.VECT.improved_buffer(airport_area, 15, 0, 0)
        self.assertFalse(
            any(issubclass(item.category, DeprecationWarning) for item in caught)
        )
        road = geometry.LineString([(0, 0), (1, 1)])
        self.assertTrue(excluded.is_empty)
        self.assertTrue(road.difference(excluded).equals(road))

    def test_successful_query_reuses_dem_and_preserves_patch_order(self):
        tile = SimpleNamespace(
            lat=12,
            lon=-123,
            dem=object(),
            custom_dem="custom-dem.tif",
            fill_nodata=None,
        )
        vector_map = object()
        airport_layer = object()
        airport_mask = numpy.zeros((1001, 1001), dtype=bool)
        airport_mask[500, 500] = True
        airport_area = geometry.box(0.4, 0.4, 0.6, 0.6)
        patch_area = geometry.box(0.1, 0.1, 0.2, 0.2)
        patch_names = ["custom"]
        order = []

        with (
            mock.patch.object(VMAP.OSM, "OSM_layer", return_value=airport_layer),
            mock.patch.object(VMAP.OSM, "OSM_queries_to_OSM_layer", return_value=True),
            mock.patch.object(VMAP.APT_DISC, "discover_airport_names"),
            mock.patch.object(VMAP.APT_DISC, "attach_surfaces_to_airports"),
            mock.patch.object(VMAP.APT_DISC, "sort_and_reconstruct_runways"),
            mock.patch.object(VMAP.APT_DISC, "discard_unwanted_airports"),
            mock.patch.object(VMAP.APT_DISC, "list_airports_and_runways"),
            mock.patch.object(VMAP.APT_GEOM, "build_hangar_areas"),
            mock.patch.object(VMAP.APT_GEOM, "build_apron_areas"),
            mock.patch.object(VMAP.APT_GEOM, "build_taxiway_areas"),
            mock.patch.object(VMAP.APT_GEOM, "update_airport_boundaries"),
            mock.patch.object(
                VMAP.APT_GEOM,
                "smooth_raster_over_airports",
                side_effect=lambda *_args: order.append("smooth"),
            ),
            mock.patch.object(
                VMAP,
                "include_patches",
                side_effect=lambda *_args: (
                    order.append("patches") or (patch_area, patch_names)
                ),
            ) as include_patches,
            mock.patch.object(
                VMAP.APT_ENC,
                "encode_runways_taxiways_and_aprons",
                return_value=airport_area,
            ) as encode_airports,
            mock.patch.object(VMAP.APT_ENC, "encode_hangars"),
            mock.patch.object(VMAP.APT_ENC, "flatten_helipads") as flatten_helipads,
            mock.patch.object(
                VMAP.APT_GEOM, "build_airport_array", return_value=airport_mask
            ),
            mock.patch.object(VMAP.DEM, "DEM") as dem_constructor,
            mock.patch.object(VMAP.UI, "vprint"),
        ):
            result = VMAP.include_airports(vector_map, tile)

        self.assertEqual(len(result), 3)
        returned_mask, returned_airport_area, returned_patch_area = result
        self.assertIs(returned_mask, airport_mask)
        self.assertTrue(returned_airport_area.equals(airport_area))
        self.assertTrue(returned_patch_area.equals(patch_area))
        self.assertEqual(order, ["smooth", "patches"])
        dem_constructor.assert_not_called()
        include_patches.assert_called_once_with(vector_map, tile)
        encode_airports.assert_called_once_with(
            tile, airport_layer, mock.ANY, vector_map, patch_names
        )
        flatten_helipads.assert_called_once()
        expected_union = ops.unary_union([patch_area, airport_area])
        self.assertTrue(flatten_helipads.call_args.args[-1].equals(expected_union))


class VectorMapDemOrderingTests(unittest.TestCase):
    def test_builder_initializes_dem_before_airports_and_roads(self):
        order = []
        dem = object()
        vector_map = SimpleNamespace(dico_edges={})
        airport_mask = numpy.zeros((1001, 1001), dtype=bool)
        airport_area = geometry.Polygon()
        patch_area = geometry.box(0.1, 0.1, 0.2, 0.2)
        ctx = SimpleNamespace(is_working=False, red_flag=False)

        def construct_dem(*_args, **_kwargs):
            order.append("dem")
            return dem

        def include_airports(_vector_map, tile):
            self.assertIs(getattr(tile, "dem", None), dem)
            order.append("airports")
            return (airport_mask, airport_area, patch_area)

        def include_roads(_vector_map, tile, received_mask, treated_area):
            self.assertIs(tile.dem, dem)
            self.assertIs(received_mask, airport_mask)
            self.assertTrue(
                treated_area.equals(ops.unary_union([patch_area, airport_area]))
            )
            order.append("roads")
            ctx.red_flag = True

        with TemporaryDirectory() as tmpdir:
            tile = SimpleNamespace(
                lat=12,
                lon=-123,
                build_dir=os.path.join(tmpdir, "build"),
                custom_dem="custom-dem.tif",
                fill_nodata=None,
                road_level=1,
            )
            osm_dir = os.path.join(tmpdir, "osm")
            with (
                mock.patch.object(VMAP.VECT, "Vector_Map", return_value=vector_map),
                mock.patch.object(
                    VMAP.DEM, "DEM", side_effect=construct_dem
                ) as dem_constructor,
                mock.patch.object(
                    VMAP, "include_airports", side_effect=include_airports
                ),
                mock.patch.object(VMAP, "include_roads", side_effect=include_roads),
                mock.patch.object(VMAP.FNAMES, "osm_dir", return_value=osm_dir),
                mock.patch.object(
                    VMAP.FNAMES,
                    "input_node_file",
                    return_value=os.path.join(tmpdir, "tile.node"),
                ),
                mock.patch.object(
                    VMAP.FNAMES,
                    "input_poly_file",
                    return_value=os.path.join(tmpdir, "tile.poly"),
                ),
                mock.patch.object(VMAP.UI, "logprint"),
                mock.patch.object(VMAP.UI, "vprint"),
                mock.patch.object(VMAP.UI, "exit_message_and_bottom_line"),
            ):
                result = VMAP.build_poly_file(tile, ctx=ctx)

        self.assertEqual(result, 0)
        self.assertEqual(order, ["dem", "airports", "roads"])
        dem_constructor.assert_called_once_with(
            12,
            -123,
            "custom-dem.tif",
            "to zero",
            info_only=False,
        )


if __name__ == "__main__":
    unittest.main()
