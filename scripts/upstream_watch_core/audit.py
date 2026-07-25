"""Deterministic audit reports that never execute upstream repository content."""

from __future__ import annotations

import ast
import fnmatch
import json
import os
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from .git_repo import (
    GitCommandError,
    GitRunner,
    classify_author_history,
    list_changes,
    list_commits,
    read_blob,
)
from .models import (
    AuditReport,
    ChangeStatus,
    InspectionResult,
    ReportValidationError,
    WatchExit,
    WatchState,
    canonical_json_bytes,
    validate_sha,
)


class AuditGenerationError(RuntimeError):
    """Raised when a report cannot be generated reproducibly."""


def inspect_python_blob(path: str, blob: bytes) -> InspectionResult:
    """Parse Python source as data, recording syntax problems without execution."""

    try:
        source = blob.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return InspectionResult(
            path=path,
            syntax_ok=False,
            syntax_error=f"source is not UTF-8: {exc}",
            signals=(),
        )
    try:
        ast.parse(source, filename=path)
    except SyntaxError as exc:
        detail = exc.msg or "invalid syntax"
        if exc.lineno is not None:
            detail = f"{detail} at line {exc.lineno}"
        return InspectionResult(
            path=path,
            syntax_ok=False,
            syntax_error=detail,
            signals=classify_change_signals(path, blob),
        )
    return InspectionResult(
        path=path,
        syntax_ok=True,
        syntax_error=None,
        signals=classify_change_signals(path, blob),
    )


def classify_change_signals(path: str, blob: bytes) -> tuple[str, ...]:
    """Extract review signals from source text without interpreting it."""

    try:
        text = blob.decode("utf-8-sig").casefold()
    except UnicodeDecodeError:
        return ()
    signals: set[str] = set()
    compact = " ".join(text.replace("_", " ").replace("-", " ").split())
    if (
        "xp11 + bathy" in compact
        or "xp11+bathy" in text
        or ("xp11" in compact and "bathy" in compact)
    ):
        signals.add("xp11-bathy")
    if "x-plane 11" in text or "xplane 11" in compact or "xp11" in compact:
        signals.add("xp11")
    if "x-plane 12" in text or "xplane 12" in compact or "xp12" in compact:
        signals.add("xp12")
    if path.startswith("Providers/"):
        signals.add("provider-data")
    return tuple(sorted(signals))


def build_audit_report(
    state: WatchState,
    base_sha: str,
    head_sha: str,
    generated_at: str,
    runner: GitRunner,
    *,
    ruff_executable: str | None = None,
) -> AuditReport:
    """Build an explicit-SHA audit manifest from a fetched local Git repository."""

    validate_sha(base_sha, "base_sha")
    validate_sha(head_sha, "head_sha")
    author_status = classify_author_history(runner, base_sha, head_sha)
    ancestry = {
        WatchExit.CURRENT: "equal",
        WatchExit.REVIEW_REQUIRED: "fast-forward",
        WatchExit.HISTORY_REWRITE: "rewritten",
    }.get(author_status)
    if ancestry is None:
        raise AuditGenerationError("Could not classify authoritative history")

    changes = list_changes(runner, base_sha, head_sha)
    inspections: list[InspectionResult] = []
    compatibility_signals: set[str] = set()
    python_blobs: dict[str, bytes] = {}
    for change in changes:
        if change.status is ChangeStatus.DELETED:
            continue
        try:
            blob = read_blob(runner, head_sha, change.path)
        except GitCommandError as exc:
            raise AuditGenerationError(
                f"Could not read changed blob {change.path}"
            ) from exc
        compatibility_signals.update(classify_change_signals(change.path, blob))
        if change.path.casefold().endswith(".py"):
            python_blobs[change.path] = blob
            inspections.append(inspect_python_blob(change.path, blob))

    report = AuditReport(
        schema_version=1,
        audit_id=f"ypsos-{base_sha[:12]}-{head_sha[:12]}",
        base_sha=base_sha,
        head_sha=head_sha,
        generated_at=generated_at,
        ancestry=ancestry,
        commits=list_commits(runner, base_sha, head_sha),
        changes=changes,
        inspections=tuple(sorted(inspections, key=lambda item: item.path)),
        dependency_changes=tuple(
            sorted(
                change.path for change in changes if _is_dependency_path(change.path)
            )
        ),
        provider_changes=tuple(
            sorted(
                change.path
                for change in changes
                if change.path.startswith("Providers/")
            )
        ),
        compatibility_signals=tuple(sorted(compatibility_signals)),
        inspection_tools={"ruff": _run_targeted_ruff(python_blobs, ruff_executable)},
    )
    # Round-trip through validation so constructed reports obey the file contract.
    return AuditReport.from_dict(report.to_dict())


def _is_dependency_path(path: str) -> bool:
    name = PurePosixPath(path).name.casefold()
    return (
        name in {"pyproject.toml", "uv.lock"}
        or fnmatch.fnmatch(name, "requirements*.txt")
        or fnmatch.fnmatch(name, "environment*.yml")
        or fnmatch.fnmatch(name, "environment*.yaml")
    )


def _run_targeted_ruff(
    python_blobs: dict[str, bytes], executable: str | None
) -> dict[str, object]:
    if executable is None:
        return {"available": False, "findings": []}
    with tempfile.TemporaryDirectory(prefix="ortho4xp-upstream-ruff-") as temporary:
        root = Path(temporary)
        materialized: dict[Path, str] = {}
        for index, (relative, blob) in enumerate(sorted(python_blobs.items())):
            target = root / f"{index:04d}.py"
            target.write_bytes(blob)
            materialized[target.resolve()] = relative
        try:
            result = subprocess.run(  # noqa: S603 - fixed Ruff argument contract.
                [
                    executable,
                    "check",
                    "--no-cache",
                    "--output-format=json",
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                stdin=subprocess.DEVNULL,
            )
        except (OSError, UnicodeError) as exc:
            raise AuditGenerationError(
                "Could not execute targeted Ruff analysis"
            ) from exc
    if result.returncode not in {0, 1}:
        raise AuditGenerationError(
            f"Targeted Ruff analysis failed with status {result.returncode}"
        )
    try:
        findings = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AuditGenerationError("Targeted Ruff returned malformed JSON") from exc
    if not isinstance(findings, list):
        raise AuditGenerationError("Targeted Ruff returned a non-array result")
    sanitized: list[dict[str, object]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise AuditGenerationError("Targeted Ruff returned an invalid finding")
        filename = finding.get("filename")
        if isinstance(filename, str):
            try:
                finding = dict(finding)
                finding["filename"] = materialized[Path(filename).resolve()]
            except KeyError as exc:
                raise AuditGenerationError(
                    "Targeted Ruff returned an unknown materialized path"
                ) from exc
        sanitized.append(finding)
    return {"available": True, "findings": sanitized}


def write_report(path: Path, report: AuditReport) -> None:
    """Write canonical report JSON atomically, retaining no partial output."""

    # Revalidate before persistence, including caller-constructed dataclasses.
    validated = AuditReport.from_dict(report.to_dict())
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(canonical_json_bytes(validated.to_dict()))
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    except OSError as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise AuditGenerationError(f"Could not write report {path.name}") from exc


def manifest_sha256(report: AuditReport) -> str:
    """Compatibility function for callers that prefer a module-level helper."""

    try:
        return report.manifest_sha256()
    except (ReportValidationError, TypeError, ValueError) as exc:
        raise AuditGenerationError("Could not digest audit manifest") from exc
