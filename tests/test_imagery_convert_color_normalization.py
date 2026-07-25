import os
import unittest
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Texture_Conversion_Utils as TCU
from O4_Texture_Source import TextureSource
from tests._imagery_color_normalization_helpers import (
    ConvertTexturePatchMixin,
)
from tests._imagery_geotiff_conversion_helpers import (
    convert_geotiff_with_failed_final_conversion,
    convert_geotiff_with_failed_geotag,
)


class ConvertTextureColorNormalizationTests(ConvertTexturePatchMixin):
    def test_convert_texture_uses_streaming_image_when_cached_jpeg_is_missing(self):
        tile = self._tile_for_conversion()
        source = TextureSource(
            tile,
            (32, 48, 16, "STREAM"),
            Image.new("RGB", (16, 16), (1, 2, 3)),
            cache_path=None,
        )

        with self._convert_texture_patches("STREAM") as conversion:
            result = IMG.convert_texture_source(source)

        self.assertTrue(result.ok)
        self.assertTrue(conversion.encode_request.source_path.endswith(".png"))
        self.assertFalse(os.path.exists(conversion.encode_request.source_path))

    def test_external_border_mask_is_not_conversion_cleanup(self):
        tile = self._tile_for_conversion()
        tile.imprint_masks_to_dds = False
        source = TextureSource(
            tile,
            (32, 48, 16, "STREAM"),
            Image.new("RGB", (16, 16), (1, 2, 3)),
        )
        with (
            self._convert_texture_patches("STREAM"),
            mock.patch.object(
                IMG, "convert_dds_texture", return_value=object()
            ) as conversion,
        ):
            IMG.convert_texture_source(source)
        cleanup_plan = conversion.call_args.args[3]
        self.assertEqual(cleanup_plan.success_paths, ())

    def test_streaming_imprinted_mask_exists_until_successful_encode(self):
        tile = self._tile_for_conversion()
        tile.imprint_masks_to_dds = True
        texture_attrs = (32, 48, 16, "STREAM")
        mask_path = self._write_dds_mask(tile, texture_attrs)
        source = TextureSource(
            tile,
            texture_attrs,
            Image.new("RGB", (16, 16), (1, 2, 3)),
        )

        with (
            self._convert_texture_patches("STREAM") as conversion,
            mock.patch.object(
                IMG.RP,
                "tile_resize_image",
                return_value=Image.new("L", (16, 16), 255),
            ),
        ):
            success = conversion.encode_texture.return_value

            def encode(request):
                self.assertTrue(os.path.exists(mask_path))
                with open(request.output_path, "wb") as output_file:
                    output_file.write(b"dds")
                return TCU.TEX.TextureEncodeResult(
                    request=request,
                    ok=True,
                    attempts=success.attempts,
                    backend_name=success.backend_name,
                    tool_name=success.tool_name,
                    returncode=success.returncode,
                    error_summary=success.error_summary,
                )

            conversion.encode_texture.side_effect = encode
            result = IMG.convert_texture_source(source)

        self.assertTrue(result.ok)
        self.assertFalse(os.path.exists(mask_path))

    def test_legacy_imprinted_mask_is_retained_after_encode_failure(self):
        self._write_cached_jpeg("MASKFAIL")
        tile = self._tile_for_conversion()
        tile.imprint_masks_to_dds = True
        texture_attrs = (32, 48, 16, "MASKFAIL")
        mask_path = self._write_dds_mask(tile, texture_attrs)

        with (
            self._convert_texture_patches("MASKFAIL") as conversion,
            mock.patch.object(
                IMG.RP,
                "tile_resize_image",
                return_value=Image.new("L", (16, 16), 255),
            ),
        ):
            failure = conversion.encode_texture.return_value

            def encode(request):
                self.assertTrue(os.path.exists(mask_path))
                return TCU.TEX.TextureEncodeResult(
                    request=request,
                    ok=False,
                    attempts=failure.attempts,
                    backend_name=failure.backend_name,
                    tool_name=failure.tool_name,
                    returncode=7,
                    error_summary="failed",
                )

            conversion.encode_texture.side_effect = encode
            result = IMG.convert_texture(tile, *texture_attrs)

        self.assertFalse(result.ok)
        self.assertTrue(os.path.exists(mask_path))

    def test_streaming_conversion_normalizes_before_color_filter(self):
        tile = self._tile_for_conversion()
        source = TextureSource(
            tile,
            (32, 48, 16, "STREAMFILTER"),
            Image.new("RGB", (16, 16), (10, 10, 10)),
            cache_path=os.path.join(self.temp_dir.name, "32_48_STREAMFILTER16.jpg"),
        )
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
            "STREAMFILTER",
            color_filters="FILTER",
        ) as conversion:
            conversion.normalize.side_effect = normalize
            conversion.color_transform.side_effect = color_transform
            IMG.normalize_texture_colors = True

            IMG.convert_texture_source(source)

        self.assertEqual(call_order, ["normalize", "color_transform"])

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
        expected_png = _dds_tmp_png_path("TMPPNG", self._conversion_tmp_dir())

        with self._convert_texture_patches("TMPPNG") as conversion:
            IMG.normalize_texture_colors = True
            conversion.normalize.return_value = normalized

            result = IMG.convert_texture(tile, 32, 48, 16, "TMPPNG")

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
        result, conversion, expected_name = (
            convert_geotiff_with_failed_final_conversion(self)
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.display_name, expected_name)
        self.assertEqual(result.provider_code, "TIFFAIL")
        self.assertIn("Could not convert texture", result.error_summary)
        self.assertEqual(conversion.run_external_command.call_count, 10)

    def test_convert_geotiff_geotag_failure_cleans_png_and_temp_tiff(self):
        result, remove, tmp_dir, expected_name = convert_geotiff_with_failed_geotag(
            self
        )

        self.assertFalse(result.ok)
        remove.assert_any_call(
            os.path.join(tmp_dir, expected_name.replace("tif", "png"))
        )
        remove.assert_any_call(
            os.path.join(tmp_dir, expected_name.replace("4326", "3857"))
        )

    def _write_dds_mask(self, tile, texture_attrs):
        mask_path = os.path.join(
            tile.build_dir,
            "textures",
            FNAMES.mask_file(*texture_attrs),
        )
        Image.new("L", (16, 16), 255).save(mask_path)
        return mask_path


def _dds_tmp_png_path(provider_code, tmp_dir):
    return os.path.join(
        tmp_dir,
        FNAMES.dds_file_name_from_attributes(32, 48, 16, provider_code).replace(
            "dds", "png"
        ),
    )


if __name__ == "__main__":
    unittest.main()
