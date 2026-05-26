import contextlib
import io
import unittest
from types import SimpleNamespace

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_CLI_Utils as CLI


class CliBuildResultTests(unittest.TestCase):
    def test_build_result_messages_reports_success(self):
        result = SimpleNamespace(ok=True, message="")

        self.assertEqual(CLI.build_result_messages(result), ("Bon vol!",))

    def test_build_result_messages_reports_failure_message_before_crash(self):
        result = SimpleNamespace(ok=False, message="interrupted")

        self.assertEqual(CLI.build_result_messages(result), ("interrupted", "Crash!"))

    def test_build_result_messages_reports_empty_failure_as_crash_only(self):
        result = SimpleNamespace(ok=False, message="")

        self.assertEqual(CLI.build_result_messages(result), ("Crash!",))

    def test_print_build_result_writes_one_message_per_line(self):
        result = SimpleNamespace(ok=False, message="interrupted")
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            CLI.print_build_result(result)

        self.assertEqual(stdout.getvalue(), "interrupted\nCrash!\n")


if __name__ == "__main__":
    unittest.main()
