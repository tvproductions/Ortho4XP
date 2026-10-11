"""Measure docstring presence without replacing usefulness review."""

import json
import re

from maintenance_common import SKILL_DIR, run_command

INTERROGATE_BASELINE_PATH = SKILL_DIR / "interrogate-baseline.json"


def docstring_result(code: int, stdout: str, stderr: str) -> tuple[str, str]:
    """Preserve execution errors and compare native coverage to the project minimum."""
    output = stdout + stderr
    if code != 0:
        return "FAIL", f"Interrogate execution error: {output[:200]}"
    match = re.search(r"actual:\s*(\d+\.\d+)%", output)
    if not match:
        return "FAIL", f"Invalid docstring measurement: {output[:200]}"
    percentage = float(match.group(1))
    minimum = load_docstring_baseline()
    status = "PASS" if percentage >= minimum else "FAIL"
    return status, f"{percentage:.1f}% (baseline: {minimum:.1f}%)"


def check_docstring_coverage() -> tuple[str, str]:
    """Run Interrogate against source without adding meaningless docstrings."""
    command = [
        "uv",
        "run",
        "--group",
        "hygiene",
        "interrogate",
        "src/",
        "--fail-under",
        "0",
    ]
    return docstring_result(*run_command(command))


def load_docstring_baseline() -> float:
    """Retain the existing project-owned minimum."""
    return json.loads(INTERROGATE_BASELINE_PATH.read_text(encoding="utf-8"))[
        "minimum_coverage"
    ]
