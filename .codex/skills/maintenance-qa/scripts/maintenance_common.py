from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR: Path | None = None


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    *,
    timeout: int = 600,
    pythonpath: bool = False,
) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if pythonpath:
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    try:
        result = subprocess.run(  # noqa: S603 - reviewed tool argument lists; no shell.
            cmd,
            cwd=cwd or ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 2, "", str(error)
    if REPORT_DIR is not None:
        name = hashlib.sha256("\0".join(cmd).encode()).hexdigest()[:12]
        (REPORT_DIR / f"command-{name}.txt").write_text(
            f"Command: {cmd!r}\nExit: {result.returncode}\n{result.stdout}\n{result.stderr}",
            encoding="utf-8",
        )
    return result.returncode, result.stdout, result.stderr
