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
import O4_Imagery_Utils as IMG
import O4_Texture_Color_Normalization as TCN


class DownloadJpegColorNormalizationTests(ImageryColorNormalizationTestCase):
    def test_download_jpeg_ortho_leaves_cache_raw_for_conversion_normalization(self):
        provider_code = "TEST"
        provider = {"code": provider_code, "request_type": "test"}

        for success in (True, False):
            with self.subTest(success=success):
                image = Image.new("RGB", (16, 16), (90, 80, 70))
                file_name = f"download-success-{success}.jpg"

                with (
                    mock.patch.dict(IMG.providers_dict, {provider_code: provider}),
                    mock.patch.object(IMG.UI, "red_flag", False),
                    mock.patch.object(
                        IMG,
                        "build_texture_from_bbox_and_size",
                        return_value=(success, image),
                    ),
                    mock.patch.object(
                        TCN,
                        "normalize_texture_image_if_enabled",
                    ) as normalize,
                    mock.patch.object(IMG.UI, "lvprint"),
                    mock.patch.object(IMG, "record_incomplete_texture"),
                ):
                    IMG.download_jpeg_ortho(
                        self.temp_dir.name,
                        file_name,
                        32,
                        48,
                        16,
                        provider_code,
                    )

                normalize.assert_not_called()


if __name__ == "__main__":
    unittest.main()
