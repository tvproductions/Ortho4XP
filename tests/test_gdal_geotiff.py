import os
import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_File_Names as FNAMES
import O4_Texture_Conversion_Utils as TCU


class GdalGeotiffSmallTileTests(unittest.TestCase):
    def setUp(self):
        self.tile = SimpleNamespace(build_dir="/build")

    def test_small_tile_calls_gdal_translate_with_epsg4326(self):
        with (
            mock.patch.object(
                TCU.GEO,
                "gtile_to_wgs84",
                side_effect=[(1.0, 2.0), (0.99, 2.01)],
            ),
            mock.patch.object(TCU.GEO, "geo_to_webm", return_value=(0, 0)),
            mock.patch.object(TCU, "gdal") as gdal_mock,
            mock.patch.object(TCU.FNAMES, "Geotiff_dir", "/geotiffs"),
            mock.patch.object(TCU, "cleanup_conversion_temps"),
        ):
            result = TCU.convert_geotiff_texture(
                self.tile,
                (32, 48, 16, "PROV"),
                ("/input.tif", "out.tif", True, "out.png", "/work/tmp.tif"),
                ("gdal_translate", "gdalwarp"),
            )

        gdal_mock.Translate.assert_called_once_with(
            os.path.join("/geotiffs", "out.tif"),
            "/input.tif",
            format="GTiff",
            creationOptions=["COMPRESS=JPEG"],
            outputBounds=[2.0, 0.99, 2.01, 1.0],
            outputSRS="EPSG:4326",
        )
        gdal_mock.Warp.assert_not_called()
        self.assertTrue(result.ok)

    def test_small_tile_retries_10_times_on_failure(self):
        with (
            mock.patch.object(
                TCU.GEO,
                "gtile_to_wgs84",
                side_effect=[(1.0, 2.0), (0.99, 2.01)],
            ),
            mock.patch.object(TCU.GEO, "geo_to_webm", return_value=(0, 0)),
            mock.patch.object(TCU, "gdal") as gdal_mock,
            mock.patch.object(TCU.FNAMES, "Geotiff_dir", "/geotiffs"),
            mock.patch.object(TCU.time, "sleep"),
            mock.patch.object(TCU.UI, "lvprint"),
            mock.patch.object(TCU, "cleanup_conversion_temps"),
        ):
            gdal_mock.Translate.side_effect = RuntimeError("gdal error")
            result = TCU.convert_geotiff_texture(
                self.tile,
                (32, 48, 16, "PROV"),
                ("/input.tif", "out.tif", True, "out.png", "/work/tmp.tif"),
                ("gdal_translate", "gdalwarp"),
            )

        self.assertEqual(gdal_mock.Translate.call_count, 10)
        self.assertFalse(result.ok)
        self.assertIn("Could not convert texture", result.error_summary)


