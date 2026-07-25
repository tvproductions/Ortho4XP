"""Validated data contracts for the sister-project upstream watch."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import IntEnum, StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, cast

SCHEMA_VERSION = 1
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SHA_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
AUDIT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
RFC3339_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)


class StateValidationError(ValueError):
    """Raised when committed upstream-watch state is unsafe or malformed."""


class ReportValidationError(ValueError):
    """Raised when an audit report is unsafe or malformed."""


class WatchExit(IntEnum):
    """Stable process exit statuses used by local and scheduled checks."""

    CURRENT = 0
    ERROR = 1
    REVIEW_REQUIRED = 2
    FORK_ANOMALY = 3
    HISTORY_REWRITE = 4


class ForkState(StrEnum):
    """Relationship between the passive fork and authoritative source."""

    SYNCHRONIZED = "synchronized"
    BEHIND = "behind"
    UNEXPECTED_COMMITS = "unexpected-commits"
    DIVERGED = "diverged"


class ChangeStatus(StrEnum):
    """Git name-status values accepted in an audit manifest."""

    ADDED = "A"
    MODIFIED = "M"
    DELETED = "D"
    RENAMED = "R"
    COPIED = "C"


class Disposition(StrEnum):
    """Human engineering decisions accepted by the audit ledger."""

    ADOPT = "adopt"
    REIMPLEMENT = "reimplement"
    INVESTIGATE = "investigate"
    REJECT = "reject"
    SUPERSEDED_LOCALLY = "superseded-locally"


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic UTF-8 JSON bytes without insignificant whitespace."""

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _require_mapping(
    value: object, field: str, error: type[ValueError]
) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise error(f"{field} must be a JSON object")
    return cast(dict[str, Any], value)


