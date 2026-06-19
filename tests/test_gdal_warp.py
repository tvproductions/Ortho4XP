import unittest
from unittest import mock

import numpy
from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class GDALWarpTests(unittest.TestCase):
    def test_warp_image_with_gdal_returns_requested_size(self):
        from O4_Imagery_Utils import warp_image_with_gdal

        source_im = Image.new("RGB", (16, 16), (255, 0, 0))

        result = warp_image_with_gdal(
            source_im,
            (0, 1, 1, 0),
            4326,
            (0, 1, 1, 0),
            4326,
            (32, 24),
        )

        self.assertIsInstance(result, Image.Image)
        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, (32, 24))

    def test_warp_image_with_gdal_preserves_rgb_channels(self):
        from O4_Imagery_Utils import warp_image_with_gdal

        source_array = numpy.zeros((8, 8, 3), dtype=numpy.uint8)
        source_array[:, :3, 0] = 255
        source_array[:, 3:6, 1] = 255
        source_array[:, 6:, 2] = 255
        source_im = Image.fromarray(source_array, "RGB")

        result = warp_image_with_gdal(
            source_im,
            (0, 1, 1, 0),
            4326,
            (0, 1, 1, 0),
            4326,
            source_im.size,
        )

        result_array = numpy.array(result)
        self.assertGreater(result_array[4, 1, 0], 200)
        self.assertGreater(result_array[4, 4, 1], 200)
        self.assertGreater(result_array[4, 7, 2], 200)

    def test_warp_image_with_gdal_preserves_grayscale_mode(self):
        from O4_Imagery_Utils import warp_image_with_gdal

        source_array = numpy.zeros((8, 8), dtype=numpy.uint8)
        source_array[2:6, 2:6] = 255
        source_im = Image.fromarray(source_array, "L")

        result = warp_image_with_gdal(
            source_im,
            (0, 1, 1, 0),
            4326,
            (0, 1, 1, 0),
            4326,
            source_im.size,
        )

        self.assertEqual(result.mode, "L")
        self.assertGreater(numpy.array(result)[4, 4], 200)

    def test_warp_image_with_gdal_uses_configured_resampling(self):
        import O4_Imagery_Utils as IMG

        source_im = Image.new("RGB", (8, 8), (255, 0, 0))
        original_warp = IMG.gdal.Warp
        captured = {}
        previous = IMG.warp_resampling

        def warp(*args, **kwargs):
            captured["resampleAlg"] = kwargs["resampleAlg"]
            return original_warp(*args, **kwargs)

        try:
            IMG.warp_resampling = "nearest"
            with mock.patch.object(IMG.gdal, "Warp", side_effect=warp):
                IMG.warp_image_with_gdal(
                    source_im,
                    (0, 1, 1, 0),
                    4326,
                    (0, 1, 1, 0),
                    4326,
                    source_im.size,
                )
        finally:
            IMG.warp_resampling = previous

        self.assertEqual(captured["resampleAlg"], "near")


if __name__ == "__main__":
    unittest.main()
