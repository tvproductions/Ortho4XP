import importlib.util
import json
import subprocess
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
    def test_lint_hook_uses_the_routine_project_scope(self):
        with (
            mock.patch.object(
                quality_check.sys, "argv", ["quality-check", "--lint-only"]
            ),
            mock.patch.object(quality_check, "run") as run,
            mock.patch.object(quality_check, "run_full_quality") as full,
        ):
            self.assertEqual(quality_check.main(), 0)
        run.assert_called_once_with(
            [
                "uv",
                "run",
                "ruff",
                "check",
                *quality_check.existing_paths(quality_check.RUFF_LINT_PATHS),
            ]
        )
        full.assert_not_called()

    def test_partial_measurement_never_rewrites_baseline(self):
        process = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        receipt = {
            "status": "error",
            "aggregate": {},
            "errors": ["unsupported fixture"],
        }
        with (
            mock.patch.object(
                quality_check, "complexity_targets", return_value=["fixture.py"]
            ),
            mock.patch.object(quality_check, "run", return_value=process),
            mock.patch.object(quality_check, "assess", return_value=receipt),
            mock.patch.object(quality_check, "load_thresholds", return_value={}),
            mock.patch.object(quality_check, "load_baseline", return_value={}),
            mock.patch.object(
                quality_check,
                "measure_complexity",
                side_effect=quality_check.MeasurementError("unsupported fixture", []),
            ),
            mock.patch.object(quality_check, "write_baseline") as write,
            self.assertRaises(SystemExit),
        ):
            quality_check.run_complexity_gate("all", write=True)
        write.assert_not_called()

    def test_baseline_refresh_cannot_add_new_advice(self):
        finding = quality_check.Finding("lizard_nloc", "fixture.py", "f", 13, "advise")
        process = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        receipt = {"status": "passed", "aggregate": {}, "errors": []}
        with (
            mock.patch.object(
                quality_check, "complexity_targets", return_value=["fixture.py"]
            ),
            mock.patch.object(quality_check, "run", return_value=process),
            mock.patch.object(quality_check, "assess", return_value=receipt),
            mock.patch.object(
                quality_check,
                "load_thresholds",
                return_value={"lizard_nloc": {"polarity": "high"}},
            ),
            mock.patch.object(quality_check, "load_baseline", return_value={}),
            mock.patch.object(
                quality_check, "measure_complexity", return_value=[finding]
            ),
            mock.patch.object(quality_check, "write_baseline"),
            self.assertRaises(SystemExit),
        ):
            quality_check.run_complexity_gate("all", write=True)

    def test_percentage_cohesion_cannot_satisfy_legacy_lcom4_policy(self):
        process = subprocess.CompletedProcess(
            [],
            0,
            stdout="File: fixture.py\n  Class: Foo (1:0)\n    Total: 25.0%\n",
            stderr="",
        )
        with mock.patch.object(quality_check, "uv_tool", return_value=process):
            findings = quality_check.measure_cohesion(["fixture.py"], {})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].metric, "cohesion_policy_unverified")
        self.assertEqual(findings[0].value, 25.0)
        self.assertEqual(findings[0].severity, "block")

    def test_lizard_malformed_measurement_is_not_clean(self):
        process = subprocess.CompletedProcess(
            [], 0, stdout="unparseable csv\n", stderr=""
        )
        with (
            mock.patch.object(quality_check, "uv_tool", return_value=process),
            self.assertRaises(ValueError),
        ):
            quality_check.measure_lizard(["fixture.py"], {})

    def test_lizard_cannot_omit_a_real_function_or_nesting_column(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fixture.py").write_text(
                "def f():\n    return 1\n", encoding="utf-8"
            )
            reports = ("", "1,1,4,0,2,id,fixture.py,f,f(),1,2\n")
            for report in reports:
                process = subprocess.CompletedProcess([], 0, stdout=report, stderr="")
                with (
                    mock.patch.object(quality_check, "ROOT", root),
                    mock.patch.object(quality_check, "uv_tool", return_value=process),
                    self.assertRaises(ValueError),
                ):
                    quality_check.measure_lizard(["fixture.py"], {})

    def test_source_universe_includes_project_stack_checker(self):
        self.assertIn("scripts/check_skills_stack.py", quality_check.all_python_files())

    def test_routine_gate_keeps_native_without_deep_analysis(self):
        with (
            mock.patch.object(quality_check, "run") as run,
            mock.patch.object(quality_check, "changed_python_files", return_value=[]),
            mock.patch.object(quality_check, "run_code_quality_audits") as structural,
            mock.patch.object(quality_check, "run_complexity_gate") as deep,
            mock.patch.object(quality_check, "run_native_checks") as native,
        ):
            quality_check.run_full_quality()
        deep.assert_not_called()
        native.assert_called_once()
        structural.assert_called_once()
        commands = [call.args[0] for call in run.call_args_list]
        for tool in ("ruff", "ty", "unittest"):
            self.assertTrue(any(tool in command for command in commands))
        self.assertIn(["git", "diff", "--check"], commands)
        self.assertIn(
            ["uv", "run", "python", "scripts/check_skills_stack.py"], commands
        )

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
