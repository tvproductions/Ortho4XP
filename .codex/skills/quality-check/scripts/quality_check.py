from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from io import StringIO
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from code_quality_audits import (  # noqa: E402
    CLASS_LINE_LIMIT,
    MODULE_HARD_LINE_LIMIT,
    MODULE_SOFT_LINE_LIMIT,
    audit_class_size,
    audit_module_size,
    audit_test_tiers,
    audit_type_ignores,
    collect_code_quality_findings,
)

ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = Path(__file__).resolve().parents[1]
THRESHOLDS_PATH = SKILL_DIR / "complexity-thresholds.json"
BASELINE_PATH = SKILL_DIR / "complexity-baseline.json"
TY_BASELINE = ["tests", "src/O4_Geo_Utils.py", "src/O4_File_Names.py"]
RUFF_LINT_PATHS = [
    "Ortho4XP.py",
    "src",
    "tests",
    ".codex/skills/quality-check/scripts/quality_check.py",
    ".codex/skills/quality-check/scripts/code_quality_audits.py",
    ".codex/skills/quality-check/scripts/code_quality_models.py",
    ".codex/skills/quality-check/scripts/code_quality_policy_audits.py",
    ".codex/skills/quality-check/scripts/code_quality_size_audits.py",
    ".codex/skills/repo-hygiene/scripts/hygiene.py",
    ".codex/skills/git-sync/scripts/git_sync.py",
]
FORMAT_BASELINE = [
    ".codex/skills/quality-check/scripts/quality_check.py",
    ".codex/skills/quality-check/scripts/code_quality_audits.py",
    ".codex/skills/quality-check/scripts/code_quality_models.py",
    ".codex/skills/quality-check/scripts/code_quality_policy_audits.py",
    ".codex/skills/quality-check/scripts/code_quality_size_audits.py",
    ".codex/skills/repo-hygiene/scripts/hygiene.py",
    ".codex/skills/git-sync/scripts/git_sync.py",
]
XENON_MAX_ABSOLUTE = "C"
XENON_MAX_MODULES = "C"
XENON_MAX_AVERAGE = "C"
XENON_QUALITY_TARGETS = [
    ".codex/skills/quality-check/scripts/quality_check.py",
    ".codex/skills/repo-hygiene/scripts/hygiene.py",
    "src/O4_Config_Models.py",
    "src/O4_Source_Data_Models.py",
    "tests/test_config_models.py",
    "tests/test_provider_parsing.py",
    "tests/test_quality_check.py",
]
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
SEVERITY_ORDER = {"advise": 1, "warn": 2, "block": 3}


@dataclass(frozen=True)
class Finding:
    metric: str
    path: str
    name: str
    value: float
    severity: str
    line: int | None = None

    @property
    def key(self) -> str:
        line = "" if self.line is None else str(self.line)
        return f"{self.metric}|{self.path}|{line}|{self.name}"


@dataclass(frozen=True)
class Regression:
    finding: Finding
    reason: str
    baseline_value: float | None = None


def run(
    args: list[str], *, check: bool = True, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args))
    return subprocess.run(
        args,
        cwd=ROOT,
        check=check,
        capture_output=capture,
        text=True,
    )


def capture_lines(args: list[str]) -> list[str]:
    proc = run(args, check=True, capture=True)
    return [line for line in proc.stdout.splitlines() if line]


def existing_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if (ROOT / path).exists()]


def changed_python_files() -> list[str]:
    changed = capture_lines(
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
    untracked = capture_lines(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "*.py",
        ]
    )
    return existing_paths(list(dict.fromkeys([*changed, *untracked])))


def all_python_files() -> list[str]:
    paths: list[str] = []
    for base in existing_paths(["Ortho4XP.py", "src", "tests", ".codex/skills"]):
        base_path = ROOT / base
        if base_path.is_file() and base_path.suffix == ".py":
            paths.append(base)
        elif base_path.is_dir():
            for item in base_path.rglob("*.py"):
                if "__pycache__" not in item.parts:
                    paths.append(item.relative_to(ROOT).as_posix())
    return sorted(dict.fromkeys(paths))


