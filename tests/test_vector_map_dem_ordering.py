import unittest
from math import cos, pi
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy
from shapely import geometry, ops

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Vector_Map as VMAP
from tests import _vector_map_airport_helpers as HELP


class VectorMapDemOrderingTests(unittest.TestCase):
    def test_builder_initializes_dem_before_airports_and_roads(self):
        vector_map = SimpleNamespace(dico_edges={})
        fixture = SimpleNamespace(
            dem=object(),
            airport_mask=numpy.zeros((1001, 1001), dtype=bool),
            airport_area=geometry.Polygon(),
            patch_area=geometry.box(0.1, 0.1, 0.2, 0.2),
            ctx=SimpleNamespace(is_working=False, red_flag=False),
        )
        fixture.expected_union = ops.unary_union(
            [fixture.patch_area, fixture.airport_area]
        )
        probe = HELP.BuilderProbe(self, fixture)

        with TemporaryDirectory() as tmpdir:
            tile = HELP.builder_tile(tmpdir)
            with HELP.builder_mocks(tmpdir, vector_map, probe) as dem_constructor:
                result = VMAP.build_poly_file(tile, ctx=fixture.ctx)

        self.assertEqual(result, 0)
        self.assertEqual(probe.order, ["dem", "airports", "roads"])
        self.assertEqual(tile.iterate, 0)
        self.assertAlmostEqual(VMAP.VECT.scalx, cos((tile.lat + 0.5) * pi / 180))
        dem_constructor.assert_called_once_with(
            12,
            -123,
            "custom-dem.tif",
            "to zero",
            info_only=False,
        )


if __name__ == "__main__":
    unittest.main()
