"""Structured audit-ledger validation and atomic baseline advancement."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .models import (
    AcceptedBaseline,
    AuditReport,
    ChangeStatus,
    Disposition,
    FindingRecord,
    PathChange,
    ReviewedNoActionRecord,
    WatchState,
    canonical_json_bytes,
    load_state,
    validate_sha,
)

_AUDIT_PREFIX = "<!-- upstream-watch:audit "
_FINDING_PREFIX = "<!-- upstream-watch:finding "
_NO_ACTION_PREFIX = "<!-- upstream-watch:reviewed-no-action "
_SUFFIX = " -->"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_WORK_ITEM_RE = re.compile(
    r"(?:TODO-[0-9-]+|#[0-9]+|https://github\.com/[^/\s]+/[^/\s]+/issues/[0-9]+)"
)


class LedgerValidationError(ValueError):
    """Raised when ledger evidence cannot authorize a state transition."""


@dataclass(frozen=True, slots=True)
class LedgerAuditRecord:
    audit_id: str
    base_sha: str
    head_sha: str
    manifest_sha256: str
    path_count: int


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    audit: LedgerAuditRecord
    findings: tuple[FindingRecord, ...]
    reviewed_no_action: tuple[ReviewedNoActionRecord, ...]


@dataclass(frozen=True, slots=True)
class CoverageResult:
    covered_paths: frozenset[str]
    blocking_findings: tuple[str, ...]


def parse_ledger(path: Path) -> tuple[LedgerEntry, ...]:
    """Parse exact structured comments while leaving narrative Markdown inert."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise LedgerValidationError(f"Could not read ledger {path.name}") from exc

    audits: dict[str, LedgerAuditRecord] = {}
    findings: dict[str, list[FindingRecord]] = {}
    no_actions: dict[str, list[ReviewedNoActionRecord]] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.startswith("<!-- upstream-watch:"):
            continue
        if line.startswith(_AUDIT_PREFIX):
            payload = _parse_payload(line, _AUDIT_PREFIX, line_number)
            record = _parse_audit(payload)
            if record.audit_id in audits:
                raise LedgerValidationError(
                    f"duplicate audit record {record.audit_id!r}"
                )
            audits[record.audit_id] = record
        elif line.startswith(_FINDING_PREFIX):
            payload = _parse_payload(line, _FINDING_PREFIX, line_number)
            record = _parse_finding(payload)
            findings.setdefault(record.audit_id, []).append(record)
        elif line.startswith(_NO_ACTION_PREFIX):
            payload = _parse_payload(line, _NO_ACTION_PREFIX, line_number)
            record = _parse_no_action(payload)
            no_actions.setdefault(record.audit_id, []).append(record)
        else:
            raise LedgerValidationError(
                f"unknown upstream-watch record at line {line_number}"
            )
    unknown_audits = (findings.keys() | no_actions.keys()) - audits.keys()
    if unknown_audits:
        raise LedgerValidationError(
            "records reference missing audits: " + ", ".join(sorted(unknown_audits))
        )
    entries = tuple(
        LedgerEntry(
            audit=audit,
            findings=tuple(findings.get(audit_id, [])),
            reviewed_no_action=tuple(no_actions.get(audit_id, [])),
        )
        for audit_id, audit in audits.items()
    )
    if not entries:
        raise LedgerValidationError("ledger contains no upstream-watch audit records")
    return entries


def _parse_payload(line: str, prefix: str, line_number: int) -> dict[str, object]:
    if not line.endswith(_SUFFIX):
        raise LedgerValidationError(
            f"malformed upstream-watch record at line {line_number}"
        )
    encoded = line[len(prefix) : -len(_SUFFIX)]
    try:
        payload = json.loads(encoded)
    except json.JSONDecodeError as exc:
        raise LedgerValidationError(
            f"invalid JSON in upstream-watch record at line {line_number}"
        ) from exc
    if not isinstance(payload, dict) or any(
        not isinstance(key, str) for key in payload
    ):
        raise LedgerValidationError(
            f"upstream-watch record at line {line_number} must be an object"
        )
    return payload


def _exact_keys(
    payload: dict[str, object], expected: set[str], record_type: str
) -> None:
    missing = expected - payload.keys()
    unknown = payload.keys() - expected
    if missing:
        raise LedgerValidationError(
            f"{record_type} is missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise LedgerValidationError(
            f"{record_type} has unknown fields: {', '.join(sorted(unknown))}"
        )


