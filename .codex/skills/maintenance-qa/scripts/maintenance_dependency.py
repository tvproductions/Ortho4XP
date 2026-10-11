"""Audit lock-exported identities without introducing a second resolver."""

import hashlib
import json
import tempfile
import tomllib
from pathlib import Path

from maintenance_common import ROOT, run_command
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

HYGIENE = ["uv", "run", "--group", "hygiene"]


def audit_directory() -> Path:
    """Allocate a retained task-specific receipt directory."""
    (ROOT / "tmp").mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="dependency-hygiene-", dir=ROOT / "tmp"))


def export_lock(path: Path) -> tuple[int, str, str]:
    """Export all locked groups without invoking a second resolver."""
    command = [
        "uv",
        "export",
        "--locked",
        "--all-groups",
        "--format",
        "requirements.txt",
    ]
    command += ["--no-emit-project", "--no-emit-local", "--output-file", str(path)]
    return run_command(command)


def local_requirement(package: dict) -> str:
    """Record an exact local wheel identity and the hash of reviewed source bytes."""
    wheel = package.get("source", {}).get("path", "")
    if not wheel.endswith(".whl"):
        return ""
    digest = hashlib.sha256((ROOT / wheel).read_bytes()).hexdigest()
    identity = f"{package['name']}=={package['version']} --hash=sha256:{digest}"
    return f"# Local wheel: {wheel}\n{identity}\n"


def append_local_wheels(path: Path) -> None:
    """Preserve index hashes and append local identities from the same lock."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    additions = "".join(map(local_requirement, lock["package"]))
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n" + additions)


def exported_requirement(line: str) -> Requirement | None:
    """Read one physical identity line, excluding annotations and hash continuations."""
    line = line.strip()
    if not line or line.startswith(("#", "--")):
        return None
    return Requirement(line.split(" --hash=", 1)[0].rstrip("\\").strip())


def host_identity(requirement: Requirement | None) -> tuple[str, str] | None:
    """Select the current host's exact pin and reject non-exact exports."""
    if requirement is None:
        return None
    if requirement.marker is not None and not requirement.marker.evaluate():
        return None
    pins = list(requirement.specifier)
    if len(pins) != 1 or pins[0].operator != "==":
        raise ValueError(f"Non-exact exported identity: {requirement}")
    return canonicalize_name(requirement.name), pins[0].version


def exported_identities(path: Path) -> set[tuple[str, str]]:
    """Require a complete independently derived expected audit population."""
    requirements = map(
        exported_requirement, path.read_text(encoding="utf-8").splitlines()
    )
    return set(filter(None, map(host_identity, requirements)))


def audit_population(dependencies: list[dict]) -> tuple[set, int, list]:
    """Account for exact identities, advisories and skipped packages separately."""
    audited = set()
    vulnerabilities = 0
    skipped = []
    for item in dependencies:
        audited.add((canonicalize_name(item["name"]), item.get("version")))
        vulnerabilities += len(item.get("vulns", []))
        if "skip_reason" in item:
            skipped.append(item)
    return audited, vulnerabilities, skipped


def classify_audit(
    expected: set, code: int, stdout: str, stderr: str
) -> tuple[str, str]:
    """Reject failed, malformed, empty or incomplete advisory measurements."""
    if code not in (0, 1):
        return "FAIL", f"pip-audit execution error: {stderr[:300]}"
    try:
        dependencies = json.loads(stdout)["dependencies"]
        audited, vulnerabilities, skipped = audit_population(dependencies)
    except ValueError, KeyError, TypeError:
        return "FAIL", "Invalid pip-audit report"
    return assessed_population(
        expected, audited, code, (dependencies, vulnerabilities, skipped)
    )


def assessed_population(
    expected: set, audited: set, code: int, receipt: tuple
) -> tuple[str, str]:
    """Reject incomplete identities before classifying security findings."""
    dependencies, vulnerabilities, skipped = receipt
    if not expected or audited != expected:
        return (
            "FAIL",
            f"Audited identity mismatch: missing={expected - audited}; extra={audited - expected}",
        )
    status = "FAIL" if audit_failed(code, vulnerabilities, skipped) else "PASS"
    details = f"Host-selected {len(dependencies)} identities; {vulnerabilities} advisories; {len(skipped)} skipped"
    return status, details


def audit_failed(code: int, vulnerabilities: int, skipped: list) -> bool:
    """Preserve tool, advisory and incomplete-population failure dimensions."""
    return bool(code or vulnerabilities or skipped)


def audit_export(path: Path) -> tuple[str, str]:
    """Audit and retain the same exact exported population."""
    expected = exported_identities(path)
    command = [*HYGIENE, "pip-audit", "-r", str(path)]
    command += ["--no-deps", "--disable-pip", "--format", "json"]
    code, stdout, stderr = run_command(command)
    (path.parent / "audit.json").write_text(stdout, encoding="utf-8")
    status, details = classify_audit(expected, code, stdout, stderr)
    return status, f"{details}; receipt {path.parent.relative_to(ROOT)}"


def check_dependency_cves() -> tuple[str, str]:
    """Audit the host-selected runtime/dev/hygiene resolution with pip-audit."""
    exported = audit_directory() / "requirements.txt"
    code, stdout, stderr = export_lock(exported)
    if code:
        return "FAIL", f"Lock export failed: {stdout + stderr}"
    append_local_wheels(exported)
    return audit_export(exported)


def check_dependency_usage() -> tuple[str, str]:
    """Assess active-source metadata, preserving dynamic consumers and archives."""
    command = [*HYGIENE, "deptry", "src", "--config", "pyproject.toml"]
    command += [
        "--known-first-party",
        "Ortho4XP",
        "--extend-exclude",
        r"^(?:src[/\\])?Unused[/\\]",
        "--no-ansi",
    ]
    command += [
        "--package-module-name-map",
        "gdal=osgeo,scikit-fmm=skfmm,pillow=PIL,rtree=rtree",
    ]
    code, stdout, stderr = run_command(command)
    return ("PASS" if code == 0 else "FAIL"), (
        "No dependency usage findings" if code == 0 else (stdout + stderr)[-700:]
    )


def check_import_boundaries() -> tuple[str, str]:
    """Run standard forbidden contracts on the actual flat-module import graph."""
    adapter = ROOT / ".codex/skills/maintenance-qa/scripts/maintenance_import_graph.py"
    code, stdout, stderr = run_command([*HYGIENE, "python", str(adapter)])
    return ("PASS" if code == 0 else "FAIL"), (stdout + stderr)[-700:]
