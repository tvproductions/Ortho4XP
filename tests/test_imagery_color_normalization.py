import os
import tempfile
import unittest
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

    def _color_for_edge(self, edge):
        return {
            "north": (100, 110, 120),
            "south": (120, 110, 100),
            "west": (80, 100, 120),
            "east": (120, 100, 80),
        }[edge]


if __name__ == "__main__":
    unittest.main()
