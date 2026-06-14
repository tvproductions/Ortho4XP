import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

QUALITY_CHECK_PATH = (
    Path(__file__).resolve().parents[1]
    / ".codex"
    / "skills"
    / "quality-check"
    / "scripts"
    / "quality_check.py"
)


spec = importlib.util.spec_from_file_location("quality_check", QUALITY_CHECK_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load quality check module from {QUALITY_CHECK_PATH}")
quality_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = quality_check
spec.loader.exec_module(quality_check)


class QualityCheckTests(unittest.TestCase):
    def test_severity_for_high_is_worse_metric(self):
        config = {"polarity": "high", "advise": 4.0, "warn": 7.0, "block": 11.0}

        self.assertIsNone(quality_check.severity_for(3.0, config))
        self.assertEqual(quality_check.severity_for(4.0, config), "advise")
        self.assertEqual(quality_check.severity_for(7.0, config), "warn")
        self.assertEqual(quality_check.severity_for(11.0, config), "block")

    def test_severity_for_low_is_worse_metric(self):
        config = {"polarity": "low", "advise": 85.0, "warn": 70.0, "block": 50.0}

        self.assertIsNone(quality_check.severity_for(90.0, config))
        self.assertEqual(quality_check.severity_for(85.0, config), "advise")
        self.assertEqual(quality_check.severity_for(70.0, config), "warn")
        self.assertEqual(quality_check.severity_for(50.0, config), "block")

    def test_baseline_comparison_blocks_new_block_finding(self):
        finding = quality_check.Finding(
            metric="radon_cc",
            path="src/example.py",
            name="build",
            value=12.0,
            severity="block",
        )
        thresholds = {"radon_cc": {"polarity": "high"}}

        regressions = quality_check.compare_to_baseline([finding], {}, thresholds)

        self.assertEqual(len(regressions), 1)
        self.assertIn("new block", regressions[0].reason)

    def test_baseline_comparison_blocks_worse_existing_finding(self):
        finding = quality_check.Finding(
            metric="radon_mi",
            path="src/example.py",
            name="<module>",
            value=45.0,
            severity="block",
        )
        baseline = {finding.key: {"value": 50.0}}
        thresholds = {"radon_mi": {"polarity": "low"}}

        regressions = quality_check.compare_to_baseline([finding], baseline, thresholds)

        self.assertEqual(len(regressions), 1)
        self.assertEqual(regressions[0].baseline_value, 50.0)

    def test_baseline_comparison_allows_existing_equal_finding(self):
        finding = quality_check.Finding(
            metric="lizard_ccn",
            path="src/example.py",
            name="build",
            value=11.0,
            severity="block",
        )
        baseline = {finding.key: {"value": 11.0}}
        thresholds = {"lizard_ccn": {"polarity": "high"}}

        regressions = quality_check.compare_to_baseline([finding], baseline, thresholds)

        self.assertEqual(regressions, [])

    def test_baseline_comparison_matches_line_shifted_existing_finding(self):
        finding = quality_check.Finding(
            metric="lizard_ccn",
            path="src/example.py",
            name="build",
            value=11.0,
            severity="block",
            line=20,
        )
        baseline = {
            "lizard_ccn|src/example.py|10|build": {
                "metric": "lizard_ccn",
                "path": "src/example.py",
                "name": "build",
                "value": 11.0,
            }
        }
        thresholds = {"lizard_ccn": {"polarity": "high"}}

        regressions = quality_check.compare_to_baseline([finding], baseline, thresholds)

        self.assertEqual(regressions, [])

    def test_baseline_comparison_matches_lizard_signature_changes(self):
        finding = quality_check.Finding(
            metric="lizard_ccn",
            path="src/example.py",
            name="build( items = None )",
            value=11.0,
            severity="block",
            line=20,
        )
        baseline = {
            "lizard_ccn|src/example.py|10|build( items = [] )": {
                "metric": "lizard_ccn",
                "path": "src/example.py",
                "name": "build( items = [] )",
                "value": 11.0,
            }
        }
        thresholds = {"lizard_ccn": {"polarity": "high"}}

        regressions = quality_check.compare_to_baseline([finding], baseline, thresholds)

        self.assertEqual(regressions, [])

    def test_compile_database_files_returns_repo_relative_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            compile_db = Path(directory) / "compile_commands.json"
            compile_db.write_text(
                json.dumps(
                    [
                        {
                            "directory": str(quality_check.ROOT),
                            "command": "clang -c Utils/src/Triangle4XP.c",
                            "file": str(
                                quality_check.ROOT / "Utils" / "src" / "Triangle4XP.c"
                            ),
                        }
                    ]
                ),
                encoding="utf-8",
            )

            files = quality_check.compile_database_files(compile_db)

        self.assertEqual(files, {"Utils/src/Triangle4XP.c"})

    def test_complexity_targets_exclude_vulture_whitelist(self):
        self.assertNotIn(
            ".codex/skills/maintenance-qa/vulture.whitelist.py",
            quality_check.all_python_files(),
        )

    def test_native_files_in_compile_database_splits_coverage(self):
        compiled, missing = quality_check.native_files_in_compile_database(
            ["Utils/src/Triangle4XP.c", "Utils/src/triangle.c"],
            {"Utils/src/Triangle4XP.c"},
        )

        self.assertEqual(compiled, ["Utils/src/Triangle4XP.c"])
        self.assertEqual(missing, ["Utils/src/triangle.c"])

    def test_run_native_command_suppresses_success_output(self):
        proc = quality_check.subprocess.CompletedProcess(
            ["native-tool"], 0, stdout="warning noise\n", stderr="more noise\n"
        )
        with (
            mock.patch.object(quality_check.subprocess, "run", return_value=proc),
            mock.patch("builtins.print") as print_mock,
        ):
            result = quality_check.run_native_command(["native-tool"])

        self.assertIs(result, proc)
        printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("+ native-tool", printed)
        self.assertNotIn("warning noise", printed)
        self.assertNotIn("more noise", printed)


if __name__ == "__main__":
    unittest.main()