def _text(value: object, field: str, *, maximum: int = 8192) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 32 for character in value)
    ):
        raise LedgerValidationError(f"{field} must be a nonempty safe string")
    return value


def _sha(value: object, field: str) -> str:
    try:
        return validate_sha(value, field)
    except ValueError as exc:
        raise LedgerValidationError(str(exc)) from exc


def _path(value: object, field: str) -> str:
    try:
        return PathChange.from_dict(
            {
                "path": value,
                "status": ChangeStatus.MODIFIED.value,
                "previous_path": None,
                "additions": None,
                "deletions": None,
            }
        ).path
    except ValueError as exc:
        raise LedgerValidationError(f"{field} is invalid: {exc}") from exc


def _audit_id(value: object) -> str:
    return _text(value, "audit_id", maximum=128)


def _parse_audit(payload: dict[str, object]) -> LedgerAuditRecord:
    _exact_keys(
        payload,
        {"audit_id", "base_sha", "head_sha", "manifest_sha256", "path_count"},
        "audit record",
    )
    digest = payload["manifest_sha256"]
    if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
        raise LedgerValidationError("audit manifest_sha256 must be a SHA-256 digest")
    path_count = payload["path_count"]
    if (
        isinstance(path_count, bool)
        or not isinstance(path_count, int)
        or path_count < 0
    ):
        raise LedgerValidationError("audit path_count must be a nonnegative integer")
    return LedgerAuditRecord(
        audit_id=_audit_id(payload["audit_id"]),
        base_sha=_sha(payload["base_sha"], "audit.base_sha"),
        head_sha=_sha(payload["head_sha"], "audit.head_sha"),
        manifest_sha256=digest,
        path_count=path_count,
    )


def _parse_finding(payload: dict[str, object]) -> FindingRecord:
    _exact_keys(
        payload,
        {
            "audit_id",
            "finding_id",
            "paths",
            "disposition",
            "rationale",
            "work_items",
            "xp12_compatibility",
        },
        "finding record",
    )
    finding_id = _text(payload["finding_id"], "finding_id", maximum=128)
    raw_paths = payload["paths"]
    if not isinstance(raw_paths, list) or not raw_paths:
        raise LedgerValidationError(f"finding {finding_id!r} paths must be nonempty")
    paths = tuple(_path(item, f"finding {finding_id!r} path") for item in raw_paths)
    if len(paths) != len(set(paths)):
        raise LedgerValidationError(f"finding {finding_id!r} has duplicate paths")
    try:
        disposition = Disposition(payload["disposition"])
    except (TypeError, ValueError) as exc:
        raise LedgerValidationError(
            f"finding {finding_id!r} has an unknown disposition"
        ) from exc
    rationale = _text(payload["rationale"], f"finding {finding_id!r} rationale")
    xp12 = _text(
        payload["xp12_compatibility"],
        f"finding {finding_id!r} xp12_compatibility",
    )
    raw_work_items = payload["work_items"]
    if not isinstance(raw_work_items, list):
        raise LedgerValidationError(
            f"finding {finding_id!r} work_items must be an array"
        )
    work_items = tuple(
        _text(item, f"finding {finding_id!r} work item", maximum=1024)
        for item in raw_work_items
    )
    if len(work_items) != len(set(work_items)):
        raise LedgerValidationError(f"finding {finding_id!r} has duplicate work items")
    if disposition in {Disposition.ADOPT, Disposition.REIMPLEMENT} and not any(
        _WORK_ITEM_RE.search(item) for item in work_items
    ):
        raise LedgerValidationError(
            f"finding {finding_id!r} accepted work requires a TODO or GitHub Issue link"
        )
    return FindingRecord(
        finding_id=finding_id,
        audit_id=_audit_id(payload["audit_id"]),
        paths=paths,
        disposition=disposition,
        rationale=rationale,
        work_items=work_items,
        xp12_compatibility=xp12,
    )


def _parse_no_action(payload: dict[str, object]) -> ReviewedNoActionRecord:
    _exact_keys(
        payload,
        {"audit_id", "path", "rationale"},
        "reviewed-no-action record",
    )
    return ReviewedNoActionRecord(
        audit_id=_audit_id(payload["audit_id"]),
        path=_path(payload["path"], "reviewed-no-action path"),
        rationale=_text(payload["rationale"], "reviewed-no-action rationale"),
    )


