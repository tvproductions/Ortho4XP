import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401
import O4_File_Names as names
import O4_Imagery_Utils as imagery


class ProviderParsingTests(unittest.TestCase):
    def test_initialize_providers_accepts_valid_json_and_skips_invalid_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider_root = Path(temp_dir)
            provider_dir = provider_root / "Test"
            provider_dir.mkdir()
            (provider_dir / "GOOD.lay.json").write_text(
                json.dumps(
                    {
                        "grid_type": "webmercator",
                        "fake_headers": {"User-Agent": imagery.user_agent_generic},
                        "in_GUI": False,
                    }
                ),
                encoding="utf-8",
            )
            (provider_dir / "BAD.lay.json").write_text(
                json.dumps(
                    {
                        "grid_type": "webmercator",
                        "fake_headers": {"X-Retry": 3},
                    }
                ),
                encoding="utf-8",
            )

            original_provider_dir = names.Provider_dir
            original_providers = imagery.providers_dict.copy()
            names.Provider_dir = str(provider_root)
            imagery.providers_dict.clear()
            try:
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    imagery.initialize_providers_dict()
                parsed_providers = imagery.providers_dict.copy()
            finally:
                names.Provider_dir = original_provider_dir
                imagery.providers_dict.clear()
                imagery.providers_dict.update(original_providers)

        self.assertIn("GOOD", parsed_providers)
        self.assertNotIn("BAD", parsed_providers)
        self.assertIs(parsed_providers["GOOD"]["in_GUI"], False)
        self.assertEqual(
            parsed_providers["GOOD"]["fake_headers"]["User-Agent"],
            imagery.user_agent_generic,
        )
        self.assertIn("provider BAD: error: fake_headers", stdout.getvalue())

    def test_provider_schema_rejects_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider_path = Path(temp_dir) / "BAD.lay.json"
            provider_path.write_text(
                json.dumps(
                    {
                        "grid_type": "webmercator",
                        "url_template": "https://example.test/{zoom}/{x}/{y}.jpg",
                        "surprise": "value",
                    }
                ),
                encoding="utf-8",
            )

            _, issues = imagery.parse_provider_definition("BAD", provider_path)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].field, "surprise")
        self.assertIn("Extra inputs are not permitted", issues[0].message)

    def test_provider_schema_rejects_legacy_color_filter_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider_path = Path(temp_dir) / "SEA.lay.json"
            provider_path.write_text(
                json.dumps(
                    {
                        "grid_type": "webmercator",
                        "url_template": "https://example.test/{zoom}/{x}/{y}.jpg",
                        "color_filter": "SEA",
                    }
                ),
                encoding="utf-8",
            )

            _, issues = imagery.parse_provider_definition("SEA", provider_path)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].field, "color_filter")

    def test_provider_schema_reports_invalid_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider_path = Path(temp_dir) / "BAD.lay.json"
            provider_path.write_text('{"grid_type": "webmercator",', encoding="utf-8")

            _, issues = imagery.parse_provider_definition("BAD", provider_path)

        self.assertEqual(len(issues), 1)
        self.assertIn(issues[0].field, {"json", "request_type"})
        self.assertIn("JSON", issues[0].message.upper())

    def test_provider_definition_normalizes_numeric_arrays(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider_path = Path(temp_dir) / "EST.lay.json"
            provider_path.write_text(
                json.dumps(
                    {
                        "request_type": "tms",
                        "epsg_code": 3301,
                        "top_left_corner": [-211000, 5732000],
                        "resolutions": [6000, 3000, 1500],
                        "tile_size": 256,
                        "url_template": "https://example.test/{zoom}/{x}/{y}.jpg",
                    }
                ),
                encoding="utf-8",
            )

            provider, issues = imagery.parse_provider_definition("EST", provider_path)

        self.assertEqual(issues, [])
        self.assertEqual(len(provider["top_left_corner"]), 40)
        self.assertTrue(isinstance(provider["top_left_corner"][0], numpy.ndarray))
        self.assertTrue(isinstance(provider["resolutions"], numpy.ndarray))

    def test_known_provider_definitions_validate_against_schema(self):
        original_filters = imagery.color_filters_dict.copy()
        try:
            imagery.color_filters_dict.clear()
            imagery.color_filters_dict["none"] = []
            imagery.initialize_color_filters_dict()

            issues = imagery.validate_provider_definitions()
        finally:
            imagery.color_filters_dict.clear()
            imagery.color_filters_dict.update(original_filters)

        self.assertEqual([str(issue) for issue in issues], [])

    def test_extent_definitions_use_double_extension_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            extent_root = Path(temp_dir)
            extent_dir = extent_root / "Test"
            extent_dir.mkdir()
            (extent_dir / "AREA.ext.json").write_text(
                json.dumps({"mask_bounds": [1.0, 2.0, 3.0, 4.0]}),
                encoding="utf-8",
            )
            (extent_dir / "BAD.ext.json").write_text(
                json.dumps({"unexpected": True}),
                encoding="utf-8",
            )

            original_extent_dir = names.Extent_dir
            original_extents = imagery.extents_dict.copy()
            names.Extent_dir = str(extent_root)
            imagery.extents_dict.clear()
            try:
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    imagery.initialize_extents_dict()
                parsed_extents = imagery.extents_dict.copy()
            finally:
                names.Extent_dir = original_extent_dir
                imagery.extents_dict.clear()
                imagery.extents_dict.update(original_extents)

        self.assertIn("AREA", parsed_extents)
        self.assertNotIn("BAD", parsed_extents)
        self.assertEqual(parsed_extents["AREA"]["dir"], "Test")
        self.assertEqual(parsed_extents["AREA"]["mask_bounds"], [1.0, 2.0, 3.0, 4.0])
        self.assertIn("extent BAD: error: unexpected", stdout.getvalue())

    def test_color_filters_use_double_extension_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            filter_root = Path(temp_dir)
            (filter_root / "SEA.flt.json").write_text(
                json.dumps(
                    [
                        {
                            "operation": "brightness-contrast",
                            "parameters": [-30.0, 10.0],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            original_filter_dir = names.Filter_dir
            original_filters = imagery.color_filters_dict.copy()
            names.Filter_dir = str(filter_root)
            imagery.color_filters_dict.clear()
            imagery.color_filters_dict["none"] = []
            try:
                imagery.initialize_color_filters_dict()
                parsed_filters = imagery.color_filters_dict.copy()
            finally:
                names.Filter_dir = original_filter_dir
                imagery.color_filters_dict.clear()
                imagery.color_filters_dict.update(original_filters)

        self.assertEqual(
            parsed_filters["SEA"],
            [["brightness-contrast", -30.0, 10.0]],
        )

    def test_combined_providers_use_double_extension_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider_root = Path(temp_dir)
            (provider_root / "EUR.comb.json").write_text(
                json.dumps(
                    [
                        {
                            "layer_code": "Arc",
                            "extent_code": "default",
                            "color_code": "default",
                            "priority": "medium",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            original_provider_dir = names.Provider_dir
            original_providers = imagery.providers_dict.copy()
            original_extents = imagery.extents_dict.copy()
            original_filters = imagery.color_filters_dict.copy()
            original_combined = imagery.combined_providers_dict.copy()
            names.Provider_dir = str(provider_root)
            imagery.providers_dict.clear()
            imagery.providers_dict["Arc"] = {
                "extent": "global",
                "color_filters": "none",
            }
            imagery.extents_dict.clear()
            imagery.extents_dict["global"] = {"dir": None, "code": "global"}
            imagery.color_filters_dict.clear()
            imagery.color_filters_dict["none"] = []
            imagery.combined_providers_dict.clear()
            try:
                imagery.initialize_combined_providers_dict()
                parsed_combined = imagery.combined_providers_dict.copy()
            finally:
                names.Provider_dir = original_provider_dir
                imagery.providers_dict.clear()
                imagery.providers_dict.update(original_providers)
                imagery.extents_dict.clear()
                imagery.extents_dict.update(original_extents)
                imagery.color_filters_dict.clear()
                imagery.color_filters_dict.update(original_filters)
                imagery.combined_providers_dict.clear()
                imagery.combined_providers_dict.update(original_combined)

        self.assertEqual(
            parsed_combined["EUR"],
            [
                {
                    "layer_code": "Arc",
                    "extent_code": "global",
                    "color_code": "none",
                    "priority": "medium",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
