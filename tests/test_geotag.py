import unittest
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Geotag as GEOTAG


class StandaloneGeotagTests(unittest.TestCase):
    def test_geotag_jpeg_uses_gdal_translate_and_warp(self):
        with (
            mock.patch.object(
                GEOTAG,
                "gtile_to_wgs84",
                side_effect=[(1.0, 2.0), (0.0, 3.0)],
            ),
            mock.patch.object(
                GEOTAG.geo_to_webm,
                "transform",
                side_effect=[(20, 0), (30, 10)],
            ),
            mock.patch.object(GEOTAG, "gdal") as gdal_mock,
            mock.patch.object(GEOTAG.os, "remove") as remove_mock,
        ):
            _geotag_jpeg_with_resampling("nearest")

        gdal_mock.Translate.assert_called_once_with(
            "48_32_16_tmp.tif",
            "48_32_16.jpg",
            format="GTiff",
            creationOptions=["COMPRESS=JPEG"],
            outputBounds=[20, 0, 30, 10],
            outputSRS="EPSG:3857",
        )
        gdal_mock.Warp.assert_called_once_with(
            "48_32_16.tif",
            "48_32_16_tmp.tif",
            format="GTiff",
            creationOptions=["COMPRESS=JPEG"],
            srcSRS="EPSG:3857",
            dstSRS="EPSG:4326",
            width=4096,
            height=4096,
            resampleAlg="near",
        )
        remove_mock.assert_called_once_with("48_32_16_tmp.tif")


def _geotag_jpeg_with_resampling(method):
    previous = GEOTAG.warp_resampling
    GEOTAG.warp_resampling = method
    try:
        GEOTAG.geotag_jpeg("48_32_16.jpg")
    finally:
        GEOTAG.warp_resampling = previous


if __name__ == "__main__":
    unittest.main()
