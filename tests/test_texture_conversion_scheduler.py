import queue
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Scheduler as TCS
import O4_Texture_Encoder as TEX


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


class TextureConversionSchedulerTests(unittest.TestCase):
    def test_scheduler_honors_worker_limit(self):
        ui = FakeUI()
        active = 0
        max_active = 0
        lock = threading.Lock()

        def convert_texture(tile, til_x_left, til_y_top, zoomlevel, provider_code):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return TEX.TextureConversionResult.success(
                f"{provider_code}.dds",
                provider_code,
            )

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("A", "B", "C", "D"),
                2,
                convert_texture=convert_texture,
                poll_interval=0.001,
            )

        self.assertEqual(result.completed, 4)
        self.assertEqual(result.failed, 0)
        self.assertFalse(result.interrupted)
        self.assertLessEqual(max_active, 2)
        self.assertIn((3, 100), ui.progress)

    def test_scheduler_aggregates_failed_jobs(self):
        ui = FakeUI()

        def convert_texture(tile, til_x_left, til_y_top, zoomlevel, provider_code):
            if provider_code == "BAD":
                return TEX.TextureConversionResult.failure(
                    "bad.dds",
                    provider_code,
                    "encoder failed",
                )
            return TEX.TextureConversionResult.success("ok.dds", provider_code)

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("OK", "BAD"),
                2,
                convert_texture=convert_texture,
                poll_interval=0.001,
            )

        self.assertEqual(result.completed, 2)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.failures[0].display_name, "bad.dds")
        self.assertEqual(result.failures[0].provider_code, "BAD")
        self.assertEqual(result.failures[0].error_summary, "encoder failed")

    def test_scheduler_converts_exceptions_to_failures(self):
        ui = FakeUI()

        def convert_texture(tile, til_x_left, til_y_top, zoomlevel, provider_code):
            raise RuntimeError("boom")

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("BI"),
                1,
                convert_texture=convert_texture,
                poll_interval=0.001,
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
                poll_interval=0.001,
            )

        self.assertEqual(result.completed, 0)
        self.assertEqual(result.failed, 0)
        self.assertTrue(result.interrupted)
        convert_texture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
