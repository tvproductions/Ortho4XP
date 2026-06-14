import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_External_Tool_Paths as PATHS
import O4_Subprocess_Runtime as RUNTIME
import O4_Subprocess_Utils as SP


class SubprocessUtilsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_log = SP.UI.log
        self.addCleanup(self._restore_ui_state)
        self.path_patch = mock.patch.object(
            SP.UI.FNAMES,
            "resource_path",
            side_effect=lambda relative: os.path.join(self.temp_dir.name, relative),
        )
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        SP.UI.log = True

    def _restore_ui_state(self):
        SP.UI.log = self.original_log

    def test_successful_command_captures_stdout(self):
        result = SP.run_external_tool(
            "python",
            ["-c", "print('ok')"],
            executable=sys.executable,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.error_summary, "")
        events = self._events()
        self.assertEqual(events[0]["message"], "External command start")
        self.assertEqual(events[0]["context"]["tool_name"], "python")
        self.assertEqual(events[1]["message"], "External command complete")
        self.assertTrue(events[1]["context"]["ok"])
        self.assertEqual(events[1]["context"]["returncode"], 0)

    def test_nonzero_command_captures_stderr_and_summary(self):
        with mock.patch.object(SP.UI, "lvprint"):
            result = SP.run_external_tool(
                "python",
                [
                    "-c",
                    "import sys; sys.stderr.write('bad news\\n'); raise SystemExit(3)",
                ],
                executable=sys.executable,
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stderr, "bad news\n")
        self.assertEqual(result.error_summary, "return code 3: bad news")
        complete_event = self._events()[1]
        self.assertEqual(complete_event["level"], "ERROR")
        self.assertEqual(complete_event["context"]["tool_name"], "python")
        self.assertEqual(complete_event["context"]["returncode"], 3)
        self.assertEqual(complete_event["error_type"], "ExternalCommandError")
        self.assertEqual(complete_event["error_summary"], "return code 3: bad news")

    def test_streamed_stdout_is_captured_and_printed(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            result = SP.run_external_tool(
                "python",
                ["-c", "print('one'); print('two')"],
                executable=sys.executable,
                stream_stdout=True,
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.stdout, "one\ntwo\n")
        self.assertEqual(stdout.getvalue(), "one\ntwo\n")

    def test_streamed_stdout_handler_receives_lines(self):
        streamed_lines = []

        result = SP.run_external_tool(
            "python",
            ["-c", "print('alpha'); print('beta')"],
            executable=sys.executable,
            stream_stdout=True,
            stdout_handler=streamed_lines.append,
        )

        self.assertTrue(result.ok)
        self.assertEqual(streamed_lines, ["alpha", "beta"])
        self.assertEqual(result.stdout, "alpha\nbeta\n")

    def test_macos_environment_is_applied_to_captured_commands(self):
        completed = subprocess.CompletedProcess(
            args=["example"],
            returncode=0,
            stdout="",
            stderr="",
        )

        with (
            mock.patch.object(SP.UI.sys, "platform", "darwin"),
            mock.patch.object(
                RUNTIME.subprocess, "run", return_value=completed
            ) as run_mock,
        ):
            result = SP.run_external_tool("example", executable="example")

        self.assertTrue(result.ok)
        self.assertEqual(
            run_mock.call_args.kwargs["env"]["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"],
            "YES",
        )

    def test_resolve_tool_uses_platform_specific_paths(self):
        with mock.patch.object(
            PATHS.FNAMES, "Utils_dir", os.path.join("root", "Utils")
        ):
            with mock.patch.object(PATHS.sys, "platform", "win32"):
                self.assertEqual(
                    SP.resolve_tool("Triangle4XP"),
                    os.path.join("root", "Utils", "win", "Triangle4XP.exe"),
                )
                self.assertEqual(SP.resolve_tool("gdalwarp"), "gdalwarp")

            with (
                mock.patch.object(PATHS.sys, "platform", "darwin"),
                mock.patch.object(PATHS.os.path, "exists", return_value=True),
            ):
                self.assertEqual(
                    SP.resolve_tool("nvcompress"),
                    os.path.join("root", "Utils", "mac", "DDSTool"),
                )
                self.assertEqual(
                    SP.resolve_tool("7z"),
                    os.path.join("root", "Utils", "mac", "7zz"),
                )

            with mock.patch.object(PATHS.sys, "platform", "linux"):
                self.assertEqual(
                    SP.resolve_tool("DSFTool"),
                    os.path.join("root", "Utils", "lin", "DSFTool"),
                )
                self.assertEqual(SP.resolve_tool("7z"), "7z")

    def _events(self):
        with open(SP.UI.log_path(), encoding="utf-8") as f:
            return [json.loads(line) for line in f]


if __name__ == "__main__":
    unittest.main()
