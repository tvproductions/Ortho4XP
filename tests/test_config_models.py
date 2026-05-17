from pathlib import Path
import re
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401
from O4_Cfg_Vars import cfg_vars
from O4_Config_Models import (
    UnsupportedWaterTechError,
    coerce_config_value,
    parse_legacy_config_literal,
    parse_legacy_zone_append,
    validate_config_registry,
)


class ConfigModelTests(unittest.TestCase):
    def test_config_registry_validates_with_pydantic(self):
        validate_config_registry(cfg_vars)

    def test_config_value_coercion_preserves_legacy_cfg_literals(self):
        self.assertIs(coerce_config_value("skip_downloads", "False", cfg_vars), False)
        self.assertEqual(coerce_config_value("default_zl", "17", cfg_vars), 17)
        self.assertEqual(coerce_config_value("ratio_water", "0.35", cfg_vars), 0.35)
        self.assertEqual(
            coerce_config_value("default_website", "'Arc'", cfg_vars), "Arc"
        )

    def test_list_typed_scalar_compatibility_is_preserved(self):
        self.assertEqual(coerce_config_value("masks_width", "100", cfg_vars), 100)
        self.assertEqual(
            coerce_config_value("masks_width", "[10, 20, 30]", cfg_vars),
            [10, 20, 30],
        )

    def test_zone_list_model_accepts_current_shape(self):
        zone_list = "[[[42, -71], 17, 'Arc']]"
        self.assertEqual(
            coerce_config_value("zone_list", zone_list, cfg_vars),
            [[[42, -71], 17, "Arc"]],
        )

    def test_legacy_zone_append_is_parsed_without_exec(self):
        self.assertEqual(
            parse_legacy_zone_append("zone_list.append([[42, -71], 17, 'Arc'])"),
            [[42, -71], 17, "Arc"],
        )

    def test_legacy_quotes_are_removed_once(self):
        self.assertEqual(parse_legacy_config_literal('"Arc"'), "Arc")

    def test_water_tech_is_fixed_to_xp12(self):
        self.assertEqual(cfg_vars["water_tech"]["default"], "XP12")
        self.assertEqual(cfg_vars["water_tech"]["values"], ("XP12",))
        self.assertEqual(coerce_config_value("water_tech", "XP12", cfg_vars), "XP12")

    def test_legacy_water_tech_values_are_rejected(self):
        for value in ("XP11", "XP11 + bathy"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    UnsupportedWaterTechError,
                    rf"{re.escape(f'water_tech={value!r}')}.*water_tech=XP12",
                ):
                    coerce_config_value("water_tech", value, cfg_vars)

    def test_legacy_water_tech_global_value_is_rejected(self):
        with self.assertRaisesRegex(
            UnsupportedWaterTechError,
            r"water_tech='XP11 \+ bathy'.*water_tech=XP12",
        ):
            coerce_config_value("global_water_tech", "XP11 + bathy", cfg_vars)

    def test_dsf_generation_has_no_legacy_water_tech_branch(self):
        dsf_source = Path("src/O4_DSF_Utils.py").read_text()
        self.assertNotIn("XP11 + bathy", dsf_source)


if __name__ == "__main__":
    unittest.main()
