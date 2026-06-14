from __future__ import annotations

import re

from maintenance_common import run_command


def check_security_lint() -> tuple[str, str]:
    """Run ruff check --select S and count findings."""
    returncode, stdout, _stderr = run_command(
        ["uv", "run", "ruff", "check", "--select", "S", "src/"]
    )

    if returncode == 0:
        return "PASS", "0 findings"

    matches = re.findall(r"^S\d+", stdout, re.MULTILINE)
    count = len(matches)
    if count == 0:
        return "PASS", "0 findings"

    return "FAIL", f"{count} security findings"
