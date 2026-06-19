import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Utils as TCU
from O4_Cfg_Vars import (
    cfg_global_tile_vars,
    cfg_tile_vars,
    cfg_vars,
    list_global_tile_vars,
    list_tile_vars,
)
from O4_Config_Models import coerce_config_value

TEXTURE_ATTRS = (32, 48, 16, "PROV")
CONVERSION_INPUT = ("/input.tif", "out.tif", True, "out.png", "/work/tmp.tif")
COG_CREATION_OPTIONS = [
    "COMPRESS=JPEG",
    "TILED=YES",
    "BLOCKXSIZE=512",
    "BLOCKYSIZE=512",
]


def _convert_small_tile(tile):
    with _small_tile_patches() as gdal_mock:
        result = TCU.convert_geotiff_texture(tile, TEXTURE_ATTRS, CONVERSION_INPUT)
    return result, gdal_mock


def _convert_large_tile(tile):
    with _large_tile_patches() as gdal_mock:
        result = TCU.convert_geotiff_texture(tile, TEXTURE_ATTRS, CONVERSION_INPUT)
    return result, gdal_mock


@contextmanager
def _small_tile_patches():
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
        yield gdal_mock


@contextmanager
def _large_tile_patches():
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
        yield gdal_mock


class CogGeotiffConfigTests(unittest.TestCase):
    def test_cog_export_is_opt_in_tile_setting(self):
        definition = cfg_tile_vars["cog_export"]

        self.assertIs(definition["type"], bool)
        self.assertIs(definition["default"], False)
        self.assertIn("cog_export", cfg_vars)
        self.assertIn("cog_export", list_tile_vars)
        self.assertIn("global_cog_export", cfg_global_tile_vars)
        self.assertIn("global_cog_export", list_global_tile_vars)
        self.assertIs(coerce_config_value("cog_export", "True", cfg_vars), True)
        self.assertIs(
            coerce_config_value("global_cog_export", "False", cfg_vars),
            False,
        )


class CogGeotiffConversionTests(unittest.TestCase):
    def setUp(self):
        self.tile = SimpleNamespace(build_dir="/build", warp_resampling="lanczos")

    def test_small_tile_cog_export_uses_tiled_options_and_builds_overviews(self):
        self.tile.cog_export = True
        result, gdal_mock = _convert_small_tile(self.tile)

        output_path = os.path.join("/geotiffs", "out.tif")
        gdal_mock.Translate.assert_called_once_with(
            output_path,
            "/input.tif",
            format="GTiff",
            creationOptions=COG_CREATION_OPTIONS,
            outputBounds=[2.0, 0.99, 2.01, 1.0],
            outputSRS="EPSG:4326",
        )
        _assert_overviews_built(self, gdal_mock, output_path)
        self.assertTrue(result.ok)

    def test_large_tile_cog_export_uses_tiled_options_on_final_warp(self):
        self.tile.cog_export = True
        result, gdal_mock = _convert_large_tile(self.tile)

        output_path = os.path.join("/geotiffs", "out.tif")
        gdal_mock.Warp.assert_called_once_with(
            output_path,
            "/work/tmp.tif",
            format="GTiff",
            creationOptions=COG_CREATION_OPTIONS,
            srcSRS="EPSG:3857",
            dstSRS="EPSG:4326",
            width=4096,
            height=4096,
            resampleAlg="lanczos",
        )
        _assert_overviews_built(self, gdal_mock, output_path)
        self.assertTrue(result.ok)

    def test_cog_export_disabled_does_not_build_overviews(self):
        result, gdal_mock = _convert_small_tile(self.tile)

        gdal_mock.Open.assert_not_called()
        self.assertTrue(result.ok)


def _assert_overviews_built(testcase, gdal_mock, output_path):
    gdal_mock.Open.assert_called_once_with(output_path, gdal_mock.GA_Update)
    gdal_mock.Open.return_value.BuildOverviews.assert_called_once_with(
        "AVERAGE",
        [2, 4, 8, 16],
    )


if __name__ == "__main__":
    unittest.main()
