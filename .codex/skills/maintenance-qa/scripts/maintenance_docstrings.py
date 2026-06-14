from __future__ import annotations

import json
import re

from maintenance_common import SKILL_DIR, run_command

INTERROGATE_BASELINE_PATH = SKILL_DIR / "interrogate-baseline.json"


def check_docstring_coverage() -> tuple[str, str]:
    """Run interrogate and compare to baseline."""
    returncode, stdout, stderr = run_command(
        ["uv", "run", "interrogate", "src/", "--fail-under", "0"]
    )

    output = stdout + stderr
    if not output.strip():
        return "FAIL", f"No output captured (rc={returncode})"

    match = re.search(r"actual:\s*(\d+\.\d+)%", output)
    if not match:
        return "FAIL", f"Could not parse docstring coverage from: {output[:200]}"

    coverage_pct = float(match.group(1))
    baseline = load_docstring_baseline()

    if coverage_pct >= baseline:
        return "PASS", f"{coverage_pct:.1f}% (baseline: {baseline:.1f}%)"

    return "FAIL", f"{coverage_pct:.1f}% (baseline: {baseline:.1f}%)"


def load_docstring_baseline() -> float:
    if not INTERROGATE_BASELINE_PATH.exists():
        return 10.0
    with open(INTERROGATE_BASELINE_PATH) as f:
        return json.load(f).get("minimum_coverage", 10.0)