def complexity_targets(scope: str) -> list[str]:
    if scope == "all":
        return all_python_files()
    changed = changed_python_files()
    if ".codex/skills/quality-check/scripts/quality_check.py" not in changed:
        changed.append(".codex/skills/quality-check/scripts/quality_check.py")
    return existing_paths(changed)


def format_check_targets(changed: list[str]) -> list[str]:
    return existing_paths(list(dict.fromkeys([*changed, *FORMAT_BASELINE])))


def xenon_quality_targets() -> list[str]:
    return existing_paths(XENON_QUALITY_TARGETS)


def load_thresholds(path: Path = THRESHOLDS_PATH) -> dict[str, dict[str, float | str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    metrics = raw.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("complexity thresholds must define a metrics object")
    required = {"polarity", "advise", "warn", "block"}
    for metric, config in metrics.items():
        if not isinstance(config, dict) or set(config) != required:
            raise ValueError(f"invalid threshold config for {metric}")
        if config["polarity"] not in {"high", "low"}:
            raise ValueError(f"invalid threshold polarity for {metric}")
    return metrics


def severity_for(value: float, config: dict[str, float | str]) -> str | None:
    polarity = config["polarity"]
    if polarity == "low":
        if value <= float(config["block"]):
            return "block"
        if value <= float(config["warn"]):
            return "warn"
        if value <= float(config["advise"]):
            return "advise"
        return None

    if value >= float(config["block"]):
        return "block"
    if value >= float(config["warn"]):
        return "warn"
    if value >= float(config["advise"]):
        return "advise"
    return None


def make_finding(
    thresholds: dict[str, dict[str, float | str]],
    metric: str,
    path: str,
    name: str,
    value: float,
    line: int | None = None,
) -> Finding | None:
    config = thresholds.get(metric)
    if config is None:
        return None
    severity = severity_for(value, config)
    if severity is None:
        return None
    return Finding(
        metric=metric,
        path=normalize_path(path),
        name=name,
        value=value,
        severity=severity,
        line=line,
    )


def normalize_path(path: str) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except (OSError, ValueError):
        return path.replace("\\", "/")


def uv_tool(args: list[str]) -> subprocess.CompletedProcess[str]:
    return run(["uv", "run", *args], check=True, capture=True)


def measure_radon_cc(
    paths: list[str], thresholds: dict[str, dict[str, float | str]]
) -> list[Finding]:
    proc = uv_tool(["radon", "cc", "--json", "--no-assert", *paths])
    raw = json.loads(proc.stdout or "{}")
    findings: list[Finding] = []
    for path, entries in raw.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or "complexity" not in entry:
                continue
            name = str(entry.get("fullname") or entry.get("name") or "<unknown>")
            line = entry.get("lineno")
            finding = make_finding(
                thresholds,
                "radon_cc",
                path,
                name,
                float(entry["complexity"]),
                int(line) if isinstance(line, int) else None,
            )
            if finding:
                findings.append(finding)
    return findings


def measure_radon_mi(
    paths: list[str], thresholds: dict[str, dict[str, float | str]]
) -> list[Finding]:
    proc = uv_tool(["radon", "mi", "--json", *paths])
    raw = json.loads(proc.stdout or "{}")
    findings: list[Finding] = []
    for path, entry in raw.items():
        if not isinstance(entry, dict) or "mi" not in entry:
            continue
        finding = make_finding(
            thresholds, "radon_mi", path, "<module>", float(entry["mi"])
        )
        if finding:
            findings.append(finding)
    return findings


def measure_radon_hal(
    paths: list[str], thresholds: dict[str, dict[str, float | str]]
) -> list[Finding]:
    proc = uv_tool(["radon", "hal", "--json", *paths])
    raw = json.loads(proc.stdout or "{}")
    findings: list[Finding] = []
    for path, entry in raw.items():
        total = entry.get("total") if isinstance(entry, dict) else None
        if not isinstance(total, dict):
            total = entry if isinstance(entry, dict) else {}
        for source_key, metric in (
            ("volume", "radon_hal_volume"),
            ("difficulty", "radon_hal_difficulty"),
            ("effort", "radon_hal_effort"),
        ):
            if source_key not in total:
                continue
            finding = make_finding(
                thresholds, metric, path, "<module>", float(total[source_key])
            )
            if finding:
                findings.append(finding)
    return findings


def measure_radon_raw(
    paths: list[str], thresholds: dict[str, dict[str, float | str]]
) -> list[Finding]:
    proc = uv_tool(["radon", "raw", "--json", *paths])
    raw = json.loads(proc.stdout or "{}")
    findings: list[Finding] = []
    for path, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        for source_key, metric in (
            ("nloc", "radon_raw_nloc"),
            ("lloc", "radon_raw_lloc"),
        ):
            if source_key not in entry:
                continue
            finding = make_finding(
                thresholds, metric, path, "<module>", float(entry[source_key])
            )
            if finding:
                findings.append(finding)
    return findings


def measure_lizard(
    paths: list[str], thresholds: dict[str, dict[str, float | str]]
) -> list[Finding]:
    proc = uv_tool(["lizard", "-End", "--csv", *paths])
    reader = csv.reader(StringIO(proc.stdout))
    findings: list[Finding] = []
    for row in reader:
        if len(row) < 11 or row[0].lower() in {"nloc", "nloc "}:
            continue
        try:
            nloc = float(row[0])
            ccn = float(row[1])
            params = float(row[3])
            path = row[6]
            name = row[8] or row[7] or "<function>"
            line = int(row[9]) if row[9].isdigit() else None
            nesting = float(row[-1]) if len(row) > 11 and row[-1] else 0.0
        except (ValueError, IndexError):
            continue
        for metric, value in (
            ("lizard_nloc", nloc),
            ("lizard_param_count", params),
            ("lizard_nesting_depth", nesting),
            ("lizard_ccn", ccn),
        ):
            finding = make_finding(thresholds, metric, path, name, value, line)
            if finding:
                findings.append(finding)
    return findings


_LCOM4_PATTERN = re.compile(r"\bLCOM4\b[^0-9]*(\d+(?:\.\d+)?)", re.IGNORECASE)


def measure_cohesion(
    paths: list[str], thresholds: dict[str, dict[str, float | str]]
) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        proc = uv_tool(["cohesion", "-f", path])
        for line in proc.stdout.splitlines():
            match = _LCOM4_PATTERN.search(line)
            if not match:
                continue
            finding = make_finding(
                thresholds,
                "cohesion_lcom4",
                path,
                line.strip().split()[0] if line.strip() else "<class>",
                float(match.group(1)),
            )
            if finding:
                findings.append(finding)
    return findings


def measure_complexity(
    paths: list[str], thresholds: dict[str, dict[str, float | str]]
) -> list[Finding]:
    if not paths:
        return []
    findings: list[Finding] = []
    findings.extend(measure_radon_cc(paths, thresholds))
    findings.extend(measure_radon_mi(paths, thresholds))
    findings.extend(measure_radon_hal(paths, thresholds))
    findings.extend(measure_radon_raw(paths, thresholds))
    findings.extend(measure_lizard(paths, thresholds))
    findings.extend(measure_cohesion(paths, thresholds))
    return sorted(findings, key=lambda item: (item.path, item.metric, item.name))


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    findings = raw.get("findings", {})
    if not isinstance(findings, dict):
        raise ValueError("complexity baseline findings must be an object")
    return findings


def write_baseline(
    findings: list[Finding], targets: list[str], path: Path = BASELINE_PATH
) -> None:
    payload = {
        "version": 1,
        "generated_by": "quality-check",
        "scope": sorted(targets),
        "findings": {finding.key: asdict(finding) for finding in findings},
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Wrote complexity baseline: {path.relative_to(ROOT).as_posix()}")


def is_worse(value: float, baseline_value: float, polarity: str) -> bool:
    if polarity == "low":
        return value < baseline_value
    return value > baseline_value


def stable_finding_key(finding: Finding) -> tuple[str, str, str]:
    return (finding.metric, finding.path, finding.name)


def baseline_by_stable_key(
    baseline: dict[str, dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for prior in baseline.values():
        if not {"metric", "path", "name"} <= set(prior):
            continue
        key = (str(prior["metric"]), str(prior["path"]), str(prior["name"]))
        if key not in indexed:
            indexed[key] = prior
    return indexed


def compare_to_baseline(
    findings: list[Finding],
    baseline: dict[str, dict[str, Any]],
    thresholds: dict[str, dict[str, float | str]],
) -> list[Regression]:
    regressions: list[Regression] = []
    stable_baseline = baseline_by_stable_key(baseline)
    for finding in findings:
        prior = baseline.get(finding.key) or stable_baseline.get(
            stable_finding_key(finding)
        )
        if prior is None:
            if finding.severity == "block":
                regressions.append(
                    Regression(finding, "new block-level complexity finding")
                )
            continue
        prior_value = float(prior["value"])
        config = thresholds[finding.metric]
        if is_worse(finding.value, prior_value, str(config["polarity"])):
            regressions.append(
                Regression(
                    finding,
                    "complexity worse than baseline",
                    baseline_value=prior_value,
                )
            )
    return regressions


def print_complexity_summary(
    findings: list[Finding], regressions: list[Regression]
) -> None:
    counts = {"advise": 0, "warn": 0, "block": 0}
    for finding in findings:
        counts[finding.severity] += 1
    print(
        "Complexity findings: "
        f"advise={counts['advise']} warn={counts['warn']} block={counts['block']}"
    )
    if not regressions:
        print("Complexity baseline check passed.")
        return
    print("Complexity baseline regressions:")
    for regression in regressions[:50]:
        finding = regression.finding
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        baseline = (
            ""
            if regression.baseline_value is None
            else f" baseline={regression.baseline_value:g}"
        )
        print(
            f"  {finding.severity.upper()} {finding.metric}={finding.value:g}{baseline} "
            f"{location} {finding.name} - {regression.reason}"
        )
    if len(regressions) > 50:
        print(f"  ... {len(regressions) - 50} more")


def run_complexity_gate(scope: str, *, write: bool = False) -> None:
    targets = complexity_targets(scope)
    print(f"Complexity scope: {scope} ({len(targets)} files)")
    run_xenon_gate(xenon_quality_targets())
    thresholds = load_thresholds()
    findings = measure_complexity(targets, thresholds)
    if write:
        write_baseline(findings, targets)
        print_complexity_summary(findings, [])
        return
    regressions = compare_to_baseline(findings, load_baseline(), thresholds)
    print_complexity_summary(findings, regressions)
    if regressions:
        raise SystemExit(1)


def run_code_quality_audits() -> None:
    findings = collect_code_quality_findings(ROOT)
    blocks = [finding for finding in findings if finding.severity == "block"]
    warnings = [finding for finding in findings if finding.severity == "warn"]
    print(
        "Code quality findings: "
        f"warnings={len(warnings)} blocks={len(blocks)} "
        f"(module soft>{MODULE_SOFT_LINE_LIMIT}, hard>{MODULE_HARD_LINE_LIMIT}; class>{CLASS_LINE_LIMIT})"
    )
    for finding in [*blocks, *warnings][:80]:
        print(
            f"  {finding.severity.upper()} {finding.check} "
            f"{finding.location} - {finding.message}"
        )
    if len(findings) > 80:
        print(f"  ... {len(findings) - 80} more")
    if blocks:
        raise SystemExit(1)


def run_xenon_gate(paths: list[str]) -> None:
    targets = existing_paths(paths)
    if not targets:
        print("No Python files for Xenon.")
        return
    run(
        [
            "uv",
            "run",
            "xenon",
            "--no-assert",
            "--max-absolute",
            XENON_MAX_ABSOLUTE,
            "--max-modules",
            XENON_MAX_MODULES,
            "--max-average",
            XENON_MAX_AVERAGE,
            *targets,
        ]
    )


def resolve_tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    windows_name = f"{name}.exe"
    for tool_dir in LLVM_TOOL_DIRS:
        for candidate in (tool_dir / windows_name, tool_dir / name):
            if candidate.exists():
                return str(candidate)
    raise SystemExit(f"Required LLVM tool not found: {name}")


def native_source_files() -> list[str]:
    paths: list[str] = []
    for base in existing_paths(NATIVE_PATHS):
        for item in (ROOT / base).rglob("*"):
            if item.is_file() and item.suffix.lower() in NATIVE_EXTENSIONS:
                paths.append(item.relative_to(ROOT).as_posix())
    return sorted(dict.fromkeys(paths))


def compile_database_files(path: Path) -> set[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("compile_commands.json must be a list")
    files: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict) or "file" not in entry:
            continue
        files.add(normalize_path(str(entry["file"])))
    return files


def native_files_in_compile_database(
    native: list[str], compiled_files: set[str]
) -> tuple[list[str], list[str]]:
    compiled_native: list[str] = []
    missing: list[str] = []
    for path in native:
        if path in compiled_files:
            compiled_native.append(path)
        else:
            missing.append(path)
    return compiled_native, missing


def run_clang_tidy_for_native(
    clang_tidy: str, compile_db: Path, paths: list[str]
) -> None:
    for path in paths:
        run_native_command([clang_tidy, "-p", str(compile_db.parent), "--quiet", path])


def report_native_compile_database_coverage(
    compiled_native: list[str], missing: list[str]
) -> None:
    if missing:
        print("Native files not in CMake compile database:")
        for path in missing:
            print(f"  {path}")
    if not compiled_native:
        print("No repo native C/C++ files are present in the compile database.")


def run_native_checks() -> None:
    clang_tidy = resolve_tool("clang-tidy")
    run_native_command([clang_tidy, "--verify-config"])
    run_native_command(["cmake", "--fresh", "--preset", "llvm-release", "-S", "Utils"])
    compile_db = ROOT / "Utils" / "build" / "llvm-release" / "compile_commands.json"
    native = native_source_files()
    if native and compile_db.exists():
        compiled_files = compile_database_files(compile_db)
        compiled_native, missing = native_files_in_compile_database(
            native, compiled_files
        )
        run_clang_tidy_for_native(clang_tidy, compile_db, compiled_native)
        report_native_compile_database_coverage(compiled_native, missing)
    elif not native:
        print("No repo native C/C++ files for clang-tidy.")
    else:
        print("No compile database yet; skipping repo native clang-tidy.")
    run_native_command(["cmake", "--build", "Utils/build/llvm-release"])


def run_full_quality(*, skip_native: bool = False) -> None:
    run(["git", "status", "--short", "--branch"], check=False)
    run(["git", "diff", "--stat"], check=False)
    run(["git", "diff", "--cached", "--stat"], check=False)
    run(["uv", "sync", "--dev"])
    run(["uv", "run", "python", "-m", "unittest", "discover", "-s", "tests"])
    run(["uv", "run", "ruff", "check", *existing_paths(RUFF_LINT_PATHS)])
    run(["uv", "run", "ty", "check", *TY_BASELINE])
    changed = changed_python_files()
    run(["uv", "run", "ruff", "format", "--check", *format_check_targets(changed)])
    if changed:
        run(["uv", "run", "ty", "check", *changed])
    run(["git", "diff", "--check"])
    run_code_quality_audits()
    run_complexity_gate("all")
    if not skip_native:
        run_native_checks()
    run(["git", "status", "--short"], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Ortho4XP quality check.")
    parser.add_argument(
        "--complexity-only", action="store_true", help="Run only complexity checks."
    )
    parser.add_argument(
        "--scope",
        choices=("changed", "all"),
        default="all",
        help="Python file scope for complexity checks.",
    )
    parser.add_argument(
        "--write-complexity-baseline",
        action="store_true",
        help="Refresh the checked-in complexity baseline for the selected scope.",
    )
    parser.add_argument(
        "--skip-native", action="store_true", help="Skip LLVM/CMake native checks."
    )
    args = parser.parse_args()

    if args.complexity_only:
        run_complexity_gate(args.scope, write=args.write_complexity_baseline)
        return 0
    if args.write_complexity_baseline:
        run_complexity_gate(args.scope, write=True)
        return 0

    run_full_quality(skip_native=args.skip_native)
    return 0


def print_completed_output(proc: subprocess.CompletedProcess[str]) -> None:
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        end = "" if proc.stderr.endswith("\n") else "\n"
        print(proc.stderr, file=sys.stderr, end=end)


def run_native_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args))
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode:
        print_completed_output(proc)
        raise subprocess.CalledProcessError(
            proc.returncode, args, proc.stdout, proc.stderr
        )
    return proc


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
