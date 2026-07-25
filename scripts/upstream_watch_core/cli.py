"""Command-line orchestration for local and scheduled upstream-watch work."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from .audit import AuditGenerationError, build_audit_report, write_report
from .git_repo import (
    GitCommandError,
    GitRunner,
    classify_author_history,
    classify_passive_fork,
    ensure_authoritative_candidate,
    fetch_repositories,
    watch_exit_status,
)
from .github_api import (
    GitHubApiError,
    GitHubClient,
    WatchObservation,
    reconcile_tracking_issue,
)
from .ledger import (
    LedgerValidationError,
    advance_baseline,
    parse_ledger,
    validate_evidence,
)
from .models import (
    AuditReport,
    ReportValidationError,
    StateValidationError,
    WatchExit,
    WatchState,
    canonical_json_bytes,
    load_report,
    load_state,
    validate_sha,
)

DEFAULT_STATE_PATH = Path(".github/upstream-watch.json")


def perform_check(state: WatchState) -> WatchObservation:
    """Fetch monitored heads and return one classified observation."""

    with fetch_repositories(state) as fetched:
        runner = GitRunner(fetched.repo)
        author_status = classify_author_history(
            runner, state.baseline.reviewed_sha, fetched.author_head
        )
        passive_state = classify_passive_fork(
            runner, fetched.author_head, fetched.passive_head
        )
        status = watch_exit_status(author_status, passive_state)
    return WatchObservation(
        status=status,
        author_repository=state.author.repository,
        author_branch=state.author.branch,
        baseline_sha=state.baseline.reviewed_sha,
        author_head=fetched.author_head,
        passive_repository=state.passive_fork.repository,
        passive_branch=state.passive_fork.branch,
        passive_head=fetched.passive_head,
        passive_state=passive_state,
    )


def create_audit_from_remotes(
    state: WatchState, base_sha: str, head_sha: str
) -> AuditReport:
    """Fetch the monitored repositories and build an explicit-SHA report."""

    validate_sha(base_sha, "base_sha")
    validate_sha(head_sha, "head_sha")
    with fetch_repositories(state) as fetched:
        ensure_authoritative_candidate(
            GitRunner(fetched.repo), head_sha, fetched.author_head
        )
        return build_audit_report(
            state,
            base_sha,
            head_sha,
            datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            GitRunner(fetched.repo),
            ruff_executable=shutil.which("ruff"),
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="upstream-watch",
        description="Detect and audit sister-project changes without executing them.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Compare monitored remote heads")
    check.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    check.add_argument("--manage-issue", action="store_true")
    check.add_argument("--repository")
    check.add_argument("--json", action="store_true")

    audit = subparsers.add_parser("audit", help="Generate an explicit-SHA audit report")
    audit.add_argument("--state", type=Path, required=True)
    audit.add_argument("--base", required=True)
    audit.add_argument("--head", required=True)
    audit.add_argument("--output", type=Path, required=True)

    validate = subparsers.add_parser(
        "validate", help="Validate report coverage against the durable ledger"
    )
    validate.add_argument("--state", type=Path, required=True)
    validate.add_argument("--report", type=Path, required=True)
    validate.add_argument("--ledger", type=Path, required=True)
    validate.add_argument("--json", action="store_true")

    accept = subparsers.add_parser(
        "accept", help="Advance the reviewed baseline after complete review"
    )
    accept.add_argument("--state", type=Path, required=True)
    accept.add_argument("--report", type=Path, required=True)
    accept.add_argument("--ledger", type=Path, required=True)
    accept.add_argument("--date", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the upstream-watch CLI and return its stable process status."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "check":
            return int(_command_check(arguments))
        if arguments.command == "audit":
            return int(_command_audit(arguments))
        if arguments.command == "validate":
            return int(_command_validate(arguments))
        if arguments.command == "accept":
            return int(_command_accept(arguments))
        raise StateValidationError(f"Unknown command {arguments.command!r}")
    except KeyboardInterrupt:
        print("upstream-watch interrupted", file=sys.stderr)
        return 130
    except (
        AuditGenerationError,
        GitCommandError,
        GitHubApiError,
        LedgerValidationError,
        OSError,
        ReportValidationError,
        StateValidationError,
    ) as exc:
        print(f"upstream-watch error: {exc}", file=sys.stderr)
        return int(WatchExit.ERROR)


def _command_check(arguments: argparse.Namespace) -> WatchExit:
    state = load_state(arguments.state)
    observation = perform_check(state)
    if arguments.manage_issue:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            raise GitHubApiError(
                "GITHUB_TOKEN or GH_TOKEN is required with --manage-issue"
            )
        repository = arguments.repository or os.environ.get("GITHUB_REPOSITORY")
        if not repository:
            raise GitHubApiError(
                "--repository or GITHUB_REPOSITORY is required with --manage-issue"
            )
        reconcile_tracking_issue(
            GitHubClient(token),
            repository=repository,
            observation=observation,
        )
    if arguments.json:
        _write_json(observation.to_dict())
    else:
        print(
            f"author={observation.author_head} "
            f"passive={observation.passive_head} "
            f"fork={observation.passive_state.value} "
            f"status={int(observation.status)}"
        )
    return observation.status


def _command_audit(arguments: argparse.Namespace) -> WatchExit:
    state = load_state(arguments.state)
    report = create_audit_from_remotes(
        state,
        validate_sha(arguments.base, "base"),
        validate_sha(arguments.head, "head"),
    )
    write_report(arguments.output, report)
    print(
        f"Wrote {report.audit_id}: {len(report.commits)} commits, "
        f"{len(report.changes)} changed paths, digest {report.manifest_sha256()}"
    )
    return WatchExit.CURRENT


def _matching_entry(report: AuditReport, ledger_path: Path):
    entries = [
        entry
        for entry in parse_ledger(ledger_path)
        if entry.audit.audit_id == report.audit_id
    ]
    if len(entries) != 1:
        raise LedgerValidationError(
            f"ledger must contain exactly one record for {report.audit_id}"
        )
    return entries[0]


def _command_validate(arguments: argparse.Namespace) -> WatchExit:
    state = load_state(arguments.state)
    report = load_report(arguments.report)
    entry = _matching_entry(report, arguments.ledger)
    coverage = validate_evidence(state, report, entry)
    status = (
        WatchExit.REVIEW_REQUIRED if coverage.blocking_findings else WatchExit.CURRENT
    )
    result = {
        "status": int(status),
        "audit_id": report.audit_id,
        "path_count": len(coverage.covered_paths),
        "blocking_findings": list(coverage.blocking_findings),
    }
    if arguments.json:
        _write_json(result)
    else:
        print(canonical_json_bytes(result).decode("ascii"))
    return status


def _command_accept(arguments: argparse.Namespace) -> WatchExit:
    report = load_report(arguments.report)
    entry = _matching_entry(report, arguments.ledger)
    state = advance_baseline(arguments.state, report, entry, arguments.date)
    print(
        f"Accepted {state.baseline.audit_id} at {state.baseline.reviewed_sha} "
        f"for {state.baseline.path_count} paths"
    )
    return WatchExit.CURRENT


def _write_json(value: object) -> None:
    print(canonical_json_bytes(value).decode("ascii"))
