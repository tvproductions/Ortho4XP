from __future__ import annotations

import re

from maintenance_common import ROOT, run_command


def check_mutation_testing() -> tuple[str, str]:
    """Run mutmut (optional, skip if not configured)."""
    mutmut_config = ROOT / "mutmut.toml"
    if not mutmut_config.exists():
        return "SKIP", "Not yet configured"

    returncode, stdout, stderr = run_command(
        ["uv", "run", "mutmut", "run", "--paths-to-mutate", "src/"]
    )

    match = re.search(r"(\d+) survived", stdout)
    if match:
        survived = int(match.group(1))
        return "WARN", f"{survived} mutations survived"

    if returncode == 0:
        return "PASS", "All mutations killed"

    return "FAIL", f"mutmut failed: {stderr[:100]}"
