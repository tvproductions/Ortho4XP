import math
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Mask_Validation as MV


class SandMaskValidationTests(unittest.TestCase):
    def test_zero_and_valid_widths_produce_safe_geometry(self):
        self.assertEqual(
            MV.validate_sand_mask(0, 2.0, (6144, 6144)),
            MV.SandMaskGeometry(0, 0),
        )
        self.assertEqual(
            MV.validate_sand_mask(100, 2.0, (6144, 6144)),
            MV.SandMaskGeometry(50, 99),
        )

    def test_rejects_non_scalar_non_finite_and_negative_widths(self):
        for width in ([10, 20, 30], "100", math.inf, math.nan, -1, True):
            with self.subTest(width=width), self.assertRaises(ValueError):
                MV.validate_sand_mask(width, 2.0, (6144, 6144))

    def test_rejects_invalid_pixel_scales(self):
        for pixel_size in (0, -2.0, True, "2.0", math.nan, math.inf, -math.inf):
            with self.subTest(pixel_size=pixel_size), self.assertRaises(ValueError):
                MV.validate_sand_mask(100, pixel_size, (6144, 6144))

    def test_rejects_width_and_pixel_scale_overflow(self):
        overflow = 10**10000
        for width, pixel_size in (
            (overflow, 2.0),
            (100, overflow),
        ):
            self._assert_invalid_sand_mask(width, pixel_size)

    def _assert_invalid_sand_mask(self, width, pixel_size):
        with self.assertRaises(ValueError):
            MV.validate_sand_mask(width, pixel_size, (6144, 6144))

    def test_rejects_invalid_image_shapes(self):
        for shape in (None, 0, (), (6144,), (0, 6144), (2, 3, 4)):
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                MV.validate_sand_mask(100, 2.0, shape)

    def test_rejects_kernel_larger_than_working_image(self):
        with self.assertRaisesRegex(ValueError, "kernel"):
            MV.validate_sand_mask(7000, 2.0, (6144, 6144))


if __name__ == "__main__":
    unittest.main()
