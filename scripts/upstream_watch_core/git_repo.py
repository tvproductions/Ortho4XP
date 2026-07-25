"""Constrained Git operations for inspecting untrusted upstream repositories."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .models import (
    ChangeStatus,
    CommitRecord,
    ForkState,
    PathChange,
    ReportValidationError,
    WatchExit,
    WatchState,
    validate_sha,
)

_CREDENTIAL_URL_RE = re.compile(r"(https://)[^/@\s]+@")


class GitCommandError(RuntimeError):
    """Raised when a constrained Git subprocess cannot provide trusted data."""


def _redact(value: str) -> str:
    return _CREDENTIAL_URL_RE.sub(r"\1***@", value)


class GitRunner:
    """Execute fixed-argument Git commands without a shell or interactive input."""

    def __init__(self, cwd: Path | None = None) -> None:
        self.cwd = cwd

    def run(self, args: Sequence[str], cwd: Path | None = None) -> str:
        result = self._execute(args, cwd=cwd, text=True)
        return cast(str, result.stdout)

    def run_bytes(self, args: Sequence[str], cwd: Path | None = None) -> bytes:
        result = self._execute(args, cwd=cwd, text=False)
        return cast(bytes, result.stdout)

    def _execute(
        self, args: Sequence[str], *, cwd: Path | None, text: bool
    ) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
        command = ["git", *args]
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        working_directory = cwd if cwd is not None else self.cwd
        try:
            result = subprocess.run(  # noqa: S603 - no shell; Git argv is constrained.
                command,
                cwd=working_directory,
                check=False,
                capture_output=True,
                text=text,
                encoding="utf-8" if text else None,
                errors="strict" if text else None,
                stdin=subprocess.DEVNULL,
                env=environment,
            )
        except (OSError, UnicodeError) as exc:
            rendered = " ".join(_redact(argument) for argument in command)
            raise GitCommandError(f"Could not execute {rendered}") from exc
        if result.returncode != 0:
            stderr_value = result.stderr
            if isinstance(stderr_value, bytes):
                stderr_value = stderr_value.decode("utf-8", errors="replace")
            stderr = _redact(stderr_value.strip())
            rendered = " ".join(_redact(argument) for argument in command)
            raise GitCommandError(
                f"{rendered} failed with status {result.returncode}: {stderr}"
            )
        return result


def _is_ancestor(runner: GitRunner, ancestor: str, descendant: str) -> bool:
    validate_sha(ancestor, "ancestor")
    validate_sha(descendant, "descendant")
    try:
        runner.run(["merge-base", "--is-ancestor", ancestor, descendant])
    except GitCommandError as exc:
        if "status 1:" in str(exc):
            return False
        raise
    return True


def classify_author_history(
    runner: GitRunner, baseline_sha: str, author_head: str
) -> WatchExit:
    """Classify the authoritative branch relative to the accepted baseline."""

    validate_sha(baseline_sha, "baseline_sha")
    validate_sha(author_head, "author_head")
    if baseline_sha == author_head:
        return WatchExit.CURRENT
    if _is_ancestor(runner, baseline_sha, author_head):
        return WatchExit.REVIEW_REQUIRED
    return WatchExit.HISTORY_REWRITE


def classify_passive_fork(
    runner: GitRunner, author_head: str, passive_head: str
) -> ForkState:
    """Classify the passive fork without treating normal lag as an anomaly."""

    validate_sha(author_head, "author_head")
    validate_sha(passive_head, "passive_head")
    if author_head == passive_head:
        return ForkState.SYNCHRONIZED
    if _is_ancestor(runner, passive_head, author_head):
        return ForkState.BEHIND
    if _is_ancestor(runner, author_head, passive_head):
        return ForkState.UNEXPECTED_COMMITS
    return ForkState.DIVERGED


def watch_exit_status(
    author_status: WatchExit, passive_fork_state: ForkState
) -> WatchExit:
    """Apply the documented status precedence shared by CLI and workflow."""

    if author_status in {
        WatchExit.ERROR,
        WatchExit.HISTORY_REWRITE,
        WatchExit.REVIEW_REQUIRED,
    }:
        return author_status
    if passive_fork_state in {ForkState.UNEXPECTED_COMMITS, ForkState.DIVERGED}:
        return WatchExit.FORK_ANOMALY
    return WatchExit.CURRENT


def list_commits(
    runner: GitRunner, base_sha: str, head_sha: str
) -> tuple[CommitRecord, ...]:
    """List deterministic commit metadata for an explicit SHA range."""

    validate_sha(base_sha, "base_sha")
    validate_sha(head_sha, "head_sha")
    output = runner.run(
        [
            "log",
            "--reverse",
            "--format=%H%x1f%an%x1f%ae%x1f%aI%x1f%s%x1e",
            f"{base_sha}..{head_sha}",
        ]
    )
    records: list[CommitRecord] = []
    for raw_record in output.split("\x1e"):
        raw_record = raw_record.strip("\r\n")
        if not raw_record:
            continue
        fields = raw_record.split("\x1f")
        if len(fields) != 5:
            raise GitCommandError("Git commit metadata had an unexpected shape")
        records.append(
            CommitRecord.from_dict(
                {
                    "sha": fields[0],
                    "author_name": fields[1],
                    "author_email": fields[2],
                    "authored_at": _normalize_git_timestamp(fields[3]),
                    "subject": fields[4],
                }
            )
        )
    return tuple(records)


def _normalize_git_timestamp(value: str) -> str:
    if value.endswith("+00:00"):
        return value[:-6] + "Z"
    return value


def list_changes(
    runner: GitRunner, base_sha: str, head_sha: str
) -> tuple[PathChange, ...]:
    """List changed paths and line statistics using NUL-delimited Git output."""

    validate_sha(base_sha, "base_sha")
    validate_sha(head_sha, "head_sha")
    name_status = runner.run(
        [
            "diff",
            "--name-status",
            "-z",
            "--find-renames",
            "--find-copies",
            base_sha,
            head_sha,
        ]
    )
    numstat = runner.run(
        [
            "diff",
            "--numstat",
            "-z",
            "--find-renames",
            "--find-copies",
            base_sha,
            head_sha,
        ]
    )
    counts = _parse_numstat(numstat)
    changes = _parse_name_status(name_status, counts)
    return tuple(sorted(changes, key=lambda change: change.path))


def _parse_name_status(
    output: str, counts: dict[str, tuple[int | None, int | None]]
) -> list[PathChange]:
    tokens = output.split("\0")
    if tokens and tokens[-1] == "":
        tokens.pop()
    changes: list[PathChange] = []
    index = 0
    while index < len(tokens):
        status_token = tokens[index]
        index += 1
        if not status_token:
            raise GitCommandError("Git name-status output contained an empty status")
        status_letter = status_token[0]
        try:
            status = ChangeStatus(status_letter)
        except ValueError as exc:
            raise GitCommandError(
                f"Git name-status output used unsupported status {status_letter!r}"
            ) from exc
        previous_path: str | None = None
        if status in {ChangeStatus.RENAMED, ChangeStatus.COPIED}:
            if index + 1 >= len(tokens):
                raise GitCommandError("Git rename/copy output was truncated")
            previous_path = tokens[index]
            path = tokens[index + 1]
            index += 2
        else:
            if index >= len(tokens):
                raise GitCommandError("Git name-status output was truncated")
            path = tokens[index]
            index += 1
        additions, deletions = counts.get(path, (None, None))
        try:
            change = PathChange.from_dict(
                {
                    "path": path,
                    "status": status.value,
                    "previous_path": previous_path,
                    "additions": additions,
                    "deletions": deletions,
                }
            )
        except ReportValidationError as exc:
            raise GitCommandError(
                f"Git returned an unsafe changed path: {exc}"
            ) from exc
        changes.append(change)
    return changes


def _parse_numstat(output: str) -> dict[str, tuple[int | None, int | None]]:
    tokens = output.split("\0")
    if tokens and tokens[-1] == "":
        tokens.pop()
    result: dict[str, tuple[int | None, int | None]] = {}
    index = 0
    while index < len(tokens):
        record = tokens[index]
        index += 1
        fields = record.split("\t", 2)
        if len(fields) != 3:
            raise GitCommandError("Git numstat output had an unexpected shape")
        additions = _parse_line_count(fields[0])
        deletions = _parse_line_count(fields[1])
        path = fields[2]
        if path == "":
            if index + 1 >= len(tokens):
                raise GitCommandError("Git rename/copy numstat output was truncated")
            index += 1  # original path is evidence in name-status
            path = tokens[index]
            index += 1
        result[path] = (additions, deletions)
    return result


def _parse_line_count(value: str) -> int | None:
    if value == "-":
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise GitCommandError(f"Git numstat count was invalid: {value!r}") from exc
    if parsed < 0:
        raise GitCommandError("Git numstat count cannot be negative")
    return parsed


def read_blob(runner: GitRunner, sha: str, path: str) -> bytes:
    """Read a blob directly from Git without checkout or execution."""

    validate_sha(sha, "sha")
    validated = PathChange.from_dict(
        {
            "path": path,
            "status": ChangeStatus.MODIFIED.value,
            "previous_path": None,
            "additions": None,
            "deletions": None,
        }
    ).path
    return runner.run_bytes(["show", f"{sha}:{validated}"])


@dataclass(slots=True)
class FetchedRepositories:
    """Temporary bare repository containing authoritative and passive refs."""

    repo: Path
    author_head: str
    passive_head: str
    _temporary_directory: tempfile.TemporaryDirectory[str]

    def close(self) -> None:
        self._temporary_directory.cleanup()

    def __enter__(self) -> FetchedRepositories:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def fetch_repositories(state: WatchState) -> FetchedRepositories:
    """Fetch only the monitored branch heads into a temporary bare repository."""

    temporary_directory = tempfile.TemporaryDirectory(prefix="ortho4xp-upstream-watch-")
    repo = Path(temporary_directory.name, "watch.git")
    runner = GitRunner()
    try:
        runner.run(["init", "--bare", str(repo)])
        author_url = _repository_url(state.author.repository)
        passive_url = _repository_url(state.passive_fork.repository)
        author_head = _ls_remote_head(runner, author_url, state.author.branch)
        passive_head = _ls_remote_head(runner, passive_url, state.passive_fork.branch)
        local_runner = GitRunner(repo)
        local_runner.run(
            [
                "fetch",
                "--no-tags",
                "--no-recurse-submodules",
                author_url,
                f"{author_head}:refs/upstream-watch/author",
            ]
        )
        local_runner.run(
            [
                "fetch",
                "--no-tags",
                "--no-recurse-submodules",
                passive_url,
                f"{passive_head}:refs/upstream-watch/passive",
            ]
        )
        local_runner.run(
            ["cat-file", "-e", f"{state.baseline.reviewed_sha}^{{commit}}"]
        )
    except Exception:
        temporary_directory.cleanup()
        raise
    return FetchedRepositories(
        repo=repo,
        author_head=author_head,
        passive_head=passive_head,
        _temporary_directory=temporary_directory,
    )


def _repository_url(repository: str) -> str:
    return f"https://github.com/{repository}.git"


def _ls_remote_head(runner: GitRunner, url: str, branch: str) -> str:
    output = runner.run(["ls-remote", "--heads", url, f"refs/heads/{branch}"])
    lines = [line for line in output.splitlines() if line]
    if len(lines) != 1:
        raise GitCommandError(f"Remote branch {branch!r} was not found uniquely")
    sha, separator, ref = lines[0].partition("\t")
    if not separator or ref != f"refs/heads/{branch}":
        raise GitCommandError("Git ls-remote output had an unexpected shape")
    try:
        return validate_sha(sha, "remote head")
    except ValueError as exc:
        raise GitCommandError(str(exc)) from exc
