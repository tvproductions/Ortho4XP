import unittest
from unittest import mock

import numpy
from osgeo import osr
from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_GDAL_Texture_Pipeline as GTP


class GDALTexturePipelineTests(unittest.TestCase):
    def test_memory_dataset_from_rgb_image_preserves_pixels_and_georef(self):
        image = Image.new("RGB", (2, 2), (10, 20, 30))

        dataset = GTP.memory_dataset_from_image(image, (0, 2, 2, 0), 4326)

        self.assertEqual(dataset.RasterXSize, 2)
        self.assertEqual(dataset.RasterYSize, 2)
        self.assertEqual(dataset.RasterCount, 3)
        projection = osr.SpatialReference(wkt=dataset.GetProjection())
        projection.AutoIdentifyEPSG()
        self.assertEqual(projection.GetAuthorityCode(None), "4326")
        self.assertEqual(dataset.GetGeoTransform(), (0.0, 1.0, 0.0, 2.0, 0.0, -1.0))
        self.assertEqual(dataset.GetRasterBand(1).ReadAsArray()[0, 0], 10)
        self.assertEqual(dataset.GetRasterBand(2).ReadAsArray()[0, 0], 20)
        self.assertEqual(dataset.GetRasterBand(3).ReadAsArray()[0, 0], 30)

    def test_vsimem_vrt_from_sources_builds_and_unlinks_vrt(self):
        image = Image.new("RGB", (2, 2), (10, 20, 30))
        dataset = GTP.memory_dataset_from_image(image, (0, 2, 2, 0), 4326)
        unlinked = []

        with mock.patch.object(GTP.gdal, "Unlink", side_effect=unlinked.append):
            with GTP.vsimem_vrt_from_sources([dataset], vrt_name="unit-test") as vrt:
                self.assertEqual(vrt.dataset.RasterXSize, 2)
                self.assertEqual(vrt.dataset.RasterYSize, 2)
                self.assertEqual(vrt.path, "/vsimem/ortho4xp/unit-test.vrt")

        self.assertEqual(unlinked, ["/vsimem/ortho4xp/unit-test.vrt"])

    def test_warp_dataset_to_image_returns_requested_size(self):
        source = Image.new("RGB", (4, 4), (200, 10, 20))
        dataset = GTP.memory_dataset_from_image(source, (0, 1, 1, 0), 4326)

        result = GTP.warp_dataset_to_image(
            dataset,
            (0, 1, 1, 0),
            4326,
            (8, 6),
            "near",
            "RGB",
        )

        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, (8, 6))
        self.assertGreater(numpy.array(result)[2, 2, 0], 150)


if __name__ == "__main__":
    unittest.main()
