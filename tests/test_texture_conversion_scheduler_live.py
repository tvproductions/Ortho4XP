import queue
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

# Live-queue tests cover producer/consumer timing that ordinary static queues miss.
# The scenario records progress snapshots without depending on scheduler internals.

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Scheduler as TCS
import O4_Texture_Encoder as TEX


def _tile():
    return SimpleNamespace(lat=12, lon=-123)


def _fast_options():
    return TCS.TextureConversionSchedulerOptions(poll_interval=0.001)


class _RecordingProgressUI:
    def __init__(self, scenario):
        self.red_flag = False
        self.progress = []
        self.scenario = scenario

    def progress_bar(self, bar, value):
        self.progress.append((bar, value, self.scenario.completed_count()))


class _LiveQueueScenario:
    def __init__(self):
        self.lock = threading.Lock()
        self.completed_codes = []
        self.errors = []
        self.calls = []
        self.first_started = threading.Event()
        self.second_queued = threading.Event()
        self.convert_queue = queue.Queue()

    def start_producer(self):
        producer_thread = threading.Thread(target=self._produce)
        producer_thread.start()
        return producer_thread

    def _produce(self):
        self.convert_queue.put((_tile(), 32, 48, 16, "FIRST"))
        if not self.first_started.wait(timeout=1):
            self.errors.append("first texture conversion did not start")
            self.convert_queue.put("quit")
            return
        self.convert_queue.put((_tile(), 48, 48, 16, "SECOND"))
        self.second_queued.set()
        self._wait_for_completed_textures(1)
        self.convert_queue.put("quit")

    def _wait_for_completed_textures(self, expected_count):
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            if self.completed_count() >= expected_count:
                return
            time.sleep(0.001)
        self.errors.append("first texture conversion did not complete")

    def completed_count(self):
        with self.lock:
            return len(self.completed_codes)

    def convert_texture(self, *args, texture_source=None):
        self.calls.append((args, texture_source))
        provider_code = texture_source.provider_code if texture_source else args[4]
        if provider_code == "FIRST":
            self.first_started.set()
            if not self.second_queued.wait(timeout=1):
                self.errors.append("second texture was not queued")
        with self.lock:
            self.completed_codes.append(provider_code)
        return TEX.TextureConversionResult.success(
            f"{provider_code}.dds",
            provider_code,
        )


class TextureConversionSchedulerLiveTests(unittest.TestCase):
    def test_scheduler_does_not_report_complete_while_live_work_is_queued(self):
        scenario = _LiveQueueScenario()
        producer_thread = scenario.start_producer()
        ui = _RecordingProgressUI(scenario)
        try:
            with mock.patch.object(TCS, "UI", ui):
                result = TCS.run_texture_conversion_queue(
                    scenario.convert_queue,
                    1,
                    convert_texture=scenario.convert_texture,
                    options=_fast_options(),
                )
        finally:
            producer_thread.join(timeout=1)

        self.assertEqual(scenario.errors, [])
        self.assertEqual(result.completed, 2)
        self.assertEqual(scenario.completed_codes, ["FIRST", "SECOND"])
        premature_complete_events = [
            event for event in ui.progress if event[1] == 100 and event[2] < 2
        ]
        self.assertEqual(premature_complete_events, [])


if __name__ == "__main__":
    unittest.main()
