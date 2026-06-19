import unittest
from types import SimpleNamespace

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class ResamplingPolicyTests(unittest.TestCase):
    def test_pillow_resampling_maps_config_names_to_pillow_constants(self):
        import O4_Resampling_Policy as RP

        self.assertEqual(RP.pillow_resampling("nearest"), Image.Resampling.NEAREST)
        self.assertEqual(RP.pillow_resampling("bilinear"), Image.Resampling.BILINEAR)
        self.assertEqual(RP.pillow_resampling("bicubic"), Image.Resampling.BICUBIC)
        self.assertEqual(RP.pillow_resampling("lanczos"), Image.Resampling.LANCZOS)

    def test_gdal_resampling_maps_config_names_to_gdal_strings(self):
        import O4_Resampling_Policy as RP

        self.assertEqual(RP.gdal_resampling("nearest"), "near")
        self.assertEqual(RP.gdal_resampling("bilinear"), "bilinear")
        self.assertEqual(RP.gdal_resampling("bicubic"), "cubic")
        self.assertEqual(RP.gdal_resampling("lanczos"), "lanczos")

    def test_policy_rejects_unknown_direct_method_names(self):
        import O4_Resampling_Policy as RP

        with self.assertRaisesRegex(ValueError, "average"):
            RP.pillow_resampling("average")
        with self.assertRaisesRegex(ValueError, "average"):
            RP.gdal_resampling("average")

    def test_tile_helpers_read_tile_value_and_fall_back_to_default(self):
        import O4_Resampling_Policy as RP

        tile = SimpleNamespace(warp_resampling="nearest")

        self.assertEqual(RP.tile_gdal_resampling(tile, "warp_resampling"), "near")
        self.assertEqual(
            RP.tile_pillow_resampling(tile, "texture_resize_resampling"),
            Image.Resampling.LANCZOS,
        )


if __name__ == "__main__":
    unittest.main()
