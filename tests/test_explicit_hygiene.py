"""Public workflow outcomes for explicit, fail-closed hygiene."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".codex/skills/maintenance-qa/scripts"
sys.path.insert(0, str(SCRIPTS))

maintenance_dead_code = importlib.import_module("maintenance_dead_code")
maintenance_security = importlib.import_module("maintenance_security")
maintenance_dependency = importlib.import_module("maintenance_dependency")
maintenance_mutation = importlib.import_module("maintenance_mutation")
maintenance_common = importlib.import_module("maintenance_common")


def audit_report(*, vulnerable=False, skipped=False):
    identity = {"name": "requests", "version": "2.34.2", "vulns": []}
    if vulnerable:
        identity["vulns"] = [{"id": "invented"}]
    if skipped:
        identity["skip_reason"] = "invented"
    return {"dependencies": [identity]}


def audit_cases():
    return (
        ({"dependencies": []}, 0, "FAIL"),
        (audit_report(), 0, "PASS"),
        (audit_report(vulnerable=True), 1, "FAIL"),
        (audit_report(skipped=True), 0, "FAIL"),
        ({}, 2, "FAIL"),
    )


class ExplicitHygieneTests(unittest.TestCase):
    def test_dead_code_receipt_counts_unreachable_and_unsatisfiable_findings(self):
        report = "\n".join(
            (
                "fixture.py:2: unused variable 'name' (100% confidence)",
                "fixture.py:4: unreachable code after 'return' (100% confidence)",
                "fixture.py:8: unsatisfiable 'if' condition (100% confidence)",
                "tool error: unused option",
            )
        )
        self.assertEqual(maintenance_dead_code.count_unused_lines(report), 3)

    def assert_audit_case(self, report, code, expected):
        calls = []

        def command(cmd):
            calls.append(cmd)
            if "export" in cmd:
                Path(cmd[-1]).write_text("requests==2.34.2\n", encoding="utf-8")
                return 0, "", ""
            return code, json.dumps(report), "synthetic auditor response"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "uv.lock").write_text("package = []\n", encoding="utf-8")
            with (
                mock.patch.object(maintenance_dependency, "ROOT", root),
                mock.patch.object(
                    maintenance_dependency, "run_command", side_effect=command
                ),
            ):
                status, _ = maintenance_dependency.check_dependency_cves()
        self.assertEqual(status, expected, report)
        self.assertEqual(len(calls), 2)

    def test_pip_audit_must_account_for_every_exported_identity(self):
        for report, code, expected in audit_cases():
            with self.subTest(report=report, code=code):
                self.assert_audit_case(report, code, expected)

    def test_incomplete_mutation_results_cannot_pass(self):
        self.assertTrue(hasattr(maintenance_mutation, "mutation_status"))
        self.assertEqual(
            maintenance_mutation.mutation_status(13, [("NORMAL", "KILLED", 12)]), "FAIL"
        )
        self.assertEqual(
            maintenance_mutation.mutation_status(13, [("NORMAL", "KILLED", 13)]), "PASS"
        )
        self.assertEqual(
            maintenance_mutation.mutation_status(
                13, [("NORMAL", "KILLED", 12), ("NORMAL", "SURVIVED", 1)]
            ),
            "WARN",
        )
        self.assertEqual(
            maintenance_mutation.mutation_status(
                13, [("NORMAL", "KILLED", 12), ("EXCEPTION", "INCOMPETENT", 1)]
            ),
            "FAIL",
        )

    def test_flat_import_adapter_keeps_conditional_and_indirect_edges(self):
        path = SCRIPTS / "maintenance_import_graph.py"
        self.assertTrue(path.exists(), "flat module Import Linter adapter is required")
        spec = importlib.util.spec_from_file_location("flat_import_graph", path)
        if spec is None or spec.loader is None:
            raise AssertionError("Cannot load flat import graph adapter")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        edges = module.import_edges(
            "if False:\n    import O4_Config_Utils as CFG\nfrom requests.adapters import HTTPAdapter\n",
            "fixture.py",
        )
        self.assertEqual([edge[0] for edge in edges], ["requests", "O4_Config_Utils"])
        with self.assertRaises(ValueError):
            module.import_edges("from .sibling import value\n", "fixture.py")

    def test_missing_executable_is_a_failing_measurement(self):
        with mock.patch.object(
            maintenance_common.subprocess, "run", side_effect=FileNotFoundError("tool")
        ):
            result = maintenance_common.run_command(["missing-executable"])
        self.assertNotEqual(result[0], 0)

    def test_auditor_failure_cannot_report_clean(self):
        with mock.patch.object(
            maintenance_dependency,
            "run_command",
            return_value=(2, "{}", "auditor failure"),
        ):
            status, _ = maintenance_dependency.check_dependency_cves()
        self.assertEqual(status, "FAIL")

    def test_known_vulnerabilities_remain_failed_hygiene(self):
        with mock.patch.object(
            maintenance_dependency,
            "run_command",
            return_value=(1, "Found 4 known vulnerabilities", ""),
        ):
            status, _ = maintenance_dependency.check_dependency_cves()
        self.assertEqual(status, "FAIL")

    def test_mutation_is_explicitly_bounded_and_unconfigured_scope_fails(self):
        with mock.patch.object(maintenance_mutation, "ROOT", ROOT / "missing-fixture"):
            status, _ = maintenance_mutation.check_mutation_testing()
        self.assertEqual(status, "FAIL")

    def test_security_tool_failure_cannot_report_clean(self):
        with mock.patch.object(
            maintenance_security, "run_command", return_value=(2, "", "missing tool")
        ):
            status, _ = maintenance_security.check_security_lint()
        self.assertEqual(status, "FAIL")

    def test_dead_code_tool_failure_cannot_report_clean(self):
        with mock.patch.object(
            maintenance_dead_code, "run_command", return_value=(2, "", "missing tool")
        ):
            status, _ = maintenance_dead_code.check_dead_code()
        self.assertEqual(status, "FAIL")

    def test_lizard_absolute_failure_is_not_a_baseline_waiver(self):
        path = ROOT / ".codex/skills/quality-check/scripts/complexity_check.py"
        self.assertTrue(path.exists(), "explicit Lizard contract checker must exist")
        spec = importlib.util.spec_from_file_location("explicit_complexity", path)
        if spec is None or spec.loader is None:
            raise AssertionError("Cannot load complexity checker")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        violations, aggregate = module.findings(
            [
                {
                    "file": "fixture.py",
                    "functions": [{"name": "f", "line": 1, "complexity": 21}],
                    "mean": 21,
                }
            ]
        )
        self.assertEqual(len(violations), 3)
        self.assertEqual(aggregate["overall_mean"], 21)

    def test_explicit_lizard_missing_scope_fails_closed(self):
        path = ROOT / ".codex/skills/quality-check/scripts/complexity_check.py"
        self.assertTrue(path.exists(), "explicit Lizard contract checker must exist")
        result = subprocess.run(  # noqa: S603 - fixed checker and synthetic missing scope.
            [
                sys.executable,
                str(path),
                "--root",
                str(ROOT),
                "--paths",
                "missing-fixture",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
