from __future__ import annotations

import json
import re

from maintenance_common import SKILL_DIR, run_command

COVERAGE_BASELINE_PATH = SKILL_DIR / "coverage-baseline.json"


def check_test_coverage() -> tuple[str, str]:
    """Run coverage and compare to baseline."""
    returncode, stdout, stderr = run_command(
        ["uv", "run", "coverage", "run", "-m", "unittest", "discover", "-s", "tests"]
    )

    if returncode != 0:
        combined = stdout + stderr
        return "FAIL", f"Tests failed (rc={returncode}): {combined[:300]}"

    _returncode, stdout, _stderr = run_command(["uv", "run", "coverage", "report"])

    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", stdout)
    if not match:
        return "FAIL", f"Could not parse coverage from: {stdout[:200]}"

    coverage_pct = int(match.group(1))
    baseline = load_coverage_baseline()

    if coverage_pct >= baseline:
        return "PASS", f"{coverage_pct}% (baseline: {baseline}%)"

    return "FAIL", f"{coverage_pct}% (baseline: {baseline}%)"


def load_coverage_baseline() -> int:
    if not COVERAGE_BASELINE_PATH.exists():
        return 40
    with open(COVERAGE_BASELINE_PATH) as f:
        return json.load(f).get("minimum_coverage", 40)