def validate_coverage(report: AuditReport, entry: LedgerEntry) -> CoverageResult:
    """Require every changed path to have one and only one disposition record."""

    if entry.audit.audit_id != report.audit_id:
        raise LedgerValidationError("ledger audit_id does not match report")
    expected = {change.path for change in report.changes}
    assigned: dict[str, str] = {}
    blocking: list[str] = []
    finding_ids: set[str] = set()
    for finding in entry.findings:
        if finding.finding_id in finding_ids:
            raise LedgerValidationError(
                f"duplicate finding identifier {finding.finding_id!r}"
            )
        finding_ids.add(finding.finding_id)
        if finding.audit_id != report.audit_id:
            raise LedgerValidationError(
                f"finding {finding.finding_id!r} references another audit"
            )
        for path in finding.paths:
            if path in assigned:
                raise LedgerValidationError(f"duplicate path coverage for {path!r}")
            assigned[path] = finding.finding_id
        if finding.disposition is Disposition.INVESTIGATE:
            blocking.append(finding.finding_id)
    for record in entry.reviewed_no_action:
        if record.audit_id != report.audit_id:
            raise LedgerValidationError(
                f"reviewed-no-action path {record.path!r} references another audit"
            )
        if record.path in assigned:
            raise LedgerValidationError(f"duplicate path coverage for {record.path!r}")
        assigned[record.path] = "reviewed-no-action"
    unknown = set(assigned) - expected
    if unknown:
        raise LedgerValidationError(
            "unknown paths in ledger: " + ", ".join(sorted(unknown))
        )
    missing = expected - set(assigned)
    if missing:
        raise LedgerValidationError(
            "missing path coverage: " + ", ".join(sorted(missing))
        )
    return CoverageResult(
        covered_paths=frozenset(assigned), blocking_findings=tuple(sorted(blocking))
    )


def validate_state_transition(
    state: WatchState, report: AuditReport, entry: LedgerEntry
) -> CoverageResult:
    """Validate immutable evidence and reject unresolved investigations."""

    coverage = validate_evidence(state, report, entry)
    if coverage.blocking_findings:
        raise LedgerValidationError(
            "investigate findings block baseline advancement: "
            + ", ".join(coverage.blocking_findings)
        )
    return coverage


def validate_evidence(
    state: WatchState, report: AuditReport, entry: LedgerEntry
) -> CoverageResult:
    """Validate a report and ledger while retaining investigate blockers as data."""

    if state.baseline.reviewed_sha != report.base_sha:
        raise LedgerValidationError("report base does not match accepted baseline")
    audit = entry.audit
    if audit.audit_id != report.audit_id:
        raise LedgerValidationError("ledger audit_id does not match report")
    if audit.base_sha != report.base_sha or audit.head_sha != report.head_sha:
        raise LedgerValidationError("ledger SHA range does not match report")
    if audit.manifest_sha256 != report.manifest_sha256():
        raise LedgerValidationError("ledger manifest digest does not match report")
    if audit.path_count != len(report.changes):
        raise LedgerValidationError("ledger path_count does not match report")
    return validate_coverage(report, entry)


def advance_baseline(
    state_path: Path,
    report: AuditReport,
    entry: LedgerEntry,
    audit_date: str,
) -> WatchState:
    """Atomically advance accepted state after complete nonblocking review."""

    state = load_state(state_path)
    validate_state_transition(state, report, entry)
    try:
        updated = WatchState(
            schema_version=state.schema_version,
            author=state.author,
            passive_fork=state.passive_fork,
            baseline=AcceptedBaseline.from_dict(
                {
                    "reviewed_sha": report.head_sha,
                    "audit_id": report.audit_id,
                    "audit_date": audit_date,
                    "manifest_sha256": report.manifest_sha256(),
                    "path_count": len(report.changes),
                }
            ),
        )
    except ValueError as exc:
        raise LedgerValidationError(f"Invalid state transition: {exc}") from exc
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{state_path.name}.",
            suffix=".tmp",
            dir=state_path.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(canonical_json_bytes(updated.to_dict()))
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(state_path)
    except OSError as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise LedgerValidationError(
            f"Could not atomically update {state_path.name}"
        ) from exc
    return updated
