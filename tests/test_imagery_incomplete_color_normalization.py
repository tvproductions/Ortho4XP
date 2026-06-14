import os
import unittest
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_File_Names as FNAMES
import O4_Imagery_Failures as IFAIL
import O4_Texture_Color_Normalization as TCN
from tests._imagery_color_normalization_helpers import (
    ImageryColorNormalizationTestCase,
)


class IncompleteNeighborColorNormalizationTests(ImageryColorNormalizationTestCase):
    def test_normalize_texture_image_skips_incomplete_neighbors(self):
        image = Image.new("RGB", (16, 16), (90, 80, 70))
        neighbor_file = FNAMES.jpeg_file_name_from_attributes(32, 32, 16, "BI")
        neighbor_path = os.path.join(self.temp_dir.name, neighbor_file)
        Image.new("RGB", (16, 16), (100, 110, 120)).save(neighbor_path)
        tile_coords = os.path.basename(os.path.dirname(self.temp_dir.name))
        IFAIL.incomplete_imgs[tile_coords] = [{"file_name": neighbor_file}]
        self.addCleanup(IFAIL.incomplete_imgs.pop, tile_coords, None)

        with mock.patch.object(
            TCN, "normalize_image_with_neighbors", return_value=image
        ) as normalize:
            result = TCN.normalize_texture_image_if_enabled(
                image,
                self._color_context(),
            )

        self.assertEqual(result.tobytes(), image.tobytes())
        normalize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
