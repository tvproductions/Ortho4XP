from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
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
from code_quality_targets import filter_changed_complexity_targets  # noqa: E402
from complexity_check import assess  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = Path(__file__).resolve().parents[1]
THRESHOLDS_PATH = SKILL_DIR / "complexity-thresholds.json"
BASELINE_PATH = SKILL_DIR / "complexity-baseline.json"
TY_BASELINE = ["tests", "src/O4_Geo_Utils.py", "src/O4_File_Names.py"]
RUFF_LINT_PATHS = [
    "Ortho4XP.py",
    "src",
    "tests",
    ".codex/skills/quality-check/scripts",
    ".codex/skills/repo-hygiene/scripts/hygiene.py",
    ".codex/skills/git-sync/scripts/git_sync.py",
    ".codex/skills/maintenance-qa/scripts",
    "scripts/check_skills_stack.py",
]
FORMAT_BASELINE = [
    ".codex/skills/quality-check/scripts",
    ".codex/skills/repo-hygiene/scripts/hygiene.py",
    ".codex/skills/git-sync/scripts/git_sync.py",
    ".codex/skills/maintenance-qa/scripts",
    "scripts/check_skills_stack.py",
]
NATIVE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
NATIVE_PATHS = ["Utils/src"]
NON_SOURCE_PYTHON_PATHS = {".codex/skills/maintenance-qa/vulture.whitelist.py"}
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
    return subprocess.run(  # noqa: S603
        args,
        cwd=ROOT,
        check=check,
        capture_output=capture,
        text=True,
        encoding="utf-8",
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


def python_paths(base: Path) -> list[str]:
    """Discover sources beneath one explicit repository scope."""
    candidates = [base] if base.is_file() else base.rglob("*.py")
    return [
        item.relative_to(ROOT).as_posix()
        for item in candidates
        if source_candidate(item)
    ]


def source_candidate(path: Path) -> bool:
    """Exclude cache files and the reviewed analyzer whitelist."""
    relative = path.relative_to(ROOT).as_posix()
    return "__pycache__" not in path.parts and relative not in NON_SOURCE_PYTHON_PATHS


def all_python_files() -> list[str]:
    """Include application, tests, project and maintained workflow sources."""
    scopes = existing_paths(["Ortho4XP.py", "src", "tests", "scripts", ".codex/skills"])
    paths = []
    for scope in scopes:
        paths.extend(python_paths(ROOT / scope))
    return sorted(set(paths))


def complexity_targets(scope: str) -> list[str]:
    if scope == "all":
        return all_python_files()
    return existing_paths(
        filter_changed_complexity_targets(
            changed_python_files(),
            all_python_files(),
            ".codex/skills/quality-check/scripts/quality_check.py",
        )
    )


def format_check_targets(changed: list[str]) -> list[str]:
    return existing_paths(list(dict.fromkeys([*changed, *FORMAT_BASELINE])))


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
    except OSError, ValueError:
        return path.replace("\\", "/")


def uv_tool(args: list[str]) -> subprocess.CompletedProcess[str]:
    return run(["uv", "run", "--group", "hygiene", *args], check=True, capture=True)


def lizard_data_row(row: list[str]) -> bool:
    """Ignore empty/header rows, never malformed data rows."""
    return bool(row) and row[0].strip().lower() != "nloc"


def parse_lizard_row(row: list[str]) -> dict[str, Any]:
    """Require every native CSV column, including the nesting extension."""
    if len(row) != 12:
        raise ValueError(f"Invalid Lizard CSV row: {row}")
    return {
        "path": normalize_path(row[6]),
        "name": row[8] or row[7],
        "line": int(row[9]),
        "nloc": float(row[0]),
        "ccn": float(row[1]),
        "params": float(row[3]),
        "nesting": float(row[11]),
    }


def lizard_row_findings(row: dict[str, Any], thresholds: dict) -> list[Finding]:
    """Apply the existing stricter thresholds to one complete function record."""
    values = (
        ("lizard_nloc", row["nloc"]),
        ("lizard_ccn", row["ccn"]),
        ("lizard_param_count", row["params"]),
        ("lizard_nesting_depth", row["nesting"]),
    )
    result = []
    for metric, value in values:
        finding = make_finding(
            thresholds, metric, row["path"], row["name"], value, row["line"]
        )
        if finding:
            result.append(finding)
    return result


def function_line(node: ast.AST) -> int | None:
    """Select exactly the AST function population, including nested/async definitions."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.lineno
    return None


def expected_functions(paths: list[str]) -> Counter:
    """Retain stable file/line identities for every source definition."""
    expected = Counter()
    for path in paths:
        expected.update(path_function_counter(path))
    return expected


def path_function_counter(path: str) -> Counter:
    """Count one original source's function locations without a synthetic denominator."""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
    lines = filter(None, map(function_line, ast.walk(tree)))
    return Counter((normalize_path(path), line) for line in lines)


def measure_lizard(paths: list[str], thresholds: dict) -> list[Finding]:
    """Refuse missing functions or nesting columns; retain partial evidence on errors."""
    proc = uv_tool(["lizard", "-End", "--csv", *paths])
    rows = list(
        map(
            parse_lizard_row, filter(lizard_data_row, csv.reader(StringIO(proc.stdout)))
        )
    )
    findings = []
    for row in rows:
        findings.extend(lizard_row_findings(row, thresholds))
    actual = Counter((row["path"], row["line"]) for row in rows)
    expected = expected_functions(paths)
    if actual != expected:
        message = f"Lizard CSV function population mismatch: missing={dict(expected - actual)}, extra={dict(actual - expected)}"
        raise MeasurementError(message, findings)
    return findings


def cohesion_percentage(line: str, identity: dict[str, str]) -> Finding:
    """Keep the analyzer's native percentage without clipping or translating it."""
    if not {"path", "name"} <= identity.keys():
        raise ValueError("Cohesion percentage without file/class identity")
    value = float(line.removeprefix("Total: ").removesuffix("%"))
    return Finding(
        "cohesion_policy_unverified", identity["path"], identity["name"], value, "block"
    )


def cohesion_record(line: str, identity: dict[str, str]) -> Finding | None:
    """Parse one line without losing original file/class identities."""
    line = line.strip()
    if line.startswith("File: "):
        identity["path"] = normalize_path(line.removeprefix("File: "))
    elif line.startswith("Class: "):
        identity["name"] = line.removeprefix("Class: ").rsplit(" (", 1)[0]
    elif line.startswith("Total: "):
        return cohesion_percentage(line, identity)
    return None


def measure_cohesion(paths: list[str], thresholds: dict) -> list[Finding]:
    """Preserve real percentages; unsupported historical LCOM4 policy stays blocked."""
    proc = uv_tool(["cohesion", "-f", *paths])
    findings = []
    identity = {}
    for line in proc.stdout.splitlines():
        record = cohesion_record(line, identity)
        if record is not None:
            findings.append(record)
    print(
        f"Cohesion percentage policy unverified: {len(findings)} class measurements retained."
    )
    return findings


class MeasurementError(ValueError):
    """Retain partial measurements while preventing an analyzer error from passing."""

    def __init__(self, message: str, findings: list[Finding]) -> None:
        super().__init__(message)
        self.findings = findings


def analyzer_findings(
    analyzer, paths: list[str], thresholds: dict
) -> tuple[list[Finding], str | None]:
    """Preserve partial evidence when discovery or tool execution fails."""
    try:
        return analyzer(paths, thresholds), None
    except MeasurementError as error:
        return error.findings, f"{analyzer.__name__}: {error}"
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        return [], f"{analyzer.__name__}: {error}"


def measure_complexity(paths: list[str], thresholds: dict) -> list[Finding]:
    """Run both retained analyzers independently without waiving partial failures."""
    findings, errors = [], []
    for analyzer in (measure_lizard, measure_cohesion):
        items, message = analyzer_findings(analyzer, paths, thresholds)
        findings.extend(items)
        errors.append(message)
    errors = list(filter(None, errors))
    if errors:
        raise MeasurementError("; ".join(errors), findings)
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
    return (finding.metric, finding.path, stable_finding_name(finding.name))


def stable_finding_name(name: str) -> str:
    if "(" not in name:
        return name
    return name.split("(", 1)[0].strip()


def baseline_by_stable_key(
    baseline: dict[str, dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for prior in baseline.values():
        if not {"metric", "path", "name"} <= set(prior):
            continue
        key = (
            str(prior["metric"]),
            str(prior["path"]),
            stable_finding_name(str(prior["name"])),
        )
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


def complexity_report_directory(targets: list[str]) -> Path:
    """Reject empty measurement scope and allocate a retained receipt."""
    if not targets:
        raise SystemExit("No Python sources selected for complexity measurement")
    (ROOT / "tmp").mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="complexity-hygiene-", dir=ROOT / "tmp"))


def ceiling_commands(targets: list[str], report: Path) -> list[list[str]]:
    """Keep the independent cyclomatic and cognitive ceilings explicit."""
    ruff = [
        "ruff",
        "check",
        "--select",
        "C901",
        "--ignore-noqa",
        "--config",
        "lint.mccabe.max-complexity=20",
        *targets,
    ]
    cognitive = ["complexipy", *targets, "--cache-dir", str(report / "cache")]
    cognitive += ["--output-format", "json", "--output", str(report / "cognitive.json")]
    return [ruff, cognitive]


def record_ceiling_command(command: list[str], path: Path) -> bool:
    """Retain analyzer output and return its actual failure state."""
    proc = run(["uv", "run", "--group", "hygiene", *command], check=False, capture=True)
    path.write_text(proc.stdout + proc.stderr, encoding="utf-8")
    print_completed_output(proc)
    return proc.returncode != 0


def absolute_complexity(targets: list[str], report: Path) -> tuple[bool, list[str]]:
    """Run all three tools even when an independent measurement fails."""
    results = [
        record_ceiling_command(command, report / f"analyzer-{index}.txt")
        for index, command in enumerate(ceiling_commands(targets, report))
    ]
    receipt = assess(ROOT, targets)
    (report / "lizard.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Lizard contract: {receipt['status']}; aggregate={receipt['aggregate']}; errors={receipt['errors']}"
    )
    return any(results) or receipt["status"] != "passed", receipt["errors"]


def ratchet_findings(
    targets: list[str], thresholds: dict
) -> tuple[list[Finding], list[str]]:
    """Return partial measurements distinctly from valid legacy findings."""
    try:
        return measure_complexity(targets, thresholds), []
    except MeasurementError as error:
        print(f"Complexity measurement error: {error}")
        return error.findings, [str(error)]


def record_ratchet(
    report: Path,
    findings: list[Finding],
    regressions: list[Regression],
    errors: list[str],
) -> None:
    """Retain all identities, scores, regressions and measurement errors."""
    payload = {
        "errors": errors,
        "findings": list(map(asdict, findings)),
        "regressions": list(map(asdict, regressions)),
    }
    (report / "ratchet.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def ratchet_assessment(
    targets: list[str], report: Path
) -> tuple[list[Finding], list[Regression], list[str]]:
    """Apply the unchanged project ratchet to every retained native measurement."""
    thresholds = load_thresholds()
    findings, errors = ratchet_findings(targets, thresholds)
    regressions = compare_to_baseline(findings, load_baseline(), thresholds)
    record_ratchet(report, findings, regressions, errors)
    return findings, regressions, errors


def refresh_complexity_baseline(
    scope_targets: tuple[str, list[str]],
    findings: list[Finding],
    regressions: list[Regression],
    errors: list,
) -> None:
    """Allow only full, complete assessments whose baseline identities shrink."""
    scope, targets = scope_targets
    prior = baseline_by_stable_key(load_baseline())
    added = [
        finding for finding in findings if stable_finding_key(finding) not in prior
    ]
    if scope != "all" or regressions or added or errors:
        raise SystemExit(
            "Baseline may only shrink after a complete full-scope regression check"
        )
    write_baseline(findings, targets)


def run_complexity_gate(scope: str, *, write: bool = False) -> None:
    """Run every independent analyzer; snapshots never waive absolute failures."""
    targets = complexity_targets(scope)
    report = complexity_report_directory(targets)
    failed, errors = absolute_complexity(targets, report)
    findings, regressions, measurement_errors = ratchet_assessment(targets, report)
    errors.extend(measurement_errors)
    if write:
        refresh_complexity_baseline((scope, targets), findings, regressions, errors)
    print_assessment(findings, regressions, errors, report)
    if failed or regressions or errors:
        raise SystemExit(1)


def print_assessment(
    findings: list, regressions: list, errors: list, report: Path
) -> None:
    """Do not report baseline success when any analyzer lacks complete evidence."""
    if errors:
        print(
            f"Complexity assessment incomplete: {len(errors)} measurement errors; baseline cannot pass."
        )
    else:
        print_complexity_summary(findings, regressions)
    print(f"Detailed complexity receipts: {report.relative_to(ROOT).as_posix()}")


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
    run(["uv", "run", "python", "scripts/check_skills_stack.py"])
    run(["uv", "run", "python", "-m", "unittest", "discover", "-s", "tests"])
    run(["uv", "run", "ruff", "check", *existing_paths(RUFF_LINT_PATHS)])
    run(["uv", "run", "ty", "check", *TY_BASELINE])
    changed = changed_python_files()
    run(["uv", "run", "ruff", "format", "--check", *format_check_targets(changed)])
    if changed:
        run(["uv", "run", "ty", "check", *changed])
    run(["git", "diff", "--check"])
    run_code_quality_audits()
    if not skip_native:
        run_native_checks()
    run(["git", "status", "--short"], check=False)


def run_typecheck() -> None:
    """Check the reviewed baseline and every changed Python source."""
    run(["uv", "run", "ty", "check", *TY_BASELINE])
    changed = changed_python_files()
    if changed:
        run(["uv", "run", "ty", "check", *changed])


def run_format_check() -> None:
    """Verify changed sources and maintained skill scripts without mass formatting."""
    run(
        [
            "uv",
            "run",
            "ruff",
            "format",
            "--check",
            *format_check_targets(changed_python_files()),
        ]
    )


def configure_console() -> None:
    """Use UTF-8 for tool receipts and captured Windows console output."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def add_complexity_options(parser: argparse.ArgumentParser) -> None:
    """Expose deep analysis only through explicit command flags."""
    parser.add_argument(
        "--complexity-only",
        action="store_true",
        help="Run only explicit complexity checks.",
    )
    parser.add_argument(
        "--scope",
        choices=("changed", "all"),
        default="all",
        help="Python source scope for complexity.",
    )
    parser.add_argument(
        "--write-complexity-baseline",
        action="store_true",
        help="Shrink the existing complexity baseline after complete assessment.",
    )


def quality_parser() -> argparse.ArgumentParser:
    """Describe routine checks and pre-commit adapters separately from deep analysis."""
    parser = argparse.ArgumentParser(description="Run the Ortho4XP quality check.")
    parser.add_argument(
        "--lint-only",
        action="store_true",
        help="Run the reviewed routine Ruff scope for pre-commit.",
    )
    parser.add_argument(
        "--typecheck-only",
        action="store_true",
        help="Run baseline and changed-file ty for pre-commit.",
    )
    parser.add_argument(
        "--format-only",
        action="store_true",
        help="Run changed-file and script formatting for pre-commit.",
    )
    parser.add_argument(
        "--skip-native", action="store_true", help="Skip LLVM/CMake native checks."
    )
    add_complexity_options(parser)
    return parser


def main() -> int:
    """Run explicit requested checks with UTF-8 output on every platform."""
    configure_console()
    args = quality_parser().parse_args()
    if run_requested_adapter(args):
        return 0
    if requested_complexity(args):
        run_complexity_gate(args.scope, write=args.write_complexity_baseline)
        return 0
    run_full_quality(skip_native=args.skip_native)
    return 0


def run_requested_adapter(args: argparse.Namespace) -> bool:
    """Run one explicitly requested routine hook adapter."""
    if args.lint_only:
        run(["uv", "run", "ruff", "check", *existing_paths(RUFF_LINT_PATHS)])
        return True
    if args.typecheck_only:
        run_typecheck()
        return True
    if args.format_only:
        run_format_check()
        return True
    return False


def requested_complexity(args: argparse.Namespace) -> bool:
    """Keep explicit analysis selection independent of routine orchestration."""
    return args.complexity_only or args.write_complexity_baseline


def print_completed_output(proc: subprocess.CompletedProcess[str]) -> None:
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        end = "" if proc.stderr.endswith("\n") else "\n"
        print(proc.stderr, file=sys.stderr, end=end)


def run_native_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args))
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)  # noqa: S603
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
