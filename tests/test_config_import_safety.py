import os
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class ConfigImportSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_env = os.environ.get("ORTHO4XP_SKIP_CONFIG_INIT")
        os.environ["ORTHO4XP_SKIP_CONFIG_INIT"] = "1"
        try:
            import O4_UI_Utils as UI
            import O4_Imagery_Utils as IMG

            UI.verbosity = 99
            IMG.http_timeout = 999

            import O4_Config_Utils as CFG  # noqa: F401

            cls.UI = UI
            cls.IMG = IMG
            cls._cfg = CFG
        finally:
            if cls._orig_env is None:
                del os.environ["ORTHO4XP_SKIP_CONFIG_INIT"]
            else:
                os.environ["ORTHO4XP_SKIP_CONFIG_INIT"] = cls._orig_env

    def test_import_does_not_read_config_file(self):
        """Importing with skip flag should not read Ortho4XP.cfg."""
        pass

    def test_import_does_not_mutate_ui_globals(self):
        """Importing with skip flag should not set UI.verbosity etc."""
        self.assertEqual(self.UI.verbosity, 99)

    def test_import_does_not_mutate_img_globals(self):
        """Importing with skip flag should not set IMG.http_timeout etc."""
        self.assertEqual(self.IMG.http_timeout, 999)


if __name__ == "__main__":
    unittest.main()
