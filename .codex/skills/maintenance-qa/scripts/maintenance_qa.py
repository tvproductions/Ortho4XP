"""Explicit source hygiene; never invoked by routine quality, hooks, or CI."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

import maintenance_common
from maintenance_common import ROOT, run_command
from maintenance_dead_code import check_dead_code
from maintenance_dependency import (
    check_dependency_cves,
    check_dependency_usage,
    check_import_boundaries,
)
from maintenance_docstrings import check_docstring_coverage
from maintenance_mutation import check_mutation_testing
from maintenance_security import check_security_lint
from maintenance_test_coverage import check_test_coverage


def check_complexity() -> tuple[str, str]:
    """Run all three complexity tools and the retained stricter project ratchet."""
    code, stdout, stderr = run_command(
        [
            "uv",
            "run",
            "--group",
            "hygiene",
            "python",
            ".codex/skills/quality-check/scripts/quality_check.py",
            "--complexity-only",
        ]
    )
    return ("PASS" if code == 0 else "FAIL"), (stdout + stderr)[-700:]


CHECKS = [
    ("Complexity", check_complexity),
    ("Dependency CVEs", check_dependency_cves),
    ("Dependency usage", check_dependency_usage),
    ("Import boundaries", check_import_boundaries),
    ("Bandit security", check_security_lint),
    ("Dead code", check_dead_code),
    ("Test coverage", check_test_coverage),
    ("Docstring coverage", check_docstring_coverage),
]


def maintenance_arguments() -> argparse.Namespace:
    """Require explicit disposable mutation configuration if mutation is requested."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutation-config", type=Path)
    parser.add_argument("--mutation-workdir", type=Path)
    args = parser.parse_args()
    if bool(args.mutation_config) != bool(args.mutation_workdir):
        parser.error("Mutation config and disposable workdir must be supplied together")
    return args


def configure_reports() -> Path:
    """Preserve analyzer output with consistent UTF-8 on Windows and POSIX."""
    for stream in (sys.stdout, sys.stderr):
        configure_stream(stream)
    (ROOT / "tmp").mkdir(exist_ok=True)
    report = Path(tempfile.mkdtemp(prefix="maintenance-hygiene-", dir=ROOT / "tmp"))
    maintenance_common.REPORT_DIR = report
    return report


def configure_stream(stream) -> None:
    """Set the console encoding without requiring a real terminal in tests."""
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


def run_check(name: str, check) -> dict[str, str]:
    """Keep independent dimensions running after a failed tool or adapter."""
    print(f"Running {name}...", flush=True)
    try:
        status, details = check()
    except (
        Exception
    ) as error:  # Adapter errors are failed measurements, never clean reports.
        status, details = "FAIL", f"Measurement error: {error}"
    return {"dimension": name, "status": status, "details": details}


def mutation_result(args: argparse.Namespace) -> dict[str, str]:
    """Separate unrequested mutation from an attempted failed assessment."""
    if args.mutation_config:
        status, details = check_mutation_testing(
            args.mutation_config, args.mutation_workdir
        )
    else:
        status, details = (
            "NOT_REQUESTED",
            "Requires explicit disposable scope and config",
        )
    return {"dimension": "Mutation testing", "status": status, "details": details}


def report_results(results: list[dict[str, str]], report: Path) -> int:
    """Retain the complete result set and report its real aggregate verdict."""
    (report / "summary.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print("\nMaintenance QA Report")
    for result in results:
        print(f"{result['dimension']}: {result['status']} {result['details']}")
    failed = any(result["status"] == "FAIL" for result in results)
    print(
        f"Result: {'FAIL' if failed else 'PASS'}; receipts {report.relative_to(ROOT)}"
    )
    return int(failed)


def main() -> int:
    """Run only explicitly requested hygiene, with independently retained findings."""
    args = maintenance_arguments()
    report = configure_reports()
    results = [run_check(name, check) for name, check in CHECKS]
    results.append(mutation_result(args))
    return report_results(results, report)


if __name__ == "__main__":
    sys.exit(main())
