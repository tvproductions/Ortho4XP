from __future__ import annotations

import re

from maintenance_common import SKILL_DIR, run_command

VULTURE_WHITELIST_PATH = SKILL_DIR / "vulture.whitelist.py"


def check_dead_code() -> tuple[str, str]:
    """Measure active source and fail when findings or tool errors remain."""
    cmd = ["uv", "run", "--group", "hygiene", "vulture", "src"]
    if VULTURE_WHITELIST_PATH.exists():
        cmd.append(str(VULTURE_WHITELIST_PATH))
    cmd.extend(["--exclude", "src/Unused", "--min-confidence", "80"])
    code, stdout, stderr = run_command(cmd)
    if code == 0:
        return "PASS", "0 findings"
    count = count_unused_lines(stdout)
    if count == 0:
        return "FAIL", f"Vulture execution error (rc={code}): {stderr[:200]}"
    return (
        "FAIL",
        f"{count} dead code findings; investigate external consumers before deletion",
    )


def is_unused_line(line: str) -> bool:
    """Recognize actual candidates without treating tool errors as measurements."""
    return re.fullmatch(r".+:\d+: .+ \(\d+% confidence\)", line.strip()) is not None


def count_unused_lines(output: str) -> int:
    """Count candidates from the retained native analyzer receipt."""
    count = 0
    for line in output.splitlines():
        if is_unused_line(line):
            count += 1
    return count
