import unittest
from types import SimpleNamespace
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class ResamplingRuntimeSelectionTests(unittest.TestCase):
    def test_texture_resize_uses_configured_module_resampling(self):
        import O4_Imagery_Utils as IMG

        source = Image.new("RGB", (8, 8), "red")
        captured = {}

        def resize(size, resample=None, box=None, reducing_gap=None):
            captured["resample"] = resample
            return Image.new("RGB", size, "red")

        previous = IMG.texture_resize_resampling
        IMG.texture_resize_resampling = "nearest"
        self.addCleanup(setattr, IMG, "texture_resize_resampling", previous)
        with (
            mock.patch.object(IMG, "get_wmts_image", return_value=(True, source)),
            mock.patch.object(source, "resize", side_effect=resize),
        ):
            IMG.get_and_paste_wmts_part(
                16, 32, 48, {}, mock.Mock(), 0, 0, None, subt_size=(4, 4)
            )

        self.assertEqual(captured["resample"], Image.Resampling.NEAREST)

    def test_alpha_mask_imprinting_uses_tile_mask_resampling(self):
        import O4_Resampling_Policy as RP

        mask = Image.new("L", (8, 8), "white")
        captured = {}

        def resize(size, resample=None, box=None, reducing_gap=None):
            captured["resample"] = resample
            return Image.new("L", size, "white")

        with mock.patch.object(mask, "resize", side_effect=resize):
            RP.tile_resize_image(
                SimpleNamespace(mask_resize_resampling="nearest"),
                "mask_resize_resampling",
                mask,
                (4, 4),
            )

        self.assertEqual(captured["resample"], Image.Resampling.NEAREST)


if __name__ == "__main__":
    unittest.main()
