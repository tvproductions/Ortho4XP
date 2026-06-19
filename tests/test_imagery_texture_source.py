import os
import tempfile
import unittest
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Imagery_Utils as IMG
from O4_Texture_Source import TextureBuildResult


class ImageryTextureSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.provider = {
            "grid_type": "webmercator",
            "tile_size": 256,
            "request_type": "tms",
            "color_filters": "none",
        }
        self.original_providers = IMG.providers_dict.copy()
        self.addCleanup(self._restore_providers)
        IMG.providers_dict.clear()
        IMG.providers_dict["BI"] = self.provider

    def _restore_providers(self):
        IMG.providers_dict.clear()
        IMG.providers_dict.update(self.original_providers)

    def test_build_texture_source_returns_image_without_writing_cache(self):
        tile = type("Tile", (), {"lat": 1, "lon": 2})()
        cache_dir = os.path.join(self.temp_dir.name, "cache")
        cache_path = os.path.join(cache_dir, "32_48_BI16.jpg")
        image = Image.new("RGB", (4096, 4096), (1, 2, 3))

        with (
            mock.patch.object(
                IMG.FNAMES,
                "jpeg_file_name_from_attributes",
                return_value="32_48_BI16.jpg",
            ),
            mock.patch.object(
                IMG.FNAMES,
                "jpeg_file_dir_from_attributes",
                return_value=cache_dir,
            ),
            mock.patch.object(
                IMG, "build_texture_from_tilbox", return_value=(1, image)
            ),
        ):
            result = IMG.build_texture_source(
                tile, (32, 48, 16, "BI"), persist_cache=False
            )

        self.assertIsInstance(result, TextureBuildResult)
        self.assertEqual(result.ok, 1)
        self.assertEqual(result.source.image.size, (4096, 4096))
        self.assertEqual(result.source.cache_path, cache_path)
        self.assertFalse(result.source.wrote_cache)
        self.assertFalse(os.path.exists(cache_path))

    def test_download_jpeg_ortho_still_writes_cache(self):
        file_dir = os.path.join(self.temp_dir.name, "cache")
        image = Image.new("RGB", (4096, 4096), (1, 2, 3))

        with mock.patch.object(
            IMG, "_assemble_ortho_image", return_value=(1, image, False)
        ):
            ok = IMG.download_jpeg_ortho(file_dir, "32_48_BI16.jpg", 32, 48, 16, "BI")

        self.assertEqual(ok, 1)
        self.assertTrue(os.path.isfile(os.path.join(file_dir, "32_48_BI16.jpg")))


if __name__ == "__main__":
    unittest.main()
