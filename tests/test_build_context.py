import unittest
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Context as BC
import O4_UI_Utils as UI


class BuildContextPropertyTests(unittest.TestCase):
    def test_red_flag_reads_ui_module(self):
        with mock.patch.object(UI, "red_flag", False):
            ctx = BC.BuildContext()
            self.assertFalse(ctx.red_flag)

    def test_red_flag_writes_through_to_ui(self):
        with mock.patch.object(UI, "red_flag", False):
            ctx = BC.BuildContext()
            ctx.red_flag = True
            self.assertTrue(UI.red_flag)

    def test_red_flag_reflects_external_ui_write(self):
        with mock.patch.object(UI, "red_flag", False):
            ctx = BC.BuildContext()
            UI.red_flag = True
            self.assertTrue(ctx.red_flag)

    def test_is_working_reads_ui_module(self):
        with mock.patch.object(UI, "is_working", False):
            ctx = BC.BuildContext()
            self.assertFalse(ctx.is_working)

    def test_is_working_writes_through_to_ui(self):
        with mock.patch.object(UI, "is_working", False):
            ctx = BC.BuildContext()
            ctx.is_working = True
            self.assertTrue(UI.is_working)

    def test_verbosity_reads_ui_module(self):
        with mock.patch.object(UI, "verbosity", 2):
            ctx = BC.BuildContext()
            self.assertEqual(ctx.verbosity, 2)

    def test_verbosity_writes_through_to_ui(self):
        with mock.patch.object(UI, "verbosity", 1):
            ctx = BC.BuildContext()
            ctx.verbosity = 3
            self.assertEqual(UI.verbosity, 3)

    def test_cleaning_level_reads_ui_module(self):
        with mock.patch.object(UI, "cleaning_level", 1):
            ctx = BC.BuildContext()
            self.assertEqual(ctx.cleaning_level, 1)

    def test_cleaning_level_writes_through_to_ui(self):
        with mock.patch.object(UI, "cleaning_level", 1):
            ctx = BC.BuildContext()
            ctx.cleaning_level = 2
            self.assertEqual(UI.cleaning_level, 2)

    def test_gui_reads_ui_module(self):
        with mock.patch.object(UI, "gui", None):
            ctx = BC.BuildContext()
            self.assertIsNone(ctx.gui)

    def test_gui_writes_through_to_ui(self):
        sentinel = object()
        with mock.patch.object(UI, "gui", None):
            ctx = BC.BuildContext()
            ctx.gui = sentinel
            self.assertIs(UI.gui, sentinel)


class BuildContextVprintTests(unittest.TestCase):
    def test_vprint_delegates_to_ui_vprint(self):
        ctx = BC.BuildContext()
        with mock.patch.object(UI, "vprint") as vprint:
            ctx.vprint(1, "hello", "world")
        vprint.assert_called_once_with(1, "hello", "world")


if __name__ == "__main__":
    unittest.main()
