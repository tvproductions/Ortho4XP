import math
import unittest

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Provider_Scoring as SCORE


class ProviderScoringTests(unittest.TestCase):
    def test_uniform_low_risk_image_scores_high_quality(self):
        image = Image.new("RGB", (32, 32), (96, 128, 96))

        result = SCORE.score_provider_image("BI", (32, 48, 16, "BI"), image)

        self.assertEqual(result.provider_code, "BI")
        self.assertEqual(result.quality_label, "excellent")
        self.assertGreaterEqual(result.global_score, 90)
        self.assertEqual(result.metrics.noise, 0)
        self.assertEqual(result.metrics.jpeg_compression, 0)
        self.assertEqual(result.metrics.clouds, 0)
        self.assertEqual(result.metrics.color_drift, 0)
        self.assertEqual(result.metrics.seam_risk, 0)

    def test_blocky_cloudy_edge_drift_image_scores_low_quality(self):
        pixels = []
        for y in range(32):
            for x in range(32):
                if x < 8:
                    pixels.append((240, 240, 240))
                elif x >= 24:
                    pixels.append((15, 45, 110))
                elif (x // 8 + y // 8) % 2 == 0:
                    pixels.append((55, 75, 55))
                else:
                    pixels.append((40, 70, 40))
        image = Image.new("RGB", (32, 32))
        image.putdata(pixels)

        result = SCORE.score_provider_image("BI", (32, 48, 16, "BI"), image)

        self.assertEqual(result.quality_label, "poor")
        self.assertLess(result.global_score, 60)
        self.assertGreater(result.metrics.jpeg_compression, 20)
        self.assertGreater(result.metrics.clouds, 20)
        self.assertGreater(result.metrics.color_drift, 20)
        self.assertGreater(result.metrics.seam_risk, 20)

    def test_score_clamps_metrics_and_labels_boundaries(self):
        metrics = SCORE.ProviderScoreMetrics(
            noise=200,
            jpeg_compression=80,
            clouds=-10,
            color_drift=0,
            seam_risk=50,
        )

        result = SCORE.provider_score_from_metrics("Arc", (1, 2, 3, "Arc"), metrics)

        self.assertTrue(math.isclose(result.global_score, 54.0))
        self.assertEqual(result.quality_label, "poor")
        self.assertEqual(result.metrics.noise, 100)
        self.assertEqual(result.metrics.clouds, 0)
        self.assertEqual(result.to_context()["provider_code"], "Arc")

    def test_metric_details_are_preserved_in_score_context(self):
        metrics = SCORE.ProviderScoreMetrics(
            noise=0,
            jpeg_compression=0,
            clouds=12.345,
            color_drift=0,
            seam_risk=23.456,
            details={
                "clouds": {"cloud_coverage_pct": 8.2},
                "seam_risk": {"worst_edge": "right"},
            },
        )

        result = SCORE.provider_score_from_metrics("BI", (32, 48, 16, "BI"), metrics)
        context = result.to_context()

        self.assertEqual(context["metrics"]["clouds"], 12.35)
        self.assertEqual(context["metrics"]["seam_risk"], 23.46)
        self.assertEqual(
            context["details"]["clouds"],
            {"cloud_coverage_pct": 8.2},
        )
        self.assertEqual(context["details"]["seam_risk"], {"worst_edge": "right"})

    def test_to_context_returns_isolated_details_copy(self):
        details = {"clouds": {"cloud_coverage_pct": 8.2}}
        metrics = SCORE.ProviderScoreMetrics(
            noise=0,
            jpeg_compression=0,
            clouds=0,
            color_drift=0,
            seam_risk=0,
            details=details,
        )
        result = SCORE.provider_score_from_metrics("BI", (32, 48, 16, "BI"), metrics)
        context = result.to_context()

        context["details"]["clouds"]["cloud_coverage_pct"] = 99.9

        self.assertEqual(result.metrics.details["clouds"]["cloud_coverage_pct"], 8.2)


if __name__ == "__main__":
    unittest.main()
