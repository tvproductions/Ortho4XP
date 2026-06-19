import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Cfg_Vars import (
    cfg_global_tile_vars,
    cfg_tile_vars,
    cfg_vars,
    list_global_tile_vars,
    list_tile_vars,
)
from O4_Config_Models import coerce_config_value


class DdsQualityConfigTests(unittest.TestCase):
    def test_dds_qa_settings_are_opt_in_tile_settings(self):
        enabled = cfg_tile_vars["dds_qa_enabled"]
        threshold = cfg_tile_vars["dds_qa_psnr_threshold"]

        self.assertIs(enabled["type"], bool)
        self.assertIs(enabled["default"], False)
        self.assertIs(threshold["type"], float)
        self.assertEqual(threshold["default"], 30.0)
        for key in ("dds_qa_enabled", "dds_qa_psnr_threshold"):
            with self.subTest(key=key):
                self.assertIn(key, cfg_vars)
                self.assertIn(key, list_tile_vars)
                self.assertIn(f"global_{key}", cfg_global_tile_vars)
                self.assertIn(f"global_{key}", list_global_tile_vars)
        self.assertIs(coerce_config_value("dds_qa_enabled", "True", cfg_vars), True)
        self.assertEqual(
            coerce_config_value("dds_qa_psnr_threshold", "35.5", cfg_vars),
            35.5,
        )


if __name__ == "__main__":
    unittest.main()
