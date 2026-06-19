import queue
import unittest
from types import SimpleNamespace
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Scheduler as TCS
import O4_Texture_Encoder as TEX
from O4_Texture_Source import TextureSource


class FakeUI:
    def __init__(self):
        self.red_flag = False
        self.progress = []

    def progress_bar(self, bar, value):
        self.progress.append((bar, value))


def _tile():
    return SimpleNamespace(lat=12, lon=-123)


def _queue(*provider_codes):
    items = queue.Queue()
    for index, provider_code in enumerate(provider_codes):
        items.put((_tile(), 32 + index * 16, 48, 16, provider_code))
    items.put("quit")
    return items


def _fast_options():
    return TCS.TextureConversionSchedulerOptions(poll_interval=0.001)


class _ProviderFailureConverter:
    def __init__(self, failed_provider):
        self.failed_provider = failed_provider

    def __call__(self, *args):
        provider_code = args[4]
        if provider_code == self.failed_provider:
            return TEX.TextureConversionResult.failure(
                "bad.dds",
                provider_code,
                "encoder failed",
            )
        return TEX.TextureConversionResult.success("ok.dds", provider_code)


class TextureConversionSchedulerFailureTests(unittest.TestCase):
    def test_conversion_job_from_streaming_source_item(self):
        tile = object()
        source = TextureSource(tile, (32, 48, 16, "BI"), Image.new("RGB", (4, 4)))

        job = TCS.TextureConversionJob.from_queue_item((tile, source))

        self.assertIs(job.tile, tile)
        self.assertIs(job.source, source)
        self.assertEqual(job.til_x_left, 32)
        self.assertEqual(job.til_y_top, 48)
        self.assertEqual(job.zoomlevel, 16)
        self.assertEqual(job.provider_code, "BI")

    def test_conversion_job_from_legacy_tuple_has_no_source(self):
        tile = object()

        job = TCS.TextureConversionJob.from_queue_item((tile, 32, 48, 16, "BI"))

        self.assertIsNone(job.source)
        self.assertEqual(job.provider_code, "BI")

    def test_scheduler_aggregates_failed_jobs(self):
        ui = FakeUI()

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("OK", "BAD"),
                2,
                convert_texture=_ProviderFailureConverter("BAD"),
                options=_fast_options(),
            )

        self.assertEqual(result.completed, 2)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.failures[0].display_name, "bad.dds")
        self.assertEqual(result.failures[0].provider_code, "BAD")
        self.assertEqual(result.failures[0].error_summary, "encoder failed")

    def test_scheduler_coerces_false_conversion_result_to_failure(self):
        ui = FakeUI()
        convert_texture = mock.Mock(return_value=False)

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("BI"),
                1,
                convert_texture=convert_texture,
                options=_fast_options(),
            )

        self.assertEqual(result.completed, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.failures[0].provider_code, "BI")
        self.assertEqual(result.failures[0].error_summary, "conversion returned False")

    def test_scheduler_converts_exceptions_to_failures(self):
        ui = FakeUI()
        convert_texture = mock.Mock(side_effect=RuntimeError("boom"))

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("BI"),
                1,
                convert_texture=convert_texture,
                options=_fast_options(),
            )

        self.assertEqual(result.completed, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.failures[0].provider_code, "BI")
        self.assertIn("boom", result.failures[0].error_summary)

    def test_scheduler_respects_red_flag_before_scheduling(self):
        ui = FakeUI()
        ui.red_flag = True
        convert_texture = mock.Mock()

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("BI"),
                1,
                convert_texture=convert_texture,
                options=_fast_options(),
            )

        self.assertEqual(result.completed, 0)
        self.assertEqual(result.failed, 0)
        self.assertTrue(result.interrupted)
        convert_texture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
