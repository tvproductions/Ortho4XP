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


def _fast_options():
    return TCS.TextureConversionSchedulerOptions(poll_interval=0.001)


class _WorkerLimitConverter:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def __call__(self, *args):
        provider_code = args[4]
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.02)
        with self.lock:
            self.active -= 1
        return TEX.TextureConversionResult.success(
            f"{provider_code}.dds",
            provider_code,
        )


class TextureConversionSchedulerLimitTests(unittest.TestCase):
    def test_scheduler_honors_worker_limit(self):
        ui = FakeUI()
        converter = _WorkerLimitConverter()

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("A", "B", "C", "D"),
                2,
                convert_texture=converter,
                options=_fast_options(),
            )

        self.assertEqual(result.completed, 4)
        self.assertEqual(result.failed, 0)
        self.assertFalse(result.interrupted)
        self.assertLessEqual(converter.max_active, 2)
        self.assertIn((3, 100), ui.progress)


if __name__ == "__main__":
    unittest.main()
