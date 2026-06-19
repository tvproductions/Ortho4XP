"""Regression tests for config schema and TODO-014 water-tech boundaries.

Several assertions intentionally inspect source text because they guard removal
of legacy water-tech branches and prevent bathymetry input from drifting back
into mask-derived data paths.
"""

import re
import unittest
from pathlib import Path
from typing import cast

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401
from O4_Cfg_Vars import (
    cfg_app_vars,
    cfg_global_tile_vars,
    cfg_tile_vars,
    cfg_vars,
    list_app_vars,
    list_global_tile_vars,
    list_tile_vars,
)
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

    def test_texture_color_normalization_is_opt_in_img_setting(self):
        definition = cfg_vars["normalize_texture_colors"]

        self.assertEqual(definition["module"], "IMG")
        self.assertIs(definition["type"], bool)
        self.assertIs(definition["default"], False)
        self.assertIn("normalize_texture_colors", list_app_vars)
        self.assertIs(
            coerce_config_value("normalize_texture_colors", "True", cfg_vars),
            True,
        )

    def test_resampling_policy_keys_are_tile_and_global_tile_settings(self):
        expected = {
            "texture_resize_resampling": "lanczos",
            "mask_resize_resampling": "nearest",
            "warp_resampling": "bicubic",
            "normalization_resampling": "bilinear",
            "dem_resampling": "bicubic",
            "airport_smoothing_resampling": "bicubic",
        }

        for key, default in expected.items():
            with self.subTest(key=key):
                definition = cfg_tile_vars[key]
                global_key = f"global_{key}"

                self.assertIs(definition["type"], str)
                self.assertEqual(definition["default"], default)
                self.assertEqual(
                    definition["values"],
                    ("nearest", "bilinear", "bicubic", "lanczos"),
                )
                hint = cast(str, definition["hint"])
                self.assertIsInstance(hint, str)
                self.assertIn("resampling", hint.lower())
                self.assertIn(key, cfg_vars)
                self.assertIn(key, list_tile_vars)
                self.assertIn(global_key, cfg_global_tile_vars)
                self.assertIn(global_key, list_global_tile_vars)

    def test_resampling_policy_keys_validate_allowed_values(self):
        for key in (
            "texture_resize_resampling",
            "mask_resize_resampling",
            "warp_resampling",
            "normalization_resampling",
            "dem_resampling",
            "airport_smoothing_resampling",
        ):
            for method in ("nearest", "bilinear", "bicubic", "lanczos"):
                with self.subTest(key=key, method=method):
                    self.assertEqual(coerce_config_value(key, method, cfg_vars), method)

            with (
                self.subTest(key=key, method="average"),
                self.assertRaisesRegex(ValueError, key),
            ):
                coerce_config_value(key, "average", cfg_vars)

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
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(
                    UnsupportedWaterTechError,
                    rf"{re.escape(f'water_tech={value!r}')}.*water_tech=XP12",
                ),
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

    def test_dsf_generation_uses_bathymetry_input_boundary(self):
        dsf_source = Path("src/O4_DSF_Utils.py").read_text()
        bathy_input_source = Path("src/O4_Bathymetry_Input.py").read_text()
        self.assertIn("extract_elevation_and_bathymetry_data", dsf_source)
        self.assertIn("extract_required_bathymetry_rasters", dsf_source)
        self.assertIn("mesh_requires_bathymetry", dsf_source)
        self.assertIn("O4_Bathymetry_Input", dsf_source)
        self.assertIn("GlobalSceneryRasterSource", bathy_input_source)

    def test_bathymetry_input_is_extracted_before_dsf_backup(self):
        dsf_source = Path("src/O4_DSF_Utils.py").read_text()
        extraction = (
            "(bDEMN, bDEMS) = extract_required_bathymetry_rasters(tile, tri_types)"
        )
        backup = 'os.replace(dsf_file_name, dsf_file_name + ".bak")'

        self.assertEqual(dsf_source.count(extraction), 1)
        self.assertLess(dsf_source.index(extraction), dsf_source.index(backup))
        self.assertIn("extract_validated_global_scenery_rasters", dsf_source)

    def test_all_land_bathymetry_rasters_are_empty_before_water_gate(self):
        dsf_source = Path("src/O4_DSF_Utils.py").read_text()
        water_gate = "if not mesh_requires_bathymetry(tri_types):"
        extraction = "extract_elevation_and_bathymetry_data(tile.lat, tile.lon)"

        self.assertLess(
            dsf_source.index("return XP12_EMPTY_BATHYMETRY_RASTERS"),
            dsf_source.index(extraction),
        )
        self.assertLess(dsf_source.index(water_gate), dsf_source.index(extraction))

    def test_masks_are_not_treated_as_bathymetry_source(self):
        bathy_source = "\n".join(
            Path("src", filename).read_text()
            for filename in (
                "O4_Bathymetry_DSF_Atoms.py",
                "O4_Bathymetry_DSF_Bytes.py",
                "O4_Bathymetry_Input.py",
                "O4_Bathymetry_Models.py",
                "O4_Bathymetry_Raster_Parser.py",
                "O4_Bathymetry_Source.py",
            )
        )
        self.assertNotIn("distance_masks_too", bathy_source)
        self.assertNotIn("ratio_bathy", bathy_source)
        self.assertNotIn("node_bathy", bathy_source)

    def test_package_naming_config_keys_have_valid_definitions(self):
        from O4_Config_Models import ConfigVariableDefinition

        for key in (
            "package_prefix",
            "package_separator",
            "mesh_purpose_token",
            "overlay_purpose_token",
            "monolithic_overlay_name",
            "latlon_format",
            "per_tile_overlays",
        ):
            definition = cfg_app_vars[key]
            ConfigVariableDefinition.model_validate(definition)

    def test_package_naming_config_defaults(self):
        prefix = cfg_app_vars["package_prefix"]["default"]
        self.assertEqual(prefix, "Ortho4XP")
        sep = cfg_app_vars["package_separator"]["default"]
        self.assertEqual(sep, "_")
        mesh = cfg_app_vars["mesh_purpose_token"]["default"]
        self.assertEqual(mesh, "Mesh")
        overlay = cfg_app_vars["overlay_purpose_token"]["default"]
        self.assertEqual(overlay, "Overlay")
        mononame = cfg_app_vars["monolithic_overlay_name"]["default"]
        self.assertEqual(mononame, "Overlays")
        latlon = cfg_app_vars["latlon_format"]["default"]
        self.assertEqual(latlon, "short")
        per_tile = cfg_app_vars["per_tile_overlays"]["default"]
        self.assertEqual(per_tile, False)


if __name__ == "__main__":
    unittest.main()
