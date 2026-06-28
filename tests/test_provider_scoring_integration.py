import os
import tempfile
import unittest
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Imagery_Utils as IMG


class ProviderScoringIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_providers = IMG.providers_dict.copy()
        self.addCleanup(self._restore_providers)
        IMG.providers_dict.clear()
        IMG.providers_dict["BI"] = {
            "grid_type": "webmercator",
            "tile_size": 256,
            "request_type": "tms",
            "color_filters": "none",
        }

    def _restore_providers(self):
        IMG.providers_dict.clear()
        IMG.providers_dict.update(self.original_providers)

    def test_build_texture_source_records_provider_score(self):
        tile = type("Tile", (), {"lat": 1, "lon": 2})()
        cache_dir = os.path.join(self.temp_dir.name, "cache")
        image = Image.new("RGB", (4096, 4096), (96, 128, 96))

        with (
            mock.patch.object(
                IMG.FNAMES,
                "jpeg_file_name_from_attributes",
                return_value="32_48_BI16.jpg",
            ),
            mock.patch.object(
                IMG.FNAMES,
                "jpeg_file_dir_from_attributes",
                return_value=cache_dir,
            ),
            mock.patch.object(
                IMG, "build_texture_from_tilbox", return_value=(1, image)
            ),
            mock.patch.object(IMG.UI, "log_event") as log_event,
        ):
            result = IMG.build_texture_source(
                tile, (32, 48, 16, "BI"), persist_cache=False
            )

        self.assertEqual(result.ok, 1)
        score_context = _provider_score_context(log_event)
        self.assertEqual(score_context["provider_code"], "BI")
        self.assertEqual(score_context["tile_x"], 32)
        self.assertEqual(score_context["tile_y"], 48)
        self.assertEqual(score_context["zoomlevel"], 16)
        self.assertEqual(score_context["quality_label"], "excellent")
        self.assertGreaterEqual(score_context["global_score"], 90)
        self._assert_score_details(score_context)

    def test_download_jpeg_ortho_records_provider_score(self):
        file_dir = os.path.join(self.temp_dir.name, "cache")
        image = Image.new("RGB", (4096, 4096), (96, 128, 96))

        with (
            mock.patch.object(
                IMG, "_assemble_ortho_image", return_value=(1, image, False)
            ),
            mock.patch.object(IMG.UI, "log_event") as log_event,
        ):
            ok = IMG.download_jpeg_ortho(file_dir, "32_48_BI16.jpg", 32, 48, 16, "BI")

        self.assertEqual(ok, 1)
        score_context = _provider_score_context(log_event)
        self.assertEqual(score_context["provider_code"], "BI")
        self.assertEqual(score_context["quality_label"], "excellent")

    def _assert_score_details(self, score_context):
        self.assertIn("details", score_context)
        self.assertIn("clouds", score_context["details"])
        self.assertIn("seam_risk", score_context["details"])
        self.assertIn(
            "cloud_coverage_pct",
            score_context["details"]["clouds"],
        )
        self.assertIn("worst_edge", score_context["details"]["seam_risk"])


def _provider_score_context(log_event):
    log_event.assert_any_call(
        "Provider imagery score",
        level="INFO",
        context=mock.ANY,
    )
    return log_event.call_args_list[-1].kwargs["context"]


if __name__ == "__main__":
    unittest.main()