def _require_exact_keys(
    value: dict[str, Any],
    required: set[str],
    field: str,
    error: type[ValueError],
    optional: set[str] | None = None,
) -> None:
    allowed = required | (optional or set())
    missing = required - value.keys()
    unknown = value.keys() - allowed
    if missing:
        raise error(f"{field} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise error(f"{field} has unknown fields: {', '.join(sorted(unknown))}")


def _validate_text(
    value: object,
    field: str,
    error: type[ValueError],
    *,
    max_length: int = 4096,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error(f"{field} must be a nonempty string")
    if len(value) > max_length or any(ord(character) < 32 for character in value):
        raise error(f"{field} contains invalid characters")
    return value


def _validate_int(
    value: object,
    field: str,
    error: type[ValueError],
    *,
    minimum: int = 0,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise error(f"{field} must be an integer greater than or equal to {minimum}")
    return value


def validate_sha(value: object, field: str) -> str:
    """Validate a lowercase full-length Git object identifier."""

    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise StateValidationError(f"{field} must be a lowercase 40-character SHA")
    return value


def _validate_report_sha(value: object, field: str) -> str:
    try:
        return validate_sha(value, field)
    except StateValidationError as exc:
        raise ReportValidationError(str(exc)) from exc


def validate_repository(value: object, field: str) -> str:
    """Validate an unauthenticated GitHub owner/name repository slug."""

    if (
        not isinstance(value, str)
        or REPOSITORY_RE.fullmatch(value) is None
        or "://" in value
        or "@" in value
    ):
        raise StateValidationError(f"{field} must use the owner/name form")
    return value


def _validate_branch(value: object, field: str) -> str:
    branch = _validate_text(value, field, StateValidationError, max_length=255)
    if (
        branch.startswith(("-", "."))
        or branch.endswith((".", "/"))
        or ".." in branch
        or "@{" in branch
        or "\\" in branch
        or any(part in {"", ".", ".."} for part in branch.split("/"))
    ):
        raise StateValidationError(f"{field} is not a safe Git branch")
    return branch


def _validate_date(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise StateValidationError(f"{field} must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise StateValidationError(f"{field} must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise StateValidationError(f"{field} must use YYYY-MM-DD")
    return value


def _validate_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or RFC3339_TIMESTAMP_RE.fullmatch(value) is None:
        raise ReportValidationError(
            f"{field} must be an RFC 3339 timestamp with a timezone"
        )
    try:
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except ValueError as exc:
        raise ReportValidationError(
            f"{field} must be an RFC 3339 timestamp with a timezone"
        ) from exc
    if parsed.utcoffset() is None:
        raise ReportValidationError(
            f"{field} must be an RFC 3339 timestamp with a timezone"
        )
    return value


def _validate_path(value: object, field: str) -> str:
    path = _validate_text(value, field, ReportValidationError)
    pure = PurePosixPath(path)
    if (
        pure.is_absolute()
        or "\\" in path
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ReportValidationError(f"{field} must be a safe repository-relative path")
    return path


def _validate_audit_id(
    value: object, field: str, error: type[ValueError] = StateValidationError
) -> str:
    if not isinstance(value, str) or AUDIT_ID_RE.fullmatch(value) is None:
        raise error(f"{field} must be a safe audit identifier")
    return value


@dataclass(frozen=True, slots=True)
class RepositoryRef:
    repository: str
    branch: str

    @classmethod
    def from_dict(cls, value: object, field: str) -> RepositoryRef:
        data = _require_mapping(value, field, StateValidationError)
        _require_exact_keys(data, {"repository", "branch"}, field, StateValidationError)
        return cls(
            repository=validate_repository(data["repository"], f"{field}.repository"),
            branch=_validate_branch(data["branch"], f"{field}.branch"),
        )

    def to_dict(self) -> dict[str, object]:
        return {"repository": self.repository, "branch": self.branch}


@dataclass(frozen=True, slots=True)
class AcceptedBaseline:
    reviewed_sha: str
    audit_id: str
    audit_date: str
    manifest_sha256: str
    path_count: int

    @classmethod
    def from_dict(cls, value: object) -> AcceptedBaseline:
        data = _require_mapping(value, "baseline", StateValidationError)
        _require_exact_keys(
            data,
            {
                "reviewed_sha",
                "audit_id",
                "audit_date",
                "manifest_sha256",
                "path_count",
            },
            "baseline",
            StateValidationError,
        )
        digest = data["manifest_sha256"]
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise StateValidationError(
                "baseline.manifest_sha256 must be a lowercase SHA-256 digest"
            )
        return cls(
            reviewed_sha=validate_sha(data["reviewed_sha"], "baseline.reviewed_sha"),
            audit_id=_validate_audit_id(data["audit_id"], "baseline.audit_id"),
            audit_date=_validate_date(data["audit_date"], "baseline.audit_date"),
            manifest_sha256=digest,
            path_count=_validate_int(
                data["path_count"], "baseline.path_count", StateValidationError
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "reviewed_sha": self.reviewed_sha,
            "audit_id": self.audit_id,
            "audit_date": self.audit_date,
            "manifest_sha256": self.manifest_sha256,
            "path_count": self.path_count,
        }


@dataclass(frozen=True, slots=True)
class WatchState:
    schema_version: int
    author: RepositoryRef
    passive_fork: RepositoryRef
    baseline: AcceptedBaseline

    @classmethod
    def from_dict(cls, value: object) -> WatchState:
        data = _require_mapping(value, "state", StateValidationError)
        _require_exact_keys(
            data,
            {"schema_version", "author", "passive_fork", "baseline"},
            "state",
            StateValidationError,
        )
        version = _validate_int(
            data["schema_version"], "schema_version", StateValidationError, minimum=1
        )
        if version != SCHEMA_VERSION:
            raise StateValidationError(
                f"schema_version must be {SCHEMA_VERSION}, got {version}"
            )
        return cls(
            schema_version=version,
            author=RepositoryRef.from_dict(data["author"], "author"),
            passive_fork=RepositoryRef.from_dict(data["passive_fork"], "passive_fork"),
            baseline=AcceptedBaseline.from_dict(data["baseline"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "author": self.author.to_dict(),
            "passive_fork": self.passive_fork.to_dict(),
            "baseline": self.baseline.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PathChange:
    path: str
    status: ChangeStatus
    previous_path: str | None = None
    additions: int | None = None
    deletions: int | None = None

    @classmethod
    def from_dict(cls, value: object) -> PathChange:
        data = _require_mapping(value, "change", ReportValidationError)
        _require_exact_keys(
            data,
            {"path", "status", "previous_path", "additions", "deletions"},
            "change",
            ReportValidationError,
        )
        try:
            status = ChangeStatus(data["status"])
        except (ValueError, TypeError) as exc:
            raise ReportValidationError("change.status is unknown") from exc
        previous = data["previous_path"]
        if previous is not None:
            previous = _validate_path(previous, "change.previous_path")
        if status in {ChangeStatus.RENAMED, ChangeStatus.COPIED} and previous is None:
            raise ReportValidationError(
                "change.previous_path is required for renames and copies"
            )
        if status not in {ChangeStatus.RENAMED, ChangeStatus.COPIED} and previous:
            raise ReportValidationError(
                "change.previous_path is allowed only for renames and copies"
            )
        counts: list[int | None] = []
        for name in ("additions", "deletions"):
            raw = data[name]
            counts.append(
                None
                if raw is None
                else _validate_int(raw, f"change.{name}", ReportValidationError)
            )
        return cls(
            path=_validate_path(data["path"], "change.path"),
            status=status,
            previous_path=previous,
            additions=counts[0],
            deletions=counts[1],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "status": self.status.value,
            "previous_path": self.previous_path,
            "additions": self.additions,
            "deletions": self.deletions,
        }


@dataclass(frozen=True, slots=True)
class CommitRecord:
    sha: str
    author_name: str
    author_email: str
    authored_at: str
    subject: str

    @classmethod
    def from_dict(cls, value: object) -> CommitRecord:
        data = _require_mapping(value, "commit", ReportValidationError)
        _require_exact_keys(
            data,
            {"sha", "author_name", "author_email", "authored_at", "subject"},
            "commit",
            ReportValidationError,
        )
        return cls(
            sha=_validate_report_sha(data["sha"], "commit.sha"),
            author_name=_validate_text(
                data["author_name"], "commit.author_name", ReportValidationError
            ),
            author_email=_validate_text(
                data["author_email"], "commit.author_email", ReportValidationError
            ),
            authored_at=_validate_timestamp(data["authored_at"], "commit.authored_at"),
            subject=_validate_text(
                data["subject"], "commit.subject", ReportValidationError
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "sha": self.sha,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "authored_at": self.authored_at,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class InspectionResult:
    path: str
    syntax_ok: bool | None
    syntax_error: str | None
    signals: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: object) -> InspectionResult:
        data = _require_mapping(value, "inspection", ReportValidationError)
        _require_exact_keys(
            data,
            {"path", "syntax_ok", "syntax_error", "signals"},
            "inspection",
            ReportValidationError,
        )
        syntax_ok = data["syntax_ok"]
        if syntax_ok is not None and not isinstance(syntax_ok, bool):
            raise ReportValidationError("inspection.syntax_ok must be boolean or null")
        syntax_error = data["syntax_error"]
        if syntax_error is not None:
            syntax_error = _validate_text(
                syntax_error, "inspection.syntax_error", ReportValidationError
            )
        raw_signals = data["signals"]
        if not isinstance(raw_signals, list):
            raise ReportValidationError("inspection.signals must be an array")
        signals = tuple(
            _validate_text(
                item, "inspection.signals[]", ReportValidationError, max_length=128
            )
            for item in raw_signals
        )
        if len(signals) != len(set(signals)):
            raise ReportValidationError("inspection.signals contains duplicates")
        return cls(
            path=_validate_path(data["path"], "inspection.path"),
            syntax_ok=syntax_ok,
            syntax_error=syntax_error,
            signals=signals,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "syntax_ok": self.syntax_ok,
            "syntax_error": self.syntax_error,
            "signals": list(self.signals),
        }


@dataclass(frozen=True, slots=True)
class AuditReport:
    schema_version: int
    audit_id: str
    base_sha: str
    head_sha: str
    generated_at: str
    ancestry: str
    commits: tuple[CommitRecord, ...]
    changes: tuple[PathChange, ...]
    inspections: tuple[InspectionResult, ...] = ()
    dependency_changes: tuple[str, ...] = ()
    provider_changes: tuple[str, ...] = ()
    compatibility_signals: tuple[str, ...] = ()
    inspection_tools: dict[str, object] | None = None

    @classmethod
    def from_dict(cls, value: object) -> AuditReport:
        data = _require_mapping(value, "report", ReportValidationError)
        _require_exact_keys(
            data,
            {
                "schema_version",
                "audit_id",
                "base_sha",
                "head_sha",
                "generated_at",
                "ancestry",
                "commits",
                "changes",
                "inspections",
                "dependency_changes",
                "provider_changes",
                "compatibility_signals",
                "inspection_tools",
            },
            "report",
            ReportValidationError,
        )
        version = _validate_int(
            data["schema_version"],
            "report.schema_version",
            ReportValidationError,
            minimum=1,
        )
        if version != SCHEMA_VERSION:
            raise ReportValidationError(
                f"report.schema_version must be {SCHEMA_VERSION}"
            )
        ancestry = _validate_text(
            data["ancestry"], "report.ancestry", ReportValidationError, max_length=32
        )
        if ancestry not in {"fast-forward", "equal", "rewritten"}:
            raise ReportValidationError("report.ancestry is unknown")
        commits_raw = data["commits"]
        changes_raw = data["changes"]
        inspections_raw = data["inspections"]
        if not isinstance(commits_raw, list):
            raise ReportValidationError("report.commits must be an array")
        if not isinstance(changes_raw, list):
            raise ReportValidationError("report.changes must be an array")
        if not isinstance(inspections_raw, list):
            raise ReportValidationError("report.inspections must be an array")
        changes = tuple(PathChange.from_dict(item) for item in changes_raw)
        paths = [change.path for change in changes]
        if len(paths) != len(set(paths)):
            raise ReportValidationError("report.changes contains duplicate paths")
        tools = data["inspection_tools"]
        if tools is not None:
            tools = _require_mapping(
                tools, "report.inspection_tools", ReportValidationError
            )
        return cls(
            schema_version=version,
            audit_id=_validate_audit_id(
                data["audit_id"], "report.audit_id", ReportValidationError
            ),
            base_sha=_validate_report_sha(data["base_sha"], "report.base_sha"),
            head_sha=_validate_report_sha(data["head_sha"], "report.head_sha"),
            generated_at=_validate_timestamp(
                data["generated_at"], "report.generated_at"
            ),
            ancestry=ancestry,
            commits=tuple(CommitRecord.from_dict(item) for item in commits_raw),
            changes=changes,
            inspections=tuple(
                InspectionResult.from_dict(item) for item in inspections_raw
            ),
            dependency_changes=_validate_path_array(
                data["dependency_changes"], "report.dependency_changes"
            ),
            provider_changes=_validate_path_array(
                data["provider_changes"], "report.provider_changes"
            ),
            compatibility_signals=_validate_text_array(
                data["compatibility_signals"],
                "report.compatibility_signals",
                ReportValidationError,
            ),
            inspection_tools=tools,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "audit_id": self.audit_id,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "generated_at": self.generated_at,
            "ancestry": self.ancestry,
            "commits": [record.to_dict() for record in self.commits],
            "changes": [change.to_dict() for change in self.changes],
            "inspections": [inspection.to_dict() for inspection in self.inspections],
            "dependency_changes": list(self.dependency_changes),
            "provider_changes": list(self.provider_changes),
            "compatibility_signals": list(self.compatibility_signals),
            "inspection_tools": self.inspection_tools,
        }

    def manifest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "audit_id": self.audit_id,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "ancestry": self.ancestry,
            "commits": [record.to_dict() for record in self.commits],
            "changes": [change.to_dict() for change in self.changes],
        }

    def manifest_sha256(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.manifest_payload())).hexdigest()


def _validate_path_array(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ReportValidationError(f"{field} must be an array")
    paths = tuple(_validate_path(item, f"{field}[]") for item in value)
    if len(paths) != len(set(paths)):
        raise ReportValidationError(f"{field} contains duplicates")
    return paths


def _validate_text_array(
    value: object, field: str, error: type[ValueError]
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise error(f"{field} must be an array")
    items = tuple(
        _validate_text(item, f"{field}[]", error, max_length=256) for item in value
    )
    if len(items) != len(set(items)):
        raise error(f"{field} contains duplicates")
    return items


@dataclass(frozen=True, slots=True)
class FindingRecord:
    finding_id: str
    audit_id: str
    paths: tuple[str, ...]
    disposition: Disposition
    rationale: str
    work_items: tuple[str, ...] = ()
    xp12_compatibility: str = ""


@dataclass(frozen=True, slots=True)
class ReviewedNoActionRecord:
    audit_id: str
    path: str
    rationale: str


def load_state(path: Path) -> WatchState:
    """Load and validate committed upstream-watch state."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StateValidationError(f"Could not load state from {path.name}") from exc
    return WatchState.from_dict(payload)


def load_report(path: Path) -> AuditReport:
    """Load and validate a generated audit report."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportValidationError(f"Could not load report from {path.name}") from exc
    return AuditReport.from_dict(payload)
