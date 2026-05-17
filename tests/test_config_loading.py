import tempfile
import unittest
from pathlib import Path

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401
import O4_Config_Utils as CFG
from O4_Config_Models import UnsupportedWaterTechError


class ConfigLoadingTests(unittest.TestCase):
    def test_tile_config_load_rejects_legacy_water_tech(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "Ortho4XP_+00+000.cfg"
            config_file.write_text("water_tech=XP11 + bathy\n")

            tile = CFG.Tile(0, 0, "")

            self.assertEqual(tile.read_from_config(str(config_file)), 0)
            self.assertEqual(getattr(tile, "water_tech"), "XP12")

    def test_tile_config_load_accepts_xp12_water_tech(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "Ortho4XP_+00+000.cfg"
            config_file.write_text("water_tech=XP12\n")

            tile = CFG.Tile(0, 0, "")

            self.assertEqual(tile.read_from_config(str(config_file)), 1)
            self.assertEqual(getattr(tile, "water_tech"), "XP12")

    def test_global_config_assignment_rejects_legacy_water_tech(self):
        with self.assertRaisesRegex(
            UnsupportedWaterTechError,
            r"water_tech='XP11'.*water_tech=XP12",
        ):
            CFG.set_global_variables("water_tech", "XP11")

    def test_global_tile_config_assignment_rejects_legacy_water_tech(self):
        with self.assertRaisesRegex(
            UnsupportedWaterTechError,
            r"water_tech='XP11 \+ bathy'.*water_tech=XP12",
        ):
            CFG.set_global_variables("global_water_tech", "XP11 + bathy")


if __name__ == "__main__":
    unittest.main()
