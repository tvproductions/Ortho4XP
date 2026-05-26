import contextlib
import io
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


def _module(name):
    return types.ModuleType(name)


def _fake_file_names(temp_dir):
    module = _module("O4_File_Names")
    for name in (
        "Preview_dir",
        "Provider_dir",
        "Extent_dir",
        "Filter_dir",
        "OSM_dir",
        "Mask_dir",
        "Imagery_dir",
        "Elevation_dir",
        "Geotiff_dir",
        "Patch_dir",
        "Tile_dir",
        "Tmp_dir",
        "Utils_dir",
    ):
        setattr(module, name, str(Path(temp_dir, name)))
    Path(module.Utils_dir).mkdir()
    return module


def _fake_imagery():
    module = _module("O4_Imagery_Utils")
    module.initialize_extents_dict = mock.Mock()
    module.initialize_color_filters_dict = mock.Mock()
    module.initialize_providers_dict = mock.Mock()
    module.initialize_combined_providers_dict = mock.Mock()
    return module


def _fake_config():
    module = _module("O4_Config_Utils")

    class FakeTile:
        def __init__(self, lat, lon, custom_build_dir):
            self.lat = lat
            self.lon = lon
            self.custom_build_dir = custom_build_dir

    module.Tile = FakeTile
    return module


def _legacy_step_module(module_name, function_name):
    module = _module(module_name)
    setattr(
        module,
        function_name,
        mock.Mock(side_effect=AssertionError(f"{function_name} should not be called")),
    )
    return module


def _fake_modules(temp_dir, *, build_result):
    fake_pyproj = _module("pyproj")
    fake_pyproj.datadir = SimpleNamespace(set_data_dir=mock.Mock())

    fake_core = _module("O4_Build_Core")
    fake_core.build_tile_all = mock.Mock(return_value=build_result)

    return {
        "pyproj": fake_pyproj,
        "O4_File_Names": _fake_file_names(temp_dir),
        "O4_Imagery_Utils": _fake_imagery(),
        "O4_Build_Core": fake_core,
        "O4_GUI_Utils": _module("O4_GUI_Utils"),
        "O4_Config_Utils": _fake_config(),
        "O4_Vector_Map": _legacy_step_module("O4_Vector_Map", "build_poly_file"),
        "O4_Mesh_Utils": _legacy_step_module("O4_Mesh_Utils", "build_mesh"),
        "O4_Mask_Utils": _legacy_step_module("O4_Mask_Utils", "build_masks"),
        "O4_Tile_Utils": _legacy_step_module("O4_Tile_Utils", "build_tile"),
    }


class LauncherCoreTests(unittest.TestCase):
    def test_cli_all_in_one_uses_core_api(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            modules = _fake_modules(
                temp_dir,
                build_result=SimpleNamespace(ok=True, message=""),
            )
            with (
                mock.patch.dict(sys.modules, modules),
                mock.patch.object(
                    sys,
                    "argv",
                    ["Ortho4XP.py", "12", "-123", "BI", "16"],
                ),
                mock.patch.object(sys, "path", list(sys.path)),
                contextlib.redirect_stdout(stdout),
            ):
                runpy.run_path(str(_path.ROOT_DIR / "Ortho4XP.py"), run_name="__main__")

        core = modules["O4_Build_Core"]
        core.build_tile_all.assert_called_once()
        tile = core.build_tile_all.call_args[0][0]
        self.assertEqual(tile.lat, 12)
        self.assertEqual(tile.lon, -123)
        self.assertEqual(tile.custom_build_dir, "")
        self.assertEqual(tile.default_website, "BI")
        self.assertEqual(tile.default_zl, 16)
        self.assertIn("Bon vol!", stdout.getvalue())
        modules["O4_Vector_Map"].build_poly_file.assert_not_called()
        modules["O4_Mesh_Utils"].build_mesh.assert_not_called()
        modules["O4_Mask_Utils"].build_masks.assert_not_called()
        modules["O4_Tile_Utils"].build_tile.assert_not_called()

    def test_cli_all_in_one_failure_prints_crash_without_bon_vol(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            modules = _fake_modules(
                temp_dir,
                build_result=SimpleNamespace(ok=False, message="interrupted"),
            )
            with (
                mock.patch.dict(sys.modules, modules),
                mock.patch.object(sys, "argv", ["Ortho4XP.py", "12", "-123"]),
                mock.patch.object(sys, "path", list(sys.path)),
                contextlib.redirect_stdout(stdout),
            ):
                runpy.run_path(str(_path.ROOT_DIR / "Ortho4XP.py"), run_name="__main__")

        output = stdout.getvalue()
        modules["O4_Build_Core"].build_tile_all.assert_called_once()
        self.assertIn("interrupted", output)
        self.assertIn("Crash!", output)
        self.assertNotIn("Bon vol!", output)


if __name__ == "__main__":
    unittest.main()
