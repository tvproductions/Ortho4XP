import os
import unittest
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from tests._imagery_color_normalization_helpers import (
    ImageryColorNormalizationTestCase,
)
import O4_File_Names as FNAMES
import O4_Texture_Color_Normalization as TCN


class TextureImageNormalizationTests(ImageryColorNormalizationTestCase):
    def test_normalize_texture_image_is_bypassed_when_disabled(self):
        image = Image.new("RGB", (16, 16), (90, 80, 70))

        with mock.patch.object(TCN, "normalize_image_with_neighbors") as normalize:
            result = TCN.normalize_texture_image_if_enabled(
                image,
                self._color_context(enabled=False),
            )

        self.assertEqual(result.tobytes(), image.tobytes())
        normalize.assert_not_called()

    def test_normalize_texture_image_loads_existing_cardinal_neighbors(self):
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
            TCN, "normalize_image_with_neighbors", side_effect=fake_normalize
        ) as normalize:
            result = TCN.normalize_texture_image_if_enabled(
                image,
                self._color_context(provider_code=attrs[-1]),
            )

        normalize.assert_called_once()
        self.assertEqual(result.getpixel((0, 0)), (120, 120, 120))

    def test_normalize_texture_image_skips_missing_and_invalid_neighbors(self):
        image = Image.new("RGB", (16, 16), (90, 80, 70))
        bad_path = os.path.join(
            self.temp_dir.name,
            FNAMES.jpeg_file_name_from_attributes(32, 32, 16, "BI"),
        )
        with open(bad_path, "w", encoding="utf-8") as handle:
            handle.write("not an image")

        with mock.patch.object(
            TCN, "normalize_image_with_neighbors", return_value=image
        ) as normalize:
            result = TCN.normalize_texture_image_if_enabled(
                image,
                self._color_context(),
            )

        self.assertEqual(result.tobytes(), image.tobytes())
        normalize.assert_not_called()

    def test_normalize_texture_image_skips_wrong_sized_neighbors(self):
        image = Image.new("RGB", (16, 16), (90, 80, 70))
        wrong_size_path = os.path.join(
            self.temp_dir.name,
            FNAMES.jpeg_file_name_from_attributes(32, 32, 16, "BI"),
        )
        Image.new("RGB", (8, 16), (100, 110, 120)).save(wrong_size_path)

        with mock.patch.object(
            TCN, "normalize_image_with_neighbors", return_value=image
        ) as normalize:
            result = TCN.normalize_texture_image_if_enabled(
                image,
                self._color_context(),
            )

        self.assertEqual(result.tobytes(), image.tobytes())
        normalize.assert_not_called()

    def test_loaded_neighbor_images_remain_usable_after_file_close(self):
        neighbor_path = os.path.join(
            self.temp_dir.name,
            FNAMES.jpeg_file_name_from_attributes(32, 32, 16, "BI"),
        )
        Image.new("RGB", (16, 16), (100, 110, 120)).save(neighbor_path)

        neighbors = TCN.load_neighbor_texture_images(
            self._color_context(),
            (16, 16),
        )

        self.assertEqual(set(neighbors), {"north"})
        self.assertEqual(neighbors["north"].getpixel((0, 0)), (100, 110, 120))


if __name__ == "__main__":
    unittest.main()
