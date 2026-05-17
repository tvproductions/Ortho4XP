import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import _path  # noqa: F401

import O4_UI_Utils as UI


class UiLoggingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_log = UI.log
        self.original_verbosity = UI.verbosity
        self.addCleanup(self._restore_ui_state)
        self.path_patch = mock.patch.object(
            UI.FNAMES,
            "resource_path",
            side_effect=lambda relative: os.path.join(self.temp_dir.name, relative),
        )
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        UI.log = True
        UI.verbosity = 1

    def _restore_ui_state(self):
        UI.log = self.original_log
        UI.verbosity = self.original_verbosity

    def test_logprint_writes_valid_jsonl_to_default_json_log(self):
        UI.logprint("hello", "world", 3)

        events = self._events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["level"], "INFO")
        self.assertEqual(events[0]["message"], "hello world 3")
        self.assertEqual(events[0]["args"], ["hello", "world", 3])
        self.assertEqual(events[0]["context"], {})
        self.assertEqual(events[0]["verbosity"], 1)
        self.assertIsNone(events[0]["error_type"])
        self.assertIsNone(events[0]["error_summary"])
        self.assertFalse(
            os.path.exists(os.path.join(self.temp_dir.name, "Ortho4XP.log"))
        )

    def test_vprint_is_human_output_only(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            UI.vprint(1, "visible")

        self.assertEqual(stdout.getvalue(), "visible\n")
        self.assertFalse(os.path.exists(UI.log_path()))

    def test_lvprint_logs_even_when_human_verbosity_suppresses_output(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            UI.lvprint(3, "structured", "only")

        self.assertEqual(stdout.getvalue(), "")
        events = self._events()
        self.assertEqual(events[0]["message"], "structured only")
        self.assertEqual(events[0]["verbosity"], 3)

    def test_logprint_is_file_only(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            UI.logprint("persistent")

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(self._events()[0]["message"], "persistent")

    def test_disabled_log_suppresses_persistent_events(self):
        UI.log = False

        UI.logprint("off")
        UI.lvprint(2, "also off")

        self.assertFalse(os.path.exists(UI.log_path()))

    def test_logging_write_errors_are_non_fatal(self):
        with mock.patch("builtins.open", side_effect=OSError("cannot write")):
            UI.logprint("still returns")

    def test_exception_logging_includes_structured_error_fields(self):
        try:
            raise ValueError("bad value")
        except ValueError:
            UI.log_exception("failed operation", "tile", context={"lat": 1})

        event = self._events()[0]
        self.assertEqual(event["level"], "ERROR")
        self.assertEqual(event["message"], "failed operation")
        self.assertEqual(event["args"], ["tile"])
        self.assertEqual(event["context"], {"lat": 1})
        self.assertEqual(event["error_type"], "ValueError")
        self.assertEqual(event["error_summary"], "bad value")
        self.assertIn("ValueError: bad value", event["traceback"])

    def test_bottom_line_helpers_route_through_json_log(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            UI.exit_message_and_bottom_line("done")

        self.assertEqual(self._events()[0]["message"], "done")
        self.assertIn(UI.BOTTOM_LINE, stdout.getvalue())

    def _events(self):
        with open(UI.log_path(), encoding="utf-8") as f:
            return [json.loads(line) for line in f]


if __name__ == "__main__":
    unittest.main()
