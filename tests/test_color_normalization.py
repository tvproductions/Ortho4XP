import unittest

import numpy
from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Color_Normalization as CNORM


class ColorNormalizationTests(unittest.TestCase):
    def test_srgb_linear_round_trip_preserves_representative_values(self):
        source = numpy.array([[[0, 12, 64], [128, 200, 255]]], dtype=numpy.uint8)

        linear = CNORM.srgb_to_linear_array(source)
        restored = CNORM.linear_to_srgb_array(linear)

        self.assertLessEqual(
            numpy.abs(restored.astype(int) - source.astype(int)).max(), 1
        )

    def test_edge_extraction_uses_requested_band(self):
        pixels = numpy.arange(4 * 5 * 3, dtype=numpy.uint8).reshape((4, 5, 3))
        image = Image.fromarray(pixels, "RGB")

        north = CNORM.extract_edge_pixels(image, "north", band_width=2)
        south = CNORM.extract_edge_pixels(image, "south", band_width=2)
        west = CNORM.extract_edge_pixels(image, "west", band_width=2)
        east = CNORM.extract_edge_pixels(image, "east", band_width=2)

        numpy.testing.assert_array_equal(north, pixels[:2, :, :])
        numpy.testing.assert_array_equal(south, pixels[-2:, :, :])
        numpy.testing.assert_array_equal(west, pixels[:, :2, :])
        numpy.testing.assert_array_equal(east, pixels[:, -2:, :])

    def test_edge_stats_distinguish_luminance_and_channel_balance(self):
        warm_dark = Image.new("RGB", (16, 16), (120, 80, 40))
        cool_bright = Image.new("RGB", (16, 16), (150, 170, 190))

        warm_stats = CNORM.edge_stats(warm_dark, "east", band_width=4)
        cool_stats = CNORM.edge_stats(cool_bright, "west", band_width=4)

        self.assertGreater(cool_stats.mean_luminance, warm_stats.mean_luminance)
        self.assertGreater(warm_stats.mean_rgb[0], warm_stats.mean_rgb[2])
        self.assertGreater(cool_stats.mean_rgb[2], cool_stats.mean_rgb[0])
        self.assertEqual(warm_stats.pixel_count, 64)

    def test_correction_moves_target_toward_neighbor_with_clamps(self):
        target = CNORM.edge_stats(Image.new("RGB", (32, 32), (80, 60, 40)), "east")
        neighbor = CNORM.edge_stats(
            Image.new("RGB", (32, 32), (220, 230, 240)), "west"
        )

        correction = CNORM.derive_color_correction([(target, neighbor)])

        self.assertEqual(correction.exposure_scale, CNORM.MAX_EXPOSURE_SCALE)
        for scale in correction.channel_scales:
            self.assertGreaterEqual(scale, CNORM.MIN_CHANNEL_SCALE)
            self.assertLessEqual(scale, CNORM.MAX_CHANNEL_SCALE)
        self.assertEqual(correction.strength, CNORM.DEFAULT_CORRECTION_STRENGTH)

    def test_apply_color_correction_preserves_mode_size_and_changes_pixels(self):
        image = Image.new("RGB", (8, 8), (100, 90, 80))
        correction = CNORM.ColorCorrection(
            exposure_scale=1.1,
            channel_scales=(1.0, 1.05, 1.1),
            strength=1.0,
        )

        result = CNORM.apply_color_correction(image, correction)

        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, image.size)
        self.assertNotEqual(result.getpixel((0, 0)), image.getpixel((0, 0)))

    def test_normalize_image_with_neighbors_returns_unchanged_without_valid_neighbors(self):
        image = Image.new("RGB", (16, 16), (100, 110, 120))

        result = CNORM.normalize_image_with_neighbors(
            image,
            {
                "north": Image.new("RGB", (8, 8), (200, 200, 200)),
                "diagonal": Image.new("RGB", (16, 16), (200, 200, 200)),
            },
            band_width=4,
        )

        self.assertEqual(result.tobytes(), image.tobytes())

    def test_normalize_image_with_neighbors_uses_opposite_neighbor_edge(self):
        target = Image.new("RGB", (16, 16), (90, 70, 50))
        neighbor = Image.new("RGB", (16, 16), (150, 160, 170))

        result = CNORM.normalize_image_with_neighbors(
            target,
            {"east": neighbor},
            band_width=4,
        )

        self.assertNotEqual(result.getpixel((8, 8)), target.getpixel((8, 8)))


if __name__ == "__main__":
    unittest.main()
