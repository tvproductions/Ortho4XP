"""Measure active-source branch and statement coverage with unittest."""

import json
import tempfile
from pathlib import Path

from maintenance_common import ROOT, SKILL_DIR, run_command

COVERAGE_BASELINE_PATH = SKILL_DIR / "coverage-baseline.json"
COVERAGE = ["uv", "run", "--group", "hygiene", "coverage"]


def coverage_directory() -> Path:
    """Allocate isolated local coverage data and JSON receipts."""
    (ROOT / "tmp").mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="coverage-hygiene-", dir=ROOT / "tmp"))


def collect_coverage(directory: Path) -> str | None:
    """Require a clean unittest baseline before producing the source report."""
    data = directory / ".coverage"
    command = [
        *COVERAGE,
        "run",
        "--branch",
        "--source",
        "src",
        "--data-file",
        str(data),
    ]
    command += ["-m", "unittest", "discover", "-s", "tests"]
    code, stdout, stderr = run_command(command)
    if code:
        return f"Unittest baseline failed: {(stdout + stderr)[-300:]}"
    command = [
        *COVERAGE,
        "json",
        "--data-file",
        str(data),
        "-o",
        str(directory / "coverage.json"),
    ]
    code, stdout, stderr = run_command(command)
    return f"Coverage report failed: {(stdout + stderr)[-300:]}" if code else None


def coverage_summary(directory: Path) -> tuple[str, str]:
    """Use native statement/branch totals without lowering the project minimum."""
    try:
        totals = json.loads((directory / "coverage.json").read_text(encoding="utf-8"))[
            "totals"
        ]
        percentage = float(totals["percent_covered"])
        branches = int(totals["num_branches"])
    except OSError, ValueError, KeyError, TypeError:
        return "FAIL", "Invalid coverage JSON"
    minimum = load_coverage_baseline()
    status = "PASS" if percentage >= minimum else "FAIL"
    return (
        status,
        f"{percentage:.2f}% statement/branch coverage; {branches} branches; minimum {minimum}%; receipt {directory.relative_to(ROOT)}",
    )


def check_test_coverage() -> tuple[str, str]:
    """Assess source coverage against the unchanged project minimum."""
    directory = coverage_directory()
    error = collect_coverage(directory)
    if error:
        return "FAIL", error
    return coverage_summary(directory)


def load_coverage_baseline() -> int:
    """Read the existing project minimum; adoption never lowers it."""
    return json.loads(COVERAGE_BASELINE_PATH.read_text(encoding="utf-8"))[
        "minimum_coverage"
    ]
