import inspect
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG


class ImageryColorNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_enabled = IMG.normalize_texture_colors
        self.addCleanup(self._restore_state)

    def _restore_state(self):
        IMG.normalize_texture_colors = self.original_enabled

    def test_normalize_texture_image_is_bypassed_when_disabled(self):
        IMG.normalize_texture_colors = False
        image = Image.new("RGB", (16, 16), (90, 80, 70))

        with mock.patch.object(IMG, "normalize_image_with_neighbors") as normalize:
            result = IMG.normalize_texture_image_if_enabled(
                image,
                self.temp_dir.name,
                32,
                48,
                16,
                "BI",
            )

        self.assertEqual(result.tobytes(), image.tobytes())
        normalize.assert_not_called()

    def test_normalize_texture_image_loads_existing_cardinal_neighbors(self):
        IMG.normalize_texture_colors = True
        image = Image.new("RGB", (16, 16), (90, 80, 70))
        attrs = (32, 48, 16, "BI")
        neighbor_attrs = {
            "north": (32, 32, 16, "BI"),
            "south": (32, 64, 16, "BI"),
            "west": (16, 48, 16, "BI"),
            "east": (48, 48, 16, "BI"),
        }
        for edge, edge_attrs in neighbor_attrs.items():
            path = os.path.join(
                self.temp_dir.name,
                FNAMES.jpeg_file_name_from_attributes(*edge_attrs),
            )
            Image.new("RGB", (16, 16), self._color_for_edge(edge)).save(path)

        def fake_normalize(target, neighbors):
            self.assertEqual(target.size, (16, 16))
            self.assertEqual(set(neighbors), {"north", "south", "west", "east"})
            return Image.new("RGB", target.size, (120, 120, 120))

        with mock.patch.object(
            IMG, "normalize_image_with_neighbors", side_effect=fake_normalize
        ) as normalize:
            result = IMG.normalize_texture_image_if_enabled(
                image,
                self.temp_dir.name,
                *attrs,
            )

        normalize.assert_called_once()
        self.assertEqual(result.getpixel((0, 0)), (120, 120, 120))

    def test_normalize_texture_image_skips_missing_and_invalid_neighbors(self):
        IMG.normalize_texture_colors = True
        image = Image.new("RGB", (16, 16), (90, 80, 70))
        bad_path = os.path.join(
            self.temp_dir.name,
            FNAMES.jpeg_file_name_from_attributes(32, 32, 16, "BI"),
        )
        with open(bad_path, "w", encoding="utf-8") as handle:
            handle.write("not an image")

        with mock.patch.object(
            IMG, "normalize_image_with_neighbors", return_value=image
        ) as normalize:
            result = IMG.normalize_texture_image_if_enabled(
                image,
                self.temp_dir.name,
                32,
                48,
                16,
                "BI",
            )

        self.assertEqual(result.tobytes(), image.tobytes())
        normalize.assert_not_called()

    def test_normalize_texture_image_skips_wrong_sized_neighbors(self):
        IMG.normalize_texture_colors = True
        image = Image.new("RGB", (16, 16), (90, 80, 70))
        wrong_size_path = os.path.join(
            self.temp_dir.name,
            FNAMES.jpeg_file_name_from_attributes(32, 32, 16, "BI"),
        )
        Image.new("RGB", (8, 16), (100, 110, 120)).save(wrong_size_path)

        with mock.patch.object(
            IMG, "normalize_image_with_neighbors", return_value=image
        ) as normalize:
            result = IMG.normalize_texture_image_if_enabled(
                image,
                self.temp_dir.name,
                32,
                48,
                16,
                "BI",
            )

        self.assertEqual(result.tobytes(), image.tobytes())
        normalize.assert_not_called()

    def test_loaded_neighbor_images_remain_usable_after_file_close(self):
        neighbor_path = os.path.join(
            self.temp_dir.name,
            FNAMES.jpeg_file_name_from_attributes(32, 32, 16, "BI"),
        )
        Image.new("RGB", (16, 16), (100, 110, 120)).save(neighbor_path)

        neighbors = IMG._load_neighbor_texture_images(
            self.temp_dir.name,
            32,
            48,
            16,
            "BI",
            (16, 16),
        )

        self.assertEqual(set(neighbors), {"north"})
        self.assertEqual(neighbors["north"].getpixel((0, 0)), (100, 110, 120))

    def test_download_jpeg_ortho_normalizes_only_successful_final_image_before_save(self):
        source = inspect.getsource(IMG.download_jpeg_ortho)

        self.assertIn("if success:", source)
        self.assertIn("normalize_texture_image_if_enabled(", source)
        self.assertLess(
            source.index("normalize_texture_image_if_enabled("),
            source.index(".save(os.path.join(file_dir, file_name))"),
        )

    def test_download_jpeg_ortho_normalizes_successful_downloads_only(self):
        provider_code = "TEST"
        provider = {"code": provider_code, "request_type": "test"}

        for success in (True, False):
            with self.subTest(success=success):
                image = Image.new("RGB", (16, 16), (90, 80, 70))
                normalized = Image.new("RGB", (16, 16), (120, 120, 120))
                file_name = f"download-success-{success}.jpg"

                with (
                    mock.patch.dict(IMG.providers_dict, {provider_code: provider}),
                    mock.patch.object(IMG.UI, "red_flag", False),
                    mock.patch.object(
                        IMG,
                        "build_texture_from_bbox_and_size",
                        return_value=(success, image),
                    ),
                    mock.patch.object(
                        IMG,
                        "normalize_texture_image_if_enabled",
                        return_value=normalized,
                    ) as normalize,
                    mock.patch.object(IMG.UI, "lvprint"),
                    mock.patch.object(IMG, "record_incomplete_texture"),
                ):
                    IMG.download_jpeg_ortho(
                        self.temp_dir.name,
                        file_name,
                        32,
                        48,
                        16,
                        provider_code,
                    )

                if success:
                    normalize.assert_called_once()
                else:
                    normalize.assert_not_called()

    def test_convert_texture_can_normalize_existing_cached_jpeg_before_conversion(self):
        source = inspect.getsource(IMG.convert_texture)

        self.assertIn("normalize_texture_image_if_enabled(", source)
        self.assertIn(
            'file_to_convert = os.path.join(FNAMES.resource_path("tmp"), png_file_name)',
            source,
        )

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
        self.assertEqual(conversion.normalize.call_args.args[1], self.temp_dir.name)

    def test_convert_texture_logs_skip_for_combined_only_provider_without_cache_dir(self):
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

    def _color_for_edge(self, edge):
        return {
            "north": (100, 110, 120),
            "south": (120, 110, 100),
            "west": (80, 100, 120),
            "east": (120, 100, 80),
        }[edge]

    def _tile_for_conversion(self):
        build_dir = os.path.join(self.temp_dir.name, "build")
        os.makedirs(os.path.join(build_dir, "textures"), exist_ok=True)
        return SimpleNamespace(
            build_dir=build_dir,
            imprint_masks_to_dds=False,
            lat=1,
            lon=2,
        )

    def _write_cached_jpeg(self, provider_code):
        path = os.path.join(
            self.temp_dir.name,
            FNAMES.jpeg_file_name_from_attributes(32, 48, 16, provider_code),
        )
        Image.new("RGB", (16, 16), (90, 80, 70)).save(path)
        return path

    def _convert_texture_patches(
        self,
        provider_code,
        *,
        color_filters="none",
        provider_in_cache=True,
        combined_provider=False,
    ):
        tmp_dir = os.path.join(self.temp_dir.name, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        provider = {"code": provider_code, "color_filters": color_filters}
        providers = {provider_code: provider} if provider_in_cache else {}
        combined_providers = (
            {provider_code: [{"code": provider_code}]} if combined_provider else {}
        )
        result = SimpleNamespace(ok=True)
        context = mock.patch.multiple(
            IMG,
            is_macos=False,
            dds_convert_cmd="dds-tool",
            run_external_command=mock.DEFAULT,
            normalize_texture_image_if_enabled=mock.DEFAULT,
            color_transform=mock.DEFAULT,
            combine_textures=mock.DEFAULT,
        )
        patches = [
            context,
            mock.patch.dict(IMG.providers_dict, providers, clear=True),
            mock.patch.dict(
                IMG.local_combined_providers_dict, combined_providers, clear=True
            ),
            mock.patch.object(
                FNAMES, "jpeg_file_dir_from_attributes", return_value=self.temp_dir.name
            ),
            mock.patch.object(FNAMES, "resource_path", return_value=tmp_dir),
            mock.patch.object(IMG.UI, "vprint"),
        ]
        return _ConvertTexturePatchContext(patches, result, tmp_dir)


class _ConvertTexturePatchContext:
    def __init__(self, patches, command_result, tmp_dir):
        self.patches = patches
        self.command_result = command_result
        self.tmp_dir = tmp_dir
        self.started = []

    def __enter__(self):
        multiple_mocks = self.patches[0].start()
        self.started.append(self.patches[0])
        self.run_external_command = multiple_mocks["run_external_command"]
        self.run_external_command.return_value = self.command_result
        self.normalize = multiple_mocks["normalize_texture_image_if_enabled"]
        self.color_transform = multiple_mocks["color_transform"]
        self.combine_textures = multiple_mocks["combine_textures"]
        for patcher in self.patches[1:-1]:
            patcher.start()
            self.started.append(patcher)
        self.vprint = self.patches[-1].start()
        self.started.append(self.patches[-1])
        return self

    def __exit__(self, exc_type, exc, traceback):
        for patcher in reversed(self.started):
            patcher.stop()

    @property
    def command(self):
        return self.run_external_command.call_args.args[0]


if __name__ == "__main__":
    unittest.main()
