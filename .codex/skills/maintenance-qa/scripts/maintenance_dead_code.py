from __future__ import annotations

from maintenance_common import SKILL_DIR, run_command

VULTURE_WHITELIST_PATH = SKILL_DIR / "vulture.whitelist.py"


def check_dead_code() -> tuple[str, str]:
    """Run vulture and check for dead code."""
    cmd = ["uv", "run", "vulture", "src/", "--min-confidence", "80"]

    if VULTURE_WHITELIST_PATH.exists():
        cmd.extend(["--exclude", str(VULTURE_WHITELIST_PATH)])

    returncode, stdout, _stderr = run_command(cmd)

    if returncode == 0:
        return "PASS", "0 findings"

    count = count_unused_lines(stdout)
    if count == 0:
        return "PASS", "0 findings"

    return "WARN", f"{count} dead code findings"


def is_unused_line(line: str) -> bool:
    return bool(line.strip() and "unused" in line.lower())


def count_unused_lines(output: str) -> int:
    count = 0
    for line in output.splitlines():
        if is_unused_line(line):
            count += 1
    return count
