import unittest
import sys
import types
from math import isclose, pi

import _path  # noqa: F401

try:
    import pyproj  # noqa: F401
except ModuleNotFoundError:
    pyproj = types.ModuleType("pyproj")

    class CRS:
        @staticmethod
        def from_epsg(epsg_code):
            return epsg_code

    class Transformer:
        @staticmethod
        def from_crs(source, target, always_xy=True):
            return Transformer()

        def transform(self, x_value, y_value):
            return x_value, y_value

    pyproj.CRS = CRS
    pyproj.Transformer = Transformer
    sys.modules["pyproj"] = pyproj

import O4_Geo_Utils as geo


class GeoUtilsTests(unittest.TestCase):
    def test_wgs84_to_gtile_and_back_at_origin(self):
        tile = geo.wgs84_to_gtile(0, 0, 1)

        self.assertEqual(tile, (1, 1))
        self.assertEqual(geo.gtile_to_wgs84(*tile, 1), (0, 0))

    def test_wgs84_pixel_round_trip_is_within_one_pixel(self):
        lat, lon, zoomlevel = 43.6426, -79.3871, 15

        pix_x, pix_y = geo.wgs84_to_pix(lat, lon, zoomlevel)
        round_trip_lat, round_trip_lon = geo.pix_to_wgs84(
            pix_x,
            pix_y,
            zoomlevel,
        )

        self.assertTrue(isclose(round_trip_lat, lat, abs_tol=0.0001))
        self.assertTrue(isclose(round_trip_lon, lon, abs_tol=0.0001))

    def test_gtile_to_quadkey_matches_bing_digit_order(self):
        self.assertEqual(geo.gtile_to_quadkey(3, 5, 3), "213")

    def test_webmercator_pixel_size_at_equator_zoom_zero(self):
        expected = 2 * pi * geo.earth_radius / 256

        self.assertTrue(isclose(geo.webmercator_pixel_size(0, 0), expected))


if __name__ == "__main__":
    unittest.main()
