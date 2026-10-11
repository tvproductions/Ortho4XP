"""Assess security findings independently of routine Ruff checks."""

import json

from maintenance_common import run_command


def bandit_result(code: int, stdout: str, stderr: str) -> tuple[str, str]:
    """Preserve native security findings and distinguish malformed measurements."""
    if code not in (0, 1):
        return "FAIL", f"Bandit execution error: {stderr[:200]}"
    try:
        payload = json.loads(stdout)
        results, errors = payload["results"], payload["errors"]
    except ValueError, KeyError, TypeError:
        return "FAIL", "Invalid Bandit report"
    if errors:
        return "FAIL", f"Bandit measurement errors: {errors}"
    return security_status(code, results), f"{len(results)} Bandit findings"


def security_status(code: int, findings: list) -> str:
    """Tool-reported failure and measured findings each preserve a failed verdict."""
    if code:
        return "FAIL"
    if findings:
        return "FAIL"
    return "PASS"


def check_security_lint() -> tuple[str, str]:
    """Run the pinned security analyzer with progress-free JSON receipts."""
    command = [
        "uv",
        "run",
        "--group",
        "hygiene",
        "bandit",
        "-q",
        "-r",
        "src",
        "Ortho4XP.py",
        "-f",
        "json",
    ]
    return bandit_result(*run_command(command))
