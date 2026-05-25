import os
from types import SimpleNamespace
import unittest
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from tests._imagery_color_normalization_helpers import (
    ConvertTexturePatchMixin,
)
import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG


class ConvertTextureColorNormalizationTests(ConvertTexturePatchMixin):
    def test_convert_texture_disabled_uses_cached_jpeg_directly(self):
        cached_path = self._write_cached_jpeg("DIRECT")
        tile = self._tile_for_conversion()

        with self._convert_texture_patches("DIRECT") as conversion:
            IMG.normalize_texture_colors = False

            result = IMG.convert_texture(tile, 32, 48, 16, "DIRECT")

        conversion.normalize.assert_not_called()
        self.assertEqual(conversion.encode_request.source_path, cached_path)
        self.assertTrue(result.ok)
        self.assertIs(result.encode_result, conversion.encode_texture.return_value)

    def test_convert_texture_enabled_uses_and_removes_normalized_tmp_png(self):
        self._write_cached_jpeg("TMPPNG")
        tile = self._tile_for_conversion()
        normalized = Image.new("RGB", (16, 16), (120, 120, 120))

        with self._convert_texture_patches("TMPPNG") as conversion:
            IMG.normalize_texture_colors = True
            conversion.normalize.return_value = normalized

            result = IMG.convert_texture(tile, 32, 48, 16, "TMPPNG")

        expected_png = os.path.join(
            conversion.tmp_dir,
            FNAMES.dds_file_name_from_attributes(32, 48, 16, "TMPPNG").replace(
                "dds", "png"
            ),
        )
        self.assertEqual(conversion.encode_request.source_path, expected_png)
        self.assertFalse(os.path.exists(expected_png))
        conversion.normalize.assert_called_once()
        self.assertTrue(result.ok)
        self.assertIs(result.encode_result, conversion.encode_texture.return_value)

    def test_convert_texture_normalizes_before_color_filter_preprocessing(self):
        self._write_cached_jpeg("FILTERED")
        tile = self._tile_for_conversion()
        call_order = []
        normalized = Image.new("RGB", (16, 16), (120, 120, 120))

        def normalize(image, *args):
            call_order.append("normalize")
            return normalized

        def color_transform(image, color_code):
            call_order.append("color_transform")
            self.assertEqual(color_code, "FILTER")
            self.assertEqual(image.getpixel((0, 0)), (120, 120, 120))
            return Image.new("RGB", image.size, (130, 130, 130))

        with self._convert_texture_patches(
            "FILTERED", color_filters="FILTER"
        ) as conversion:
            conversion.normalize.side_effect = normalize
            conversion.color_transform.side_effect = color_transform

            IMG.convert_texture(tile, 32, 48, 16, "FILTERED")

        self.assertEqual(call_order, ["normalize", "color_transform"])

    def test_convert_texture_normalizes_combined_provider_with_cache_dir(self):
        tile = self._tile_for_conversion()
        combined = Image.new("RGB", (16, 16), (90, 80, 70))
        normalized = Image.new("RGB", (16, 16), (120, 120, 120))

        with self._convert_texture_patches(
            "COMBINED",
            provider_in_cache=True,
            combined_provider=True,
        ) as conversion:
            conversion.combine_textures.return_value = combined
            conversion.normalize.return_value = normalized
            IMG.normalize_texture_colors = True

            IMG.convert_texture(tile, 32, 48, 16, "COMBINED")

        conversion.normalize.assert_called_once()
        context = conversion.normalize.call_args.args[1]
        self.assertEqual(context.file_dir, self.temp_dir.name)
        self.assertEqual(context.provider_code, "COMBINED")

    def test_convert_texture_logs_skip_for_combined_only_provider_without_cache_dir(
        self,
    ):
        tile = self._tile_for_conversion()
        combined = Image.new("RGB", (16, 16), (90, 80, 70))

        with self._convert_texture_patches(
            "COMBINEDONLY",
            provider_in_cache=False,
            combined_provider=True,
        ) as conversion:
            conversion.combine_textures.return_value = combined
            IMG.normalize_texture_colors = True

            IMG.convert_texture(tile, 32, 48, 16, "COMBINEDONLY")

        conversion.normalize.assert_not_called()
        conversion.vprint.assert_any_call(
            3,
            "Skipping texture color normalization for combined provider",
            "COMBINEDONLY",
            "because no cached provider directory is available for neighbor lookup.",
        )

    def test_convert_geotiff_final_conversion_failure_returns_failure_result(self):
        self._write_cached_jpeg("TIFFAIL")
        tile = self._tile_for_conversion()
        expected_name = FNAMES.geotiff_file_name_from_attributes(
            32, 48, 16, "TIFFAIL"
        )

        with (
            self._convert_texture_patches("TIFFAIL") as conversion,
            mock.patch.object(
                IMG.GEO,
                "gtile_to_wgs84",
                side_effect=[(1.0, 2.0), (0.99, 2.01)],
            ),
            mock.patch.object(IMG.GEO, "geo_to_webm", return_value=(0, 0)),
            mock.patch.object(IMG.UI, "lvprint"),
            mock.patch.object(IMG.time, "sleep"),
        ):
            conversion.run_external_command.return_value = SimpleNamespace(
                ok=False,
                error_summary="gdal translate failed",
            )

            result = IMG.convert_texture(tile, 32, 48, 16, "TIFFAIL", type="tif")

        self.assertFalse(result.ok)
        self.assertEqual(result.display_name, expected_name)
        self.assertEqual(result.provider_code, "TIFFAIL")
        self.assertIn("Could not convert texture", result.error_summary)
        self.assertEqual(conversion.run_external_command.call_count, 10)

    def test_convert_geotiff_geotag_failure_cleans_png_and_temp_tiff(self):
        self._write_cached_jpeg("GEOTAGFAIL")
        tile = self._tile_for_conversion()
        expected_name = FNAMES.geotiff_file_name_from_attributes(
            32, 48, 16, "GEOTAGFAIL"
        )

        with (
            self._convert_texture_patches(
                "GEOTAGFAIL", color_filters="FILTER"
            ) as conversion,
            mock.patch.object(
                IMG.GEO,
                "gtile_to_wgs84",
                side_effect=[(1.0, 2.0), (0.0, 3.0)],
            ),
            mock.patch.object(
                IMG.GEO,
                "geo_to_webm",
                side_effect=[(20, 0), (30, 10)],
            ),
            mock.patch.object(IMG.os, "remove") as remove,
        ):
            conversion.color_transform.side_effect = lambda image, _: image
            conversion.run_external_command.return_value = SimpleNamespace(
                ok=False,
                error_summary="gdal geotag failed",
            )

            result = IMG.convert_texture(tile, 32, 48, 16, "GEOTAGFAIL", type="tif")

        expected_png = os.path.join(
            conversion.tmp_dir,
            expected_name.replace("tif", "png"),
        )
        expected_tmp_tif = os.path.join(
            conversion.tmp_dir,
            expected_name.replace("4326", "3857"),
        )
        self.assertFalse(result.ok)
        remove.assert_any_call(expected_png)
        remove.assert_any_call(expected_tmp_tif)


if __name__ == "__main__":
    unittest.main()
