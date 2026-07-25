import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest import mock

import numpy
from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_DDS_Quality as DQA

# Quality tests cover decoded-image metrics, disposition reporting, and the
# enabled-check request boundary independently from native decoder processes.
# Real temporary PNGs keep metric assertions faithful to runtime image modes,
# while decoder and UI patches isolate the disposition contract.
# Request assertions keep QA thresholds and decoded-output naming observable.
# Error assertions preserve caught decoder details for diagnostics.
#


def _expected_enabled_request():
    return DQA.DdsQualityRequest(
        "source.png",
        "out.dds",
        str(Path("tmp") / "out.dds.qa.png"),
        35.5,
        "out.dds",
    )


# DDS QA tests are split across files to keep each surface focused:
# - this file covers pure image metrics and helper enablement;
# - test_dds_quality_config.py covers config registration;
# - test_dds_quality_conversion.py covers conversion integration.
# Fixtures stay tiny so metric expectations can be computed directly.


def _save_rgb(path: Path, pixels) -> None:
    array = numpy.array(pixels, dtype=numpy.uint8)
    Image.fromarray(array, "RGB").save(path)


class DdsQualityMetricTests(unittest.TestCase):
    def test_identical_images_have_zero_mse_and_infinite_psnr(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            decoded = Path(tmp) / "decoded.png"
            pixels = [[[10, 20, 30], [40, 50, 60]]]
            _save_rgb(source, pixels)
            _save_rgb(decoded, pixels)

            metrics = DQA.compute_quality_metrics(str(source), str(decoded))

        self.assertEqual(metrics.mse, 0.0)
        self.assertTrue(math.isinf(metrics.psnr))
        self.assertEqual(metrics.width, 2)
        self.assertEqual(metrics.height, 1)

    def test_changed_pixels_compute_mse_and_psnr(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            decoded = Path(tmp) / "decoded.png"
            _save_rgb(source, [[[10, 20, 30]]])
            _save_rgb(decoded, [[[13, 24, 30]]])

            metrics = DQA.compute_quality_metrics(str(source), str(decoded))

        expected_mse = (9 + 16 + 0) / 3
        expected_psnr = 20 * math.log10(255.0 / math.sqrt(expected_mse))
        self.assertAlmostEqual(metrics.mse, expected_mse)
        self.assertAlmostEqual(metrics.psnr, expected_psnr)

    def test_run_quality_check_warns_below_psnr_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            decoded_fixture = Path(tmp) / "decoded-fixture.png"
            decoded = Path(tmp) / "decoded.png"
            _save_rgb(source, [[[0, 0, 0]]])
            _save_rgb(decoded_fixture, [[[255, 255, 255]]])

            def decode(_dds_path, decoded_path):
                Image.open(decoded_fixture).save(decoded_path)

            with (
                mock.patch.object(DQA, "decode_dds_to_png", side_effect=decode),
                mock.patch.object(DQA.UI, "vprint") as vprint,
            ):
                result = DQA.run_dds_quality_check(
                    DQA.DdsQualityRequest(
                        str(source),
                        "out.dds",
                        str(decoded),
                        60.0,
                        "out.dds",
                    )
                )

        self._assert_below_threshold(result, vprint)

    def _assert_below_threshold(self, result, vprint):
        self.assertEqual(result.disposition, "below_threshold")
        self.assertIsNotNone(result.metrics)
        metrics = cast(DQA.DdsQualityMetrics, result.metrics)
        self.assertAlmostEqual(metrics.psnr, 0.0)
        vprint.assert_called_once()
        message = " ".join(map(str, vprint.call_args.args))
        self.assertIn("below threshold", message)

    def test_run_quality_check_returns_error_disposition_for_caught_failure(self):
        request = DQA.DdsQualityRequest(
            "source.png",
            "out.dds",
            "decoded.png",
            30.0,
            "out.dds",
        )

        with (
            mock.patch.object(
                DQA,
                "decode_dds_to_png",
                side_effect=OSError("decode failed"),
            ),
            mock.patch.object(DQA.UI, "vprint") as vprint,
        ):
            result = DQA.run_dds_quality_check(request)

        self.assertEqual(getattr(result, "disposition", None), "error")
        self.assertIsNone(result.metrics)
        self.assertIn("OSError: decode failed", result.error_summary)
        vprint.assert_called_once()

    def test_run_quality_check_does_not_warn_above_psnr_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            decoded_fixture = Path(tmp) / "decoded-fixture.png"
            decoded = Path(tmp) / "decoded.png"
            pixels = [[[25, 35, 45]]]
            _save_rgb(source, pixels)
            _save_rgb(decoded_fixture, pixels)

            def decode(_dds_path, decoded_path):
                Image.open(decoded_fixture).save(decoded_path)

            with (
                mock.patch.object(DQA, "decode_dds_to_png", side_effect=decode),
                mock.patch.object(DQA.UI, "vprint") as vprint,
            ):
                result = DQA.run_dds_quality_check(
                    DQA.DdsQualityRequest(
                        str(source),
                        "out.dds",
                        str(decoded),
                        60.0,
                        "out.dds",
                    )
                )

        self._assert_quality_passed(result, vprint)

    def _assert_quality_passed(self, result, vprint):
        self.assertEqual(result.disposition, "passed")
        self.assertIsNotNone(result.metrics)
        vprint.assert_not_called()

    def test_enabled_quality_check_builds_decoded_png_request(self):
        tile = SimpleNamespace(dds_qa_enabled=True, dds_qa_psnr_threshold=35.5)
        encode_result = SimpleNamespace(
            ok=True,
            request=SimpleNamespace(
                source_path="source.png",
                output_path="out.dds",
                display_name="out.dds",
            ),
        )

        with (
            mock.patch.object(DQA.FNAMES, "resource_path", return_value="tmp"),
            mock.patch.object(DQA, "run_dds_quality_check") as quality_check,
        ):
            expected = object()
            quality_check.return_value = expected
            result = DQA.run_enabled_dds_quality_check(tile, encode_result)

        quality_check.assert_called_once_with(_expected_enabled_request())
        self.assertIs(result, expected)

    def test_disabled_quality_check_does_not_build_decoded_png_request(self):
        tile = SimpleNamespace(dds_qa_enabled=False)
        encode_result = SimpleNamespace(ok=True)

        with mock.patch.object(DQA, "run_dds_quality_check") as quality_check:
            result = DQA.run_enabled_dds_quality_check(tile, encode_result)

        quality_check.assert_not_called()
        self.assertEqual(getattr(result, "disposition", None), "skipped")
        self.assertTrue(result.allows_cleanup)


if __name__ == "__main__":
    unittest.main()
