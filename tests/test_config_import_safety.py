import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class ConfigImportSafetyTests(unittest.TestCase):
    def setUp(self):
        self._orig_config_module = sys.modules.pop("O4_Config_Utils", None)

    def tearDown(self):
        sys.modules.pop("O4_Config_Utils", None)
        if self._orig_config_module is not None:
            sys.modules["O4_Config_Utils"] = self._orig_config_module

    def test_plain_import_does_not_read_config_file_or_mutate_globals(self):
        """Importing config utilities should not initialize runtime config."""
        import O4_Imagery_Utils as IMG
        import O4_UI_Utils as UI

        UI.verbosity = 99
        IMG.http_timeout = 999

        with mock.patch("builtins.open", side_effect=AssertionError("unexpected I/O")):
            import O4_Config_Utils as CFG

        self.assertNotIn("apt_smoothing_pix", CFG.__dict__)
        self.assertEqual(UI.verbosity, 99)
        self.assertEqual(IMG.http_timeout, 999)

    def test_explicit_initializer_applies_defaults_and_creates_missing_config(self):
        import O4_Imagery_Utils as IMG
        import O4_UI_Utils as UI
        import O4_Config_Utils as CFG

        UI.verbosity = 99
        IMG.http_timeout = 999

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir, "Ortho4XP.cfg")
            with mock.patch.object(CFG, "global_cfg_file", str(config_path)):
                CFG.initialize_global_config(force=True)

            self.assertTrue(config_path.exists())

        self.assertIn("apt_smoothing_pix", CFG.__dict__)
        self.assertEqual(UI.verbosity, 1)
        self.assertEqual(IMG.http_timeout, 10)


if __name__ == "__main__":
    unittest.main()
