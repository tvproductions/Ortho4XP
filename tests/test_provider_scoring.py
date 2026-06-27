"""Regression coverage for provider imagery scoring heuristics."""

import math
import unittest

import numpy
from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Provider_Scoring as SCORE


class ProviderScoringTests(unittest.TestCase):
    def _score_image(
        self,
        image: Image.Image,
        scoring_context: SCORE.ProviderScoreContext | None = None,
    ) -> SCORE.ProviderScoreResult:
        return SCORE.score_provider_image(
            "BI",
            (32, 48, 16, "BI"),
            image,
            scoring_context=scoring_context,
        )

    def _image_from_coords(self, pixel_fn) -> Image.Image:
        image = Image.new("RGB", (32, 32))
        image.putdata([pixel_fn(x, y) for y in range(32) for x in range(32)])
        return image

    def test_uniform_low_risk_image_scores_high_quality(self):
        image = Image.new("RGB", (32, 32), (96, 128, 96))

        result = self._score_image(image)

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

        result = self._score_image(image)

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

    def test_small_cloud_coverage_under_tolerance_is_not_penalized(self):
        image = Image.new("RGB", (20, 20), (80, 130, 85))
        pixels = [(80, 130, 85)] * 400
        for index in range(16):
            pixels[index] = (242, 242, 242)
        image.putdata(pixels)

        result = self._score_image(image)

        self.assertEqual(result.metrics.clouds, 0)
        self.assertLess(
            result.metrics.details["clouds"]["cloud_coverage_pct"],
            5.0,
        )

    def test_dense_cloud_coverage_above_tolerance_increases_cloud_risk(self):
        image = Image.new("RGB", (20, 20), (80, 130, 85))
        pixels = [(80, 130, 85)] * 400
        for index in range(80):
            pixels[index] = (242, 242, 242)
        image.putdata(pixels)

        result = self._score_image(image)

        self.assertGreater(result.metrics.clouds, 20)
        self.assertGreater(
            result.metrics.details["clouds"]["dense_cloud_pct"],
            15,
        )

    def test_blue_sky_like_pixels_are_excluded_from_cloud_coverage(self):
        image = Image.new("RGB", (20, 20), (110, 155, 230))

        result = self._score_image(image)

        self.assertEqual(result.metrics.clouds, 0)
        self.assertGreater(
            result.metrics.details["clouds"]["blue_sky_excluded_pct"],
            90,
        )

    def test_low_variance_haze_increases_cloud_risk(self):
        image = Image.new("RGB", (20, 20), (188, 188, 185))

        result = self._score_image(image)

        self.assertGreater(result.metrics.clouds, 80)
        self.assertGreater(result.metrics.details["clouds"]["veil_pct"], 90)

    def test_single_problematic_edge_increases_seam_risk_and_identifies_edge(self):
        image = self._image_from_coords(
            lambda x, _y: (210, 210, 210) if x >= 30 else (95, 130, 95)
        )

        result = self._score_image(image)

        self.assertGreater(result.metrics.seam_risk, 20)
        self.assertEqual(result.metrics.details["seam_risk"]["worst_edge"], "right")
        self.assertGreater(
            result.metrics.details["seam_risk"]["edges"]["right"]["risk"],
            result.metrics.details["seam_risk"]["edges"]["left"]["risk"],
        )

    def test_abrupt_border_gradient_increases_seam_risk(self):
        image = self._image_from_coords(
            lambda _x, y: (225, 225, 225) if y == 1 else (90, 125, 90)
        )

        result = self._score_image(image)

        self.assertGreater(result.metrics.seam_risk, 10)
        self.assertGreater(
            result.metrics.details["seam_risk"]["edges"]["top"]["border_gradient"],
            50,
        )

    def test_neighbor_edge_mismatch_increases_seam_risk_when_context_is_supplied(self):
        image = Image.new("RGB", (32, 32), (95, 130, 95))
        neighbor_edge = numpy.full((32, 2, 3), 230.0)
        scoring_context = SCORE.ProviderScoreContext(
            neighbor_edges={"right": neighbor_edge}
        )

        result = self._score_image(image, scoring_context=scoring_context)

        self.assertGreater(result.metrics.seam_risk, 20)
        self.assertTrue(result.metrics.details["seam_risk"]["neighbor_compared"])
        self.assertEqual(result.metrics.details["seam_risk"]["worst_edge"], "right")


if __name__ == "__main__":
    unittest.main()
