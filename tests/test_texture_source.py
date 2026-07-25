import unittest
from typing import Any, cast

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Texture_Source import TextureBuildResult, TextureSource

# Source tests distinguish requested terrain identity from resolved provider
# identity while preserving the legacy success/failure facade contract.
#


class TextureSourceTests(unittest.TestCase):
    def test_source_preserves_requested_identity_after_provider_resolution(self):
        source = TextureSource(
            object(),
            (32, 48, 16, "Arc"),
            Image.new("RGB", (4, 4)),
        ).with_requested_attrs(cast(Any, [32, 48, 16, "BI"]))

        self.assertEqual(source.provider_code, "Arc")
        self.assertEqual(source.terrain_attrs, (32, 48, 16, "BI"))
        self.assertIsInstance(source.requested_attrs, tuple)
        self.assertEqual(source.output_name(), "48_32_Arc16.dds")
        self.assertEqual(source.output_name("jpg"), "48_32_Arc16.jpg")

    def test_source_exposes_texture_attributes(self):
        tile = object()
        image = Image.new("RGB", (4, 4), (10, 20, 30))
        source = TextureSource(tile, (32, 48, 16, "BI"), image, "cache.jpg", False)

        self.assertIs(source.tile, tile)
        self.assertEqual(source.til_x_left, 32)
        self.assertEqual(source.til_y_top, 48)
        self.assertEqual(source.zoomlevel, 16)
        self.assertEqual(source.provider_code, "BI")
        self.assertEqual(source.cache_path, "cache.jpg")
        self.assertFalse(source.wrote_cache)

    def test_success_result_has_legacy_ok_value(self):
        source = TextureSource(object(), (32, 48, 16, "BI"), Image.new("RGB", (4, 4)))

        result = TextureBuildResult.success(source, incomplete=True)

        self.assertEqual(result.ok, 1)
        self.assertIs(result.source, source)
        self.assertTrue(result.incomplete)
        self.assertIsNone(result.error_summary)

    def test_failure_result_has_attributes_without_source(self):
        result = TextureBuildResult.failure(
            (32, 48, 16, "BI"),
            "GDAL warp failed",
            incomplete=True,
        )

        self.assertEqual(result.ok, 0)
        self.assertIsNone(result.source)
        self.assertEqual(result.attrs, (32, 48, 16, "BI"))
        self.assertEqual(result.provider_code, "BI")
        self.assertEqual(result.error_summary, "GDAL warp failed")
        self.assertTrue(result.incomplete)


if __name__ == "__main__":
    unittest.main()
