import unittest
import queue
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Scheduler as TCS
import O4_Texture_Encoder as TEX
import O4_Tile_Utils as TILE


def _tile():
    return SimpleNamespace(
        lat=12,
        lon=-123,
        build_dir="build",
        grouped=False,
        write_to_config=mock.Mock(),
    )


class _RecordingQueue(queue.Queue):
    def __init__(self):
        super().__init__()
        self.put_calls = []

    def put(self, item, *args, **kwargs):
        self.put_calls.append(item)
        return super().put(item, *args, **kwargs)


class TileTextureConversionSummaryTests(unittest.TestCase):
    def test_reports_failed_conversion_providers(self):
        result = TCS.TextureConversionBatchResult(
            completed=3,
            failed=2,
            interrupted=False,
            failures=(
                TEX.TextureConversionResult.failure("a.dds", "BI", "bad"),
                TEX.TextureConversionResult.failure("b.dds", "GO2", "bad"),
            ),
        )

        with mock.patch.object(TILE.UI, "vprint") as vprint:
            TILE._report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(
            1,
            "DDS conversion summary:",
            "2 failed texture(s)",
            "for tile +12-123.",
            "Providers: BI=1, GO2=1.",
        )

    def test_reports_successful_conversion_completion(self):
        result = TCS.TextureConversionBatchResult(
            completed=2,
            failed=0,
            interrupted=False,
            failures=(),
        )

        with mock.patch.object(TILE.UI, "vprint") as vprint:
            TILE._report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(1, " *DDS conversion of textures completed.")

    def test_reports_interrupted_conversion(self):
        result = TCS.TextureConversionBatchResult(
            completed=0,
            failed=0,
            interrupted=True,
            failures=(),
        )

        with mock.patch.object(TILE.UI, "vprint") as vprint:
            TILE._report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(1, "DDS conversion process interrupted.")


class TileTextureConversionSchedulerIntegrationTests(unittest.TestCase):
    def test_build_tile_sends_one_quit_joins_scheduler_and_reports_result(self):
        tile = _tile()
        download_queue = _RecordingQueue()
        convert_queue = _RecordingQueue()
        result = TCS.TextureConversionBatchResult(
            completed=1,
            failed=0,
            interrupted=False,
            failures=(),
        )
        scheduler_joined = []

        class FakeThread:
            def __init__(self, target, args):
                self.target = target
                self.args = args

            def start(self):
                pass

            def join(self):
                if self.target is TILE._run_texture_conversion_scheduler:
                    scheduler_joined.append(list(convert_queue.put_calls))
                    self.args[1]["result"] = result

        queue_factory_calls = [0]

        def queue_factory():
            queue_factory_calls[0] += 1
            return download_queue if queue_factory_calls[0] == 1 else convert_queue

        with (
            mock.patch.object(TILE.os.path, "isfile", return_value=True),
            mock.patch.object(TILE.os.path, "exists", return_value=True),
            mock.patch.object(TILE.os.path, "isdir", return_value=True),
            mock.patch.object(TILE.IMG, "initialize_local_combined_providers_dict", return_value=True),
            mock.patch.object(TILE.threading, "Thread", side_effect=FakeThread),
            mock.patch.object(TILE.queue, "Queue", side_effect=queue_factory),
            mock.patch.object(TILE.os, "replace"),
            mock.patch.object(TILE.UI, "is_working", 0),
            mock.patch.object(TILE.UI, "red_flag", False),
            mock.patch.object(TILE.UI, "cleaning_level", 0),
            mock.patch.object(TILE.UI, "vprint") as vprint,
            mock.patch.object(TILE.UI, "logprint"),
            mock.patch.object(TILE.UI, "timings_and_bottom_line"),
        ):
            self.assertEqual(TILE.build_tile(tile), 1)

        self.assertEqual(convert_queue.put_calls, ["quit"])
        self.assertEqual(scheduler_joined, [["quit"]])
        vprint.assert_any_call(1, " *DDS conversion of textures completed.")

    def test_scheduler_exception_is_reported_without_key_error(self):
        original_error = RuntimeError("scheduler failed")
        result_holder = {}

        with mock.patch.object(
            TILE.TCS,
            "run_texture_conversion_queue",
            side_effect=original_error,
        ):
            TILE._run_texture_conversion_scheduler(_RecordingQueue(), result_holder)

        self.assertIs(result_holder["exception"], original_error)
        with (
            mock.patch.object(TILE.UI, "vprint") as vprint,
            mock.patch.object(TILE.UI, "red_flag", False),
        ):
            TILE._handle_texture_conversion_scheduler_result(_tile(), result_holder)
            self.assertTrue(TILE.UI.red_flag)

        vprint.assert_any_call(
            1,
            "DDS conversion scheduler failed:",
            "scheduler failed",
        )


if __name__ == "__main__":
    unittest.main()
