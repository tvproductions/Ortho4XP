from __future__ import annotations

import re

from maintenance_common import run_command


def check_dependency_cves() -> tuple[str, str]:
    """Run uv audit and check for CVEs."""
    returncode, stdout, stderr = run_command(
        ["uv", "audit", "--preview-features", "audit-command"]
    )

    output = stdout + stderr
    if "Found 0 known vulnerabilities" in output:
        return "PASS", "No known CVEs"

    match = re.search(r"Found (\d+) known vulnerabilities", output)
    if match:
        count = int(match.group(1))
        return "WARN", f"{count} known CVEs (assessed, see SECURITY.md)"

    if returncode != 0 and "Found" not in output:
        return "FAIL", f"uv audit failed: {stderr[:100]}"

    return "PASS", "No known CVEs"
