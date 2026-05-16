import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
import O4_File_Names as names
import O4_Imagery_Utils as imagery


class ProviderParsingTests(unittest.TestCase):
    def test_fake_headers_accept_literals_and_known_user_agent_name(self):
        headers = imagery.parse_provider_fake_headers(
            "{'User-Agent': user_agent_generic, 'Accept': '*/*'}"
        )

        self.assertEqual(headers["User-Agent"], imagery.user_agent_generic)
        self.assertEqual(headers["Accept"], "*/*")

    def test_fake_headers_reject_executable_expression(self):
        with self.assertRaises(ValueError):
            imagery.parse_provider_fake_headers(
                "{'User-Agent': __import__('os').getcwd()}"
            )

    def test_fake_headers_reject_non_string_values(self):
        with self.assertRaises(ValueError):
            imagery.parse_provider_fake_headers("{'X-Retry': 3}")

    def test_provider_bool_requires_real_bool_literal(self):
        self.assertIs(imagery.parse_provider_bool("False"), False)
        self.assertIs(imagery.parse_provider_bool("True"), True)

        with self.assertRaises(ValueError):
            imagery.parse_provider_bool("'False'")

    def test_initialize_providers_accepts_safe_metadata_and_skips_bad_headers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider_root = Path(temp_dir)
            provider_dir = provider_root / "Test"
            provider_dir.mkdir()
            (provider_dir / "GOOD.lay").write_text(
                "\n".join(
                    [
                        "grid_type=webmercator",
                        "fake_headers={'User-Agent': user_agent_generic}",
                        "in_GUI=False",
                    ]
                ),
                encoding="utf-8",
            )
            (provider_dir / "BAD.lay").write_text(
                "\n".join(
                    [
                        "grid_type=webmercator",
                        "fake_headers={'User-Agent': __import__('os').getcwd()}",
                    ]
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
            provider_path = Path(temp_dir) / "BAD.lay"
            provider_path.write_text(
                "\n".join(
                    [
                        "grid_type=webmercator",
                        "url_template=https://example.test/{zoom}/{x}/{y}.jpg",
                        "surprise=value",
                    ]
                ),
                encoding="utf-8",
            )

            _, issues = imagery.parse_provider_definition("BAD", provider_path)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].field, "surprise")
        self.assertIn("unknown field", issues[0].message)

    def test_provider_schema_accepts_legacy_color_filter_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider_path = Path(temp_dir) / "SEA.lay"
            provider_path.write_text(
                "\n".join(
                    [
                        "grid_type=webmercator",
                        "url_template=https://example.test/{zoom}/{x}/{y}.jpg",
                        "color_filter=SEA",
                    ]
                ),
                encoding="utf-8",
            )

            original_filters = imagery.color_filters_dict.copy()
            imagery.color_filters_dict["SEA"] = []
            try:
                provider, issues = imagery.parse_provider_definition(
                    "SEA", provider_path
                )
            finally:
                imagery.color_filters_dict.clear()
                imagery.color_filters_dict.update(original_filters)

        self.assertEqual(issues, [])
        self.assertEqual(provider["color_filters"], "SEA")

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


if __name__ == "__main__":
    unittest.main()
