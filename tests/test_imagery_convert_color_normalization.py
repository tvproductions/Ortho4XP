import os
import unittest

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

            IMG.convert_texture(tile, 32, 48, 16, "DIRECT")

        conversion.normalize.assert_not_called()
        self.assertEqual(conversion.command[-2], cached_path)

    def test_convert_texture_enabled_uses_and_removes_normalized_tmp_png(self):
        self._write_cached_jpeg("TMPPNG")
        tile = self._tile_for_conversion()
        normalized = Image.new("RGB", (16, 16), (120, 120, 120))

        with self._convert_texture_patches("TMPPNG") as conversion:
            IMG.normalize_texture_colors = True
            conversion.normalize.return_value = normalized

            IMG.convert_texture(tile, 32, 48, 16, "TMPPNG")

        expected_png = os.path.join(
            conversion.tmp_dir,
            FNAMES.dds_file_name_from_attributes(32, 48, 16, "TMPPNG").replace(
                "dds", "png"
            ),
        )
        self.assertEqual(conversion.command[-2], expected_png)
        self.assertFalse(os.path.exists(expected_png))
        conversion.normalize.assert_called_once()

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


if __name__ == "__main__":
    unittest.main()
