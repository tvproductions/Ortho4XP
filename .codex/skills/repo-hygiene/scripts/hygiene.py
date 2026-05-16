from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
TY_BASELINE = ["tests", "src/O4_Geo_Utils.py", "src/O4_File_Names.py"]
NATIVE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
NATIVE_PATHS = ["Utils/src"]
LLVM_TOOL_DIRS = [
    Path("C:/Program Files/LLVM/bin"),
    Path("/opt/homebrew/opt/llvm/bin"),
    Path("/usr/local/opt/llvm/bin"),
    Path("/usr/lib/llvm-22/bin"),
    Path("/usr/lib/llvm-21/bin"),
    Path("/usr/lib/llvm-20/bin"),
    Path("/usr/lib/llvm-19/bin"),
    Path("/usr/lib/llvm-18/bin"),
]
FORBIDDEN_PATTERNS = [
    "pytest",
    "py.test",
    "requirements.txt",
    "python -m pip",
    "pip install",
    "python -m venv",
    "source venv",
    "activate.bat",
]
SCAN_PATHS = [
    "README.md",
    "AGENTS.md",
    "ROADMAP.md",
    "TODO.md",
    ".github",
    "install_mac.sh",
    "install_windows.bat",
    "start_mac.sh",
    "start_windows.bat",
    "pyproject.toml",
    "tests",
]


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args))
    return subprocess.run(
        args,
        cwd=ROOT,
        check=check,
        text=True,
    )


def capture(args: list[str]) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def capture_lines(args: list[str]) -> list[str]:
    output = capture(args)
    return [line for line in output.splitlines() if line]


def changed_python_files() -> list[str]:
    return capture_lines(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRTUXB",
            "HEAD",
            "--",
            "*.py",
        ]
    )


def changed_native_files() -> list[str]:
    pathspecs = [f"*{extension}" for extension in sorted(NATIVE_EXTENSIONS)]
    changed = capture_lines(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRTUXB",
            "HEAD",
            "--",
            *pathspecs,
        ]
    )
    untracked = capture_lines(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            *pathspecs,
        ]
    )
    native_paths = [
        path
        for path in dict.fromkeys([*changed, *untracked])
        if Path(path).suffix.lower() in NATIVE_EXTENSIONS
        and any(
            path.startswith(f"{prefix}/") or path.startswith(f"{prefix}\\")
            for prefix in NATIVE_PATHS
        )
    ]
    return native_paths


def resolve_tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    windows_name = f"{name}.exe"
    for tool_dir in LLVM_TOOL_DIRS:
        candidate = tool_dir / windows_name
        if candidate.exists():
            return str(candidate)
        candidate = tool_dir / name
        if candidate.exists():
            return str(candidate)
    raise SystemExit(f"Required LLVM tool not found: {name}")


def changed_line_ranges(path: str) -> list[tuple[int, int]]:
    file_path = ROOT / path
    if not file_path.exists():
        return []

    tracked = run(["git", "ls-files", "--error-unmatch", path], check=False)
    if tracked.returncode != 0:
        line_count = len(
            file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        )
        return [(1, max(line_count, 1))]

    diff = capture(["git", "diff", "--unified=0", "HEAD", "--", path])
    ranges: list[tuple[int, int]] = []
    for line in diff.splitlines():
        if not line.startswith("@@ "):
            continue
        marker = line.split(" +", 1)[1].split(" ", 1)[0]
        if "," in marker:
            start_s, count_s = marker.split(",", 1)
            start = int(start_s)
            count = int(count_s)
        else:
            start = int(marker)
            count = 1
        if count > 0:
            ranges.append((start, start + count - 1))
    return ranges


def run_clang_format_check(files: list[str]) -> None:
    if not files:
        print("No changed native C/C++ files for clang-format.")
        return

    clang_format = resolve_tool("clang-format")
    for path in files:
        ranges = changed_line_ranges(path)
        if not ranges:
            continue
        args = [clang_format, "--dry-run", "--Werror"]
        for start, end in ranges:
            args.append(f"--lines={start}:{end}")
        args.append(path)
        run(args)


def run_clang_tidy(files: list[str]) -> None:
    clang_tidy = resolve_tool("clang-tidy")
    run([clang_tidy, "--verify-config"])

    compile_db = ROOT / "Utils" / "build" / "llvm-release" / "compile_commands.json"
    if not files:
        print("No changed native C/C++ files for clang-tidy.")
        return
    if not compile_db.exists():
        print("No compile database yet; skipping changed-file clang-tidy.")
        return

    for path in files:
        ranges = changed_line_ranges(path)
        if not ranges:
            continue
        line_filter = json.dumps(
            [{"name": str((ROOT / path).resolve()), "lines": ranges}]
        )
        run(
            [
                clang_tidy,
                "-p",
                str(compile_db.parent),
                "--quiet",
                f"--line-filter={line_filter}",
                path,
            ]
        )


def format_check_targets(changed: list[str]) -> list[str]:
    targets = list(changed)
    skill_script = ".codex/skills/repo-hygiene/scripts/hygiene.py"
    if skill_script not in targets:
        targets.append(skill_script)
    return targets


def scan_forbidden_patterns() -> None:
    existing_paths = [path for path in SCAN_PATHS if (ROOT / path).exists()]
    if not existing_paths:
        return
    pattern = "|".join(FORBIDDEN_PATTERNS)
    result = run(
        [
            "rg",
            "-n",
            pattern,
            "-S",
            *existing_paths,
            "-g",
            "!uv.lock",
            "-g",
            "!.venv/**",
            "-g",
            "!Utils/build/**",
        ],
        check=False,
    )
    if result.returncode not in (0, 1):
        raise subprocess.CalledProcessError(result.returncode, result.args)
    if result.returncode == 0:
        raise SystemExit("Forbidden legacy pattern found. See rg output above.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ortho4XP hygiene checks.")
    parser.add_argument(
        "--quick", action="store_true", help="Run Python hygiene checks."
    )
    parser.add_argument(
        "--full", action="store_true", help="Run Python and native C hygiene checks."
    )
    args = parser.parse_args()

    full = args.full or not args.quick

    run(["git", "status", "--short", "--branch"], check=False)
    scan_forbidden_patterns()
    run(["uv", "sync", "--dev"])
    run(["uv", "run", "python", "-m", "unittest", "discover", "-s", "tests"])
    run(["uv", "run", "ruff", "check", "Ortho4XP.py", "src"])
    run(["uv", "run", "ty", "check", *TY_BASELINE])

    changed = changed_python_files()
    run(["uv", "run", "ruff", "format", "--check", *format_check_targets(changed)])
    if changed:
        run(["uv", "run", "ty", "check", *changed])

    if full:
        native = changed_native_files()
        run_clang_format_check(native)
        run(["cmake", "--fresh", "--preset", "llvm-release", "-S", "Utils"])
        run_clang_tidy(native)
        run(["cmake", "--build", "Utils/build/llvm-release", "--target", "Triangle4XP"])

    run(["git", "status", "--short"], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
