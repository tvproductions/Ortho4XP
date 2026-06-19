import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from PIL import Image, ImageFilter

import O4_Imagery_Utils as IMG


class ColorFilterTests(unittest.TestCase):
    def test_color_transform_applies_unsharp_mask_sharpen_operation(self):
        image = Image.new("RGB", (5, 5), (120, 120, 120))
        image.putpixel((2, 2), (220, 220, 220))
        filters = IMG.color_filters_dict.copy()
        IMG.color_filters_dict["SHARPEN"] = [["sharpen", 1.5, 180.0, 2.0]]
        try:
            result = IMG.color_transform(image.copy(), "SHARPEN")
        finally:
            IMG.color_filters_dict.clear()
            IMG.color_filters_dict.update(filters)

        expected = image.filter(
            ImageFilter.UnsharpMask(radius=1.5, percent=180, threshold=2)
        )
        self.assertEqual(result.tobytes(), expected.tobytes())


if __name__ == "__main__":
    unittest.main()