class GdalGeotiffLargeTileTests(unittest.TestCase):
    def setUp(self):
        self.tile = SimpleNamespace(build_dir="/build")

    def test_large_tile_calls_geotag_then_warp(self):
        with (
            mock.patch.object(
                TCU.GEO,
                "gtile_to_wgs84",
                side_effect=[(1.0, 2.0), (0.0, 3.0)],
            ),
            mock.patch.object(TCU.GEO, "geo_to_webm", side_effect=[(20, 0), (30, 10)]),
            mock.patch.object(TCU, "gdal") as gdal_mock,
            mock.patch.object(TCU.FNAMES, "Geotiff_dir", "/geotiffs"),
            mock.patch.object(TCU, "cleanup_conversion_temps"),
        ):
            result = TCU.convert_geotiff_texture(
                self.tile,
                (32, 48, 16, "PROV"),
                ("/input.tif", "out.tif", True, "out.png", "/work/tmp.tif"),
                ("gdal_translate", "gdalwarp"),
            )

        gdal_mock.Translate.assert_called_once_with(
            "/work/tmp.tif",
            "/input.tif",
            format="GTiff",
            creationOptions=["COMPRESS=JPEG"],
            outputBounds=[20, 0, 30, 10],
            outputSRS="EPSG:3857",
        )
        gdal_mock.Warp.assert_called_once_with(
            os.path.join("/geotiffs", "out.tif"),
            "/work/tmp.tif",
            format="GTiff",
            creationOptions=["COMPRESS=JPEG"],
            srcSRS="EPSG:3857",
            dstSRS="EPSG:4326",
            width=4096,
            height=4096,
            resampleAlg="bilinear",
        )
        self.assertTrue(result.ok)

    def test_large_tile_geotag_failure_cleans_up_and_returns_failure(self):
        with (
            mock.patch.object(
                TCU.GEO,
                "gtile_to_wgs84",
                side_effect=[(1.0, 2.0), (0.0, 3.0)],
            ),
            mock.patch.object(TCU.GEO, "geo_to_webm", side_effect=[(20, 0), (30, 10)]),
            mock.patch.object(TCU, "gdal") as gdal_mock,
            mock.patch.object(TCU.FNAMES, "Geotiff_dir", "/geotiffs"),
            mock.patch.object(TCU, "cleanup_conversion_temps") as cleanup,
            mock.patch.object(TCU.UI, "vprint"),
        ):
            gdal_mock.Translate.side_effect = RuntimeError("geotag error")
            result = TCU.convert_geotiff_texture(
                self.tile,
                (32, 48, 16, "PROV"),
                ("/input.tif", "out.tif", True, "out.png", "/work/tmp.tif"),
                ("gdal_translate", "gdalwarp"),
            )

        gdal_mock.Warp.assert_not_called()
        cleanup.assert_called_once_with(True, "out.png", "/work/tmp.tif")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_summary, "Could not geotag texture")

    def test_large_tile_warp_retries_10_times_on_failure(self):
        with (
            mock.patch.object(
                TCU.GEO,
                "gtile_to_wgs84",
                side_effect=[(1.0, 2.0), (0.0, 3.0)],
            ),
            mock.patch.object(TCU.GEO, "geo_to_webm", side_effect=[(20, 0), (30, 10)]),
            mock.patch.object(TCU, "gdal") as gdal_mock,
            mock.patch.object(TCU.FNAMES, "Geotiff_dir", "/geotiffs"),
            mock.patch.object(TCU.time, "sleep"),
            mock.patch.object(TCU.UI, "lvprint"),
            mock.patch.object(TCU, "cleanup_conversion_temps"),
        ):
            gdal_mock.Warp.side_effect = RuntimeError("warp error")
            result = TCU.convert_geotiff_texture(
                self.tile,
                (32, 48, 16, "PROV"),
                ("/input.tif", "out.tif", True, "out.png", "/work/tmp.tif"),
                ("gdal_translate", "gdalwarp"),
            )

        self.assertEqual(gdal_mock.Warp.call_count, 10)
        self.assertFalse(result.ok)
        self.assertIn("Could not convert texture", result.error_summary)

    def test_large_tile_warp_failure_cleans_tmp_tif(self):
        with (
            mock.patch.object(
                TCU.GEO,
                "gtile_to_wgs84",
                side_effect=[(1.0, 2.0), (0.0, 3.0)],
            ),
            mock.patch.object(TCU.GEO, "geo_to_webm", side_effect=[(20, 0), (30, 10)]),
            mock.patch.object(TCU, "gdal") as gdal_mock,
            mock.patch.object(TCU.FNAMES, "Geotiff_dir", "/geotiffs"),
            mock.patch.object(TCU.time, "sleep"),
            mock.patch.object(TCU.UI, "lvprint"),
            mock.patch.object(TCU, "cleanup_conversion_temps") as cleanup,
        ):
            gdal_mock.Warp.side_effect = RuntimeError("warp error")
            TCU.convert_geotiff_texture(
                self.tile,
                (32, 48, 16, "PROV"),
                ("/input.tif", "out.tif", True, "out.png", "/work/tmp.tif"),
                ("gdal_translate", "gdalwarp"),
            )

        cleanup.assert_called_once_with(True, "out.png", "/work/tmp.tif")


class GdalGeotiffGdalCommandsIgnoredTests(unittest.TestCase):
    def test_gdal_commands_parameter_is_ignored(self):
        tile = SimpleNamespace(build_dir="/build")
        with (
            mock.patch.object(
                TCU.GEO,
                "gtile_to_wgs84",
                side_effect=[(1.0, 2.0), (0.99, 2.01)],
            ),
            mock.patch.object(TCU.GEO, "geo_to_webm", return_value=(0, 0)),
            mock.patch.object(TCU, "gdal"),
            mock.patch.object(TCU.FNAMES, "Geotiff_dir", "/geotiffs"),
            mock.patch.object(TCU, "cleanup_conversion_temps"),
        ):
            result = TCU.convert_geotiff_texture(
                tile,
                (32, 48, 16, "PROV"),
                ("/input.tif", "out.tif", True, "out.png", "/work/tmp.tif"),
                (None, None),
            )

        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
