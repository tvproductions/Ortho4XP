import contextlib
import importlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

import _path


class StartupSmokeTests(unittest.TestCase):
    def test_cli_help_exits_before_runtime_setup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [sys.executable, str(_path.ROOT_DIR / "Ortho4XP.py"), "--help"],
                cwd=temp_dir,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("USAGE: Ortho4XP.py", result.stdout)
            self.assertEqual(os.listdir(temp_dir), [])

    def test_core_modules_import_in_test_context(self):
        for module_name in ("O4_File_Names", "O4_Geo_Utils", "O4_Imagery_Utils"):
            with self.subTest(module=module_name):
                with contextlib.redirect_stdout(io.StringIO()):
                    module = importlib.import_module(module_name)
                self.assertIsNotNone(module)

    def test_custom_url_provider_module_loads_without_warning(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            imagery = importlib.import_module("O4_Imagery_Utils")

        self.assertTrue(imagery.has_URL)
        self.assertNotIn("O4_Custom_URL.py contains invalid code", stdout.getvalue())

    def test_provider_dictionaries_initialize(self):
        imagery = importlib.import_module("O4_Imagery_Utils")

        imagery.extents_dict.clear()
        imagery.color_filters_dict.clear()
        imagery.providers_dict.clear()
        imagery.combined_providers_dict.clear()

        with contextlib.redirect_stdout(io.StringIO()):
            imagery.initialize_extents_dict()
            imagery.initialize_color_filters_dict()
            imagery.initialize_providers_dict()
            imagery.initialize_combined_providers_dict()

        self.assertIn("Arc", imagery.providers_dict)
        self.assertGreater(len(imagery.providers_dict), 0)
        self.assertGreater(len(imagery.extents_dict), 0)
        self.assertGreater(len(imagery.color_filters_dict), 0)

    def test_required_source_resource_directories_exist(self):
        names = importlib.import_module("O4_File_Names")

        required_dirs = (
            names.Utils_dir,
            names.Provider_dir,
            names.Extent_dir,
            names.Filter_dir,
            names.Patch_dir,
        )

        for directory in required_dirs:
            with self.subTest(directory=directory):
                self.assertTrue(os.path.isdir(directory), directory)


if __name__ == "__main__":
    unittest.main()
