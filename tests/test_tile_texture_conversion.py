import unittest
import queue
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

# Tile conversion tests cover the Step 3 integration boundary:
# summary reporting, scheduler thread shutdown, and DSF activation failure.
# External DSF, download, filesystem, and conversion work are patched out.
# The assertions stay at the user-visible lifecycle rather than thread internals.
# This keeps the tests stable while conversion backends evolve.

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Scheduler as TCS
import O4_Texture_Encoder as TEX
import O4_Tile_Texture_Conversion as TTC
import O4_Tile_Utils as TILE


def _tile():
    return SimpleNamespace(
        lat=12,
        lon=-123,
        build_dir="build",
        grouped=False,
        write_to_config=mock.Mock(),
    )


def _build_tile_patches(tile, *, replace=None, vprint=None):
    stack = ExitStack()
    stack.enter_context(mock.patch.object(TILE.os.path, "isfile", return_value=True))
    stack.enter_context(mock.patch.object(TILE.os.path, "exists", return_value=True))
    stack.enter_context(mock.patch.object(TILE.os.path, "isdir", return_value=True))
    stack.enter_context(mock.patch.object(TILE.shutil, "rmtree"))
    stack.enter_context(
        mock.patch.object(
            TILE.IMG,
            "initialize_local_combined_providers_dict",
            return_value=True,
        )
    )
    stack.enter_context(mock.patch.object(TILE.DSF, "build_dsf"))
    stack.enter_context(mock.patch.object(TILE, "download_textures"))
    stack.enter_context(mock.patch.object(TILE.os, "replace", replace or mock.Mock()))
    stack.enter_context(mock.patch.object(TILE.UI, "is_working", 0))
    stack.enter_context(mock.patch.object(TILE.UI, "red_flag", False))
    stack.enter_context(mock.patch.object(TILE.UI, "cleaning_level", 0))
    stack.enter_context(mock.patch.object(TILE.UI, "vprint", vprint or mock.Mock()))
    stack.enter_context(mock.patch.object(TILE.UI, "lvprint"))
    stack.enter_context(mock.patch.object(TILE.UI, "logprint"))
    stack.enter_context(mock.patch.object(TILE.UI, "exit_message_and_bottom_line"))
    stack.enter_context(mock.patch.object(TILE.UI, "timings_and_bottom_line"))
    tile.grouped = True
    return stack


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
            TTC.report_texture_conversion_result(_tile(), result)

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
            TTC.report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(1, " *DDS conversion of textures completed.")

    def test_reports_interrupted_conversion(self):
        result = TCS.TextureConversionBatchResult(
            completed=0,
            failed=0,
            interrupted=True,
            failures=(),
        )

        with mock.patch.object(TILE.UI, "vprint") as vprint:
            TTC.report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(1, "DDS conversion process interrupted.")


class TileTextureConversionSchedulerIntegrationTests(unittest.TestCase):
    def test_build_tile_sends_one_quit_joins_scheduler_and_reports_result(self):
        tile = _tile()
        queues = [_RecordingQueue(), _RecordingQueue()]
        result = TCS.TextureConversionBatchResult(
            completed=1,
            failed=0,
            interrupted=False,
            failures=(),
        )
        consumed_sentinels = []
        scheduler_queues = []

        queue_factory_calls = [0]

        def queue_factory():
            queue_factory_calls[0] += 1
            return queues[queue_factory_calls[0] - 1]

        def run_scheduler(convert_queue, _max_workers, *, convert_texture):
            scheduler_queues.append(convert_queue)
            consumed_sentinels.append(convert_queue.get(timeout=1))
            return result

        vprint = mock.Mock()
        with _build_tile_patches(tile, vprint=vprint):
            with (
                mock.patch.object(TILE.queue, "Queue", side_effect=queue_factory),
                mock.patch.object(
                    TTC.TCS,
                    "run_texture_conversion_queue",
                    side_effect=run_scheduler,
                ),
            ):
                self.assertEqual(TILE.build_tile(tile), 1)

        convert_queue = queues[1]
        self.assertIs(scheduler_queues[0], convert_queue)
        self.assertEqual(convert_queue.put_calls, ["quit"])
        self.assertEqual(consumed_sentinels, ["quit"])
        vprint.assert_any_call(1, " *DDS conversion of textures completed.")

    def test_scheduler_failure_aborts_before_dsf_activation(self):
        tile = _tile()
        replace = mock.Mock()
        vprint = mock.Mock()

        with _build_tile_patches(tile, replace=replace, vprint=vprint):
            with mock.patch.object(
                TTC.TCS,
                "run_texture_conversion_queue",
                side_effect=RuntimeError("scheduler failed"),
            ):
                self.assertEqual(TILE.build_tile(tile), 0)

        replace.assert_not_called()
        vprint.assert_any_call(
            1,
            "DDS conversion scheduler failed:",
            "RuntimeError: scheduler failed",
        )

    def test_scheduler_exception_is_reported_without_key_error(self):
        original_error = RuntimeError("scheduler failed")
        result_holder = {}

        with mock.patch.object(
            TTC.TCS,
            "run_texture_conversion_queue",
            side_effect=original_error,
        ):
            TTC.run_texture_conversion_scheduler(
                _RecordingQueue(),
                result_holder,
                max_convert_slots=4,
            )

        self.assertIs(result_holder["exception"], original_error)
        with (
            mock.patch.object(TILE.UI, "vprint") as vprint,
            mock.patch.object(TILE.UI, "red_flag", False),
        ):
            TTC.handle_texture_conversion_scheduler_result(_tile(), result_holder)
            self.assertTrue(TILE.UI.red_flag)

        vprint.assert_any_call(
            1,
            "DDS conversion scheduler failed:",
            "RuntimeError: scheduler failed",
        )


if __name__ == "__main__":
    unittest.main()
