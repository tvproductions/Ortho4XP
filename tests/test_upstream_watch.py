from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from scripts.upstream_watch_core.audit import (
    build_audit_report,
    inspect_python_blob,
    write_report,
)
from scripts.upstream_watch_core.cli import main
from scripts.upstream_watch_core.git_repo import (
    GitCommandError,
    GitRunner,
    classify_author_history,
    classify_passive_fork,
    list_changes,
    read_blob,
)
from scripts.upstream_watch_core.github_api import (
    GitHubApiError,
    GitHubClient,
    HttpResponse,
    WatchObservation,
    observation_fingerprint,
    reconcile_tracking_issue,
    render_observation_body,
)
from scripts.upstream_watch_core.ledger import (
    LedgerValidationError,
    advance_baseline,
    parse_ledger,
    validate_coverage,
)
from scripts.upstream_watch_core.models import (
    AuditReport,
    ChangeStatus,
    ForkState,
    PathChange,
    StateValidationError,
    WatchExit,
    WatchState,
    canonical_json_bytes,
    load_report,
    load_state,
)
from tests._path import ROOT_DIR  # noqa: F401

BASE_SHA = "4ca0a8d404b078ad899979bafde84769a0fb235b"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class WatchStateTests(unittest.TestCase):
    def _state(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "author": {
                "repository": "Ypsos/ORTHO4XP_V3",
                "branch": "ORTHO4XP_V3",
            },
            "passive_fork": {
                "repository": "tvproductions/ORTHO4XP_V3",
                "branch": "ORTHO4XP_V3",
            },
            "baseline": {
                "reviewed_sha": BASE_SHA,
                "audit_id": "bootstrap-existing-baseline",
                "audit_date": "2026-06-16",
                "manifest_sha256": EMPTY_SHA256,
                "path_count": 0,
            },
        }

    def _load(self, payload: dict[str, object]):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "state.json")
            path.write_text(json.dumps(payload), encoding="utf-8")
            return load_state(path)

    def test_load_state_accepts_valid_schema(self) -> None:
        state = self._load(self._state())
        self.assertEqual(state.baseline.reviewed_sha, BASE_SHA)
        self.assertEqual(WatchExit.REVIEW_REQUIRED, 2)

    def test_canonical_json_is_order_independent(self) -> None:
        self.assertEqual(canonical_json_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}')

    def test_load_state_rejects_short_sha(self) -> None:
        payload = self._state()
        baseline = cast(dict[str, Any], payload["baseline"])
        baseline["reviewed_sha"] = "abc123"
        with self.assertRaisesRegex(StateValidationError, "lowercase 40-character SHA"):
            self._load(payload)

    def test_load_state_rejects_repository_url_or_credentials(self) -> None:
        for value in (
            "https://github.com/Ypsos/ORTHO4XP_V3",
            "token@github.com/Ypsos/ORTHO4XP_V3",
        ):
            with self.subTest(value=value):
                payload = self._state()
                author = cast(dict[str, Any], payload["author"])
                author["repository"] = value
                with self.assertRaisesRegex(StateValidationError, "owner/name"):
                    self._load(payload)

    def test_load_state_rejects_unknown_schema_version(self) -> None:
        payload = self._state()
        payload["schema_version"] = 2
        with self.assertRaisesRegex(StateValidationError, "schema_version"):
            self._load(payload)

    def test_load_state_rejects_unknown_fields(self) -> None:
        payload = self._state()
        payload["unexpected"] = True
        with self.assertRaisesRegex(StateValidationError, "unknown fields"):
            self._load(payload)

    def test_load_state_rejects_boolean_path_count(self) -> None:
        payload = self._state()
        baseline = cast(dict[str, Any], payload["baseline"])
        baseline["path_count"] = True
        with self.assertRaisesRegex(StateValidationError, "path_count"):
            self._load(payload)


class GitRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repo = Path(self.temporary_directory.name, "repo")
        self.repo.mkdir()
        self._git("init", "-q")
        self._git("config", "user.name", "Upstream Watch Tests")
        self._git("config", "user.email", "upstream-watch@example.invalid")
        self._write("tracked.txt", "base\n")
        self._write("renamed-before.txt", "rename me\n")
        self._write("delete-me.txt", "delete me\n")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "base")
        self.base = self._git("rev-parse", "HEAD")
        self._git("branch", "fork-behind")

        self._write("tracked.txt", "author\n")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "author first")
        self._git("mv", "renamed-before.txt", "renamed-after.txt")
        Path(self.repo, "delete-me.txt").unlink()
        self._write("new.txt", "new\n")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "author second")
        self.author_head = self._git("rev-parse", "HEAD")

        self._git("checkout", "-q", "-b", "fork-ahead")
        self._write("fork.txt", "fork-only\n")
        self._git("add", "fork.txt")
        self._git("commit", "-q", "-m", "fork ahead")
        self.fork_ahead = self._git("rev-parse", "HEAD")

        self._git("checkout", "-q", "-b", "fork-diverged", self.base)
        self._write("diverged.txt", "diverged\n")
        self._git("add", "diverged.txt")
        self._git("commit", "-q", "-m", "fork diverged")
        self.fork_diverged = self._git("rev-parse", "HEAD")
        self.runner = GitRunner(self.repo)

    def _git(self, *args: str) -> str:
        environment = os.environ.copy()
        environment.update(
            {
                "GIT_AUTHOR_DATE": "2026-07-19T12:00:00Z",
                "GIT_COMMITTER_DATE": "2026-07-19T12:00:00Z",
            }
        )
        result = subprocess.run(  # noqa: S603 - local test Git only.
            ["git", *args],  # noqa: S607 - PATH-resolved test dependency.
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
        )
        return result.stdout.strip()

    def _write(self, relative: str, content: str) -> None:
        Path(self.repo, relative).write_text(content, encoding="utf-8")

    def test_classifies_author_history(self) -> None:
        self.assertEqual(
            classify_author_history(self.runner, self.base, self.author_head),
            WatchExit.REVIEW_REQUIRED,
        )
        self.assertEqual(
            classify_author_history(self.runner, self.author_head, self.author_head),
            WatchExit.CURRENT,
        )
        self.assertEqual(
            classify_author_history(self.runner, self.author_head, self.base),
            WatchExit.HISTORY_REWRITE,
        )

    def test_classifies_passive_fork_relationships(self) -> None:
        self.assertEqual(
            classify_passive_fork(self.runner, self.author_head, self.author_head),
            ForkState.SYNCHRONIZED,
        )
        self.assertEqual(
            classify_passive_fork(self.runner, self.author_head, self.base),
            ForkState.BEHIND,
        )
        self.assertEqual(
            classify_passive_fork(self.runner, self.author_head, self.fork_ahead),
            ForkState.UNEXPECTED_COMMITS,
        )
        self.assertEqual(
            classify_passive_fork(self.runner, self.author_head, self.fork_diverged),
            ForkState.DIVERGED,
        )

    def test_lists_name_status_and_line_counts(self) -> None:
        changes = list_changes(self.runner, self.base, self.author_head)
        by_path = {change.path: change for change in changes}
        self.assertEqual(by_path["new.txt"].status, ChangeStatus.ADDED)
        self.assertEqual(by_path["delete-me.txt"].status, ChangeStatus.DELETED)
        self.assertEqual(by_path["renamed-after.txt"].status, ChangeStatus.RENAMED)
        self.assertEqual(
            by_path["renamed-after.txt"].previous_path, "renamed-before.txt"
        )
        self.assertEqual(by_path["tracked.txt"].additions, 1)
        self.assertEqual(by_path["tracked.txt"].deletions, 1)

    def test_reads_blob_without_checkout(self) -> None:
        self.assertEqual(read_blob(self.runner, self.author_head, "new.txt"), b"new\n")

    def test_redacts_credentials_from_git_errors(self) -> None:
        with self.assertRaises(GitCommandError) as context:
            self.runner.run(
                ["show", "https://secret-token@github.com/example/repo.git"]
            )
        self.assertNotIn("secret-token", str(context.exception))


class AuditReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repo = Path(self.temporary_directory.name, "repo")
        self.repo.mkdir()
        self._git("init", "-q")
        self._git("config", "user.name", "Upstream Author")
        self._git("config", "user.email", "author@example.invalid")
        self._write("README.md", "base\n")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "base")
        self.base = self._git("rev-parse", "HEAD")

        self._write(
            "src/must_not_execute.py",
            'raise RuntimeError("must not execute")\nXP_MODE = "XP11 + bathy"\n',
        )
        self._write("src/invalid.py", "def broken(:\n")
        self._write("Providers/Global/Test.lay", "request_type=xyz\n")
        self._write("requirements-dev.txt", "ruff\n")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "candidate")
        self.head = self._git("rev-parse", "HEAD")
        self.runner = GitRunner(self.repo)
        self.state = WatchState.from_dict(
            {
                "schema_version": 1,
                "author": {
                    "repository": "Ypsos/ORTHO4XP_V3",
                    "branch": "ORTHO4XP_V3",
                },
                "passive_fork": {
                    "repository": "tvproductions/ORTHO4XP_V3",
                    "branch": "ORTHO4XP_V3",
                },
                "baseline": {
                    "reviewed_sha": self.base,
                    "audit_id": "bootstrap-existing-baseline",
                    "audit_date": "2026-06-16",
                    "manifest_sha256": EMPTY_SHA256,
                    "path_count": 0,
                },
            }
        )

    def _git(self, *args: str) -> str:
        environment = os.environ.copy()
        environment.update(
            {
                "GIT_AUTHOR_DATE": "2026-07-19T12:00:00Z",
                "GIT_COMMITTER_DATE": "2026-07-19T12:00:00Z",
            }
        )
        result = subprocess.run(  # noqa: S603 - local test Git only.
            ["git", *args],  # noqa: S607 - PATH-resolved test dependency.
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
        )
        return result.stdout.strip()

    def _write(self, relative: str, content: str) -> None:
        path = Path(self.repo, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_builds_deterministic_report_without_executing_source(self) -> None:
        first = build_audit_report(
            self.state,
            self.base,
            self.head,
            "2026-07-19T12:00:00Z",
            self.runner,
            ruff_executable=None,
        )
        second = build_audit_report(
            self.state,
            self.base,
            self.head,
            "2026-07-20T12:00:00Z",
            self.runner,
            ruff_executable=None,
        )
        self.assertEqual(first.manifest_sha256(), second.manifest_sha256())
        self.assertEqual(first.audit_id, f"ypsos-{self.base[:12]}-{self.head[:12]}")
        self.assertEqual(
            [change.path for change in first.changes],
            sorted(change.path for change in first.changes),
        )
        self.assertEqual(first.provider_changes, ("Providers/Global/Test.lay",))
        self.assertEqual(first.dependency_changes, ("requirements-dev.txt",))
        self.assertIn("xp11-bathy", first.compatibility_signals)
        by_path = {inspection.path: inspection for inspection in first.inspections}
        self.assertTrue(by_path["src/must_not_execute.py"].syntax_ok)
        self.assertFalse(by_path["src/invalid.py"].syntax_ok)
        self.assertIn("invalid syntax", by_path["src/invalid.py"].syntax_error or "")
        self.assertEqual(len(first.commits), 1)
        self.assertEqual(first.commits[0].subject, "candidate")

    def test_python_inspection_records_syntax_error_as_data(self) -> None:
        result = inspect_python_blob("bad.py", b"def broken(:\n")
        self.assertFalse(result.syntax_ok)
        self.assertIn("invalid syntax", result.syntax_error or "")

    def test_write_report_is_atomic_and_round_trips(self) -> None:
        report = build_audit_report(
            self.state,
            self.base,
            self.head,
            "2026-07-19T12:00:00Z",
            self.runner,
            ruff_executable=None,
        )
        output = Path(self.temporary_directory.name, "reports", "audit.json")
        write_report(output, report)
        self.assertEqual(load_report(output), report)
        self.assertTrue(output.read_bytes().endswith(b"\n"))


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.state_path = self.root / "state.json"
        self.ledger_path = self.root / "ledger.md"
        self.report = AuditReport(
            schema_version=1,
            audit_id="ypsos-aaaaaaaaaaaa-bbbbbbbbbbbb",
            base_sha="a" * 40,
            head_sha="b" * 40,
            generated_at="2026-07-19T12:00:00Z",
            ancestry="fast-forward",
            commits=(),
            changes=(
                PathChange(
                    path="Providers/Global/Test.lay",
                    status=ChangeStatus.ADDED,
                    additions=1,
                    deletions=0,
                ),
                PathChange(
                    path="src/O4_Example.py",
                    status=ChangeStatus.MODIFIED,
                    additions=2,
                    deletions=1,
                ),
            ),
        )
        self.state = WatchState.from_dict(
            {
                "schema_version": 1,
                "author": {
                    "repository": "Ypsos/ORTHO4XP_V3",
                    "branch": "ORTHO4XP_V3",
                },
                "passive_fork": {
                    "repository": "tvproductions/ORTHO4XP_V3",
                    "branch": "ORTHO4XP_V3",
                },
                "baseline": {
                    "reviewed_sha": self.report.base_sha,
                    "audit_id": "bootstrap-existing-baseline",
                    "audit_date": "2026-06-16",
                    "manifest_sha256": EMPTY_SHA256,
                    "path_count": 0,
                },
            }
        )
        self.state_path.write_bytes(canonical_json_bytes(self.state.to_dict()) + b"\n")

    def _audit_record(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "audit_id": self.report.audit_id,
            "base_sha": self.report.base_sha,
            "head_sha": self.report.head_sha,
            "manifest_sha256": self.report.manifest_sha256(),
            "path_count": len(self.report.changes),
        }
        value.update(overrides)
        return value

    def _finding(
        self,
        finding_id: str,
        paths: list[str],
        *,
        disposition: str = "reject",
        rationale: str = "Not compatible with the local architecture.",
        work_items: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "audit_id": self.report.audit_id,
            "finding_id": finding_id,
            "paths": paths,
            "disposition": disposition,
            "rationale": rationale,
            "work_items": work_items or [],
            "xp12_compatibility": "Reviewed for strict XP12 behavior.",
        }

    def _write_ledger(
        self,
        findings: list[dict[str, object]],
        no_action: list[dict[str, object]] | None = None,
        *,
        audit: dict[str, object] | None = None,
    ) -> None:
        lines = [
            "# Audit Ledger",
            f"<!-- upstream-watch:audit {json.dumps(audit or self._audit_record(), sort_keys=True)} -->",
        ]
        lines.extend(
            f"<!-- upstream-watch:finding {json.dumps(item, sort_keys=True)} -->"
            for item in findings
        )
        lines.extend(
            f"<!-- upstream-watch:reviewed-no-action {json.dumps(item, sort_keys=True)} -->"
            for item in (no_action or [])
        )
        self.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_validate_coverage_accepts_each_path_exactly_once(self) -> None:
        self._write_ledger(
            [
                self._finding(
                    "provider",
                    ["Providers/Global/Test.lay"],
                    disposition="reject",
                ),
                self._finding(
                    "source",
                    ["src/O4_Example.py"],
                    disposition="reimplement",
                    work_items=["TODO-999", "#999"],
                ),
            ]
        )
        entry = parse_ledger(self.ledger_path)[0]
        coverage = validate_coverage(self.report, entry)
        self.assertEqual(
            coverage.covered_paths,
            frozenset(change.path for change in self.report.changes),
        )
        self.assertFalse(coverage.blocking_findings)

    def test_validate_coverage_rejects_missing_duplicate_and_unknown_paths(
        self,
    ) -> None:
        cases = {
            "missing": [
                self._finding("one", ["Providers/Global/Test.lay"]),
            ],
            "duplicate": [
                self._finding("one", ["Providers/Global/Test.lay"]),
                self._finding(
                    "two",
                    ["Providers/Global/Test.lay", "src/O4_Example.py"],
                ),
            ],
            "unknown": [
                self._finding(
                    "one",
                    [
                        "Providers/Global/Test.lay",
                        "src/O4_Example.py",
                        "unknown.py",
                    ],
                )
            ],
        }
        for expected, findings in cases.items():
            with self.subTest(expected=expected):
                self._write_ledger(findings)
                entry = parse_ledger(self.ledger_path)[0]
                with self.assertRaisesRegex(LedgerValidationError, expected):
                    validate_coverage(self.report, entry)

    def test_parse_rejects_empty_rationale_and_accepted_work_without_link(self) -> None:
        cases = (
            self._finding(
                "empty",
                ["Providers/Global/Test.lay"],
                rationale="",
            ),
            self._finding(
                "unlinked",
                ["Providers/Global/Test.lay"],
                disposition="adopt",
            ),
        )
        for finding in cases:
            with self.subTest(finding=finding["finding_id"]):
                self._write_ledger([finding])
                with self.assertRaises(LedgerValidationError):
                    parse_ledger(self.ledger_path)

    def test_investigate_blocks_baseline_advancement(self) -> None:
        self._write_ledger(
            [
                self._finding(
                    "provider",
                    ["Providers/Global/Test.lay"],
                    disposition="investigate",
                    work_items=["TODO-041-4", "#41"],
                ),
                self._finding("source", ["src/O4_Example.py"]),
            ]
        )
        entry = parse_ledger(self.ledger_path)[0]
        coverage = validate_coverage(self.report, entry)
        self.assertEqual(coverage.blocking_findings, ("provider",))
        with self.assertRaisesRegex(LedgerValidationError, "investigate"):
            advance_baseline(
                self.state_path, self.report, entry, audit_date="2026-07-19"
            )

    def test_advance_rejects_digest_mismatch(self) -> None:
        self._write_ledger(
            [
                self._finding(
                    "all",
                    [change.path for change in self.report.changes],
                )
            ],
            audit=self._audit_record(manifest_sha256="c" * 64),
        )
        entry = parse_ledger(self.ledger_path)[0]
        with self.assertRaisesRegex(LedgerValidationError, "digest"):
            advance_baseline(
                self.state_path, self.report, entry, audit_date="2026-07-19"
            )

    def test_advance_updates_state_atomically(self) -> None:
        self._write_ledger(
            [
                self._finding(
                    "all",
                    [change.path for change in self.report.changes],
                )
            ]
        )
        entry = parse_ledger(self.ledger_path)[0]
        updated = advance_baseline(
            self.state_path, self.report, entry, audit_date="2026-07-19"
        )
        self.assertEqual(updated.baseline.reviewed_sha, self.report.head_sha)
        self.assertEqual(
            updated.baseline.manifest_sha256, self.report.manifest_sha256()
        )
        self.assertEqual(load_state(self.state_path), updated)

    def test_failed_atomic_replace_preserves_original_state(self) -> None:
        self._write_ledger(
            [
                self._finding(
                    "all",
                    [change.path for change in self.report.changes],
                )
            ]
        )
        original = self.state_path.read_bytes()
        entry = parse_ledger(self.ledger_path)[0]
        with (
            patch.object(Path, "replace", side_effect=OSError("replace failed")),
            self.assertRaises(LedgerValidationError),
        ):
            advance_baseline(
                self.state_path, self.report, entry, audit_date="2026-07-19"
            )
        self.assertEqual(self.state_path.read_bytes(), original)


class FakeTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.requests: list[dict[str, object]] = []

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> HttpResponse:
        safe_headers = dict(headers)
        if "Authorization" in safe_headers:
            safe_headers["Authorization"] = "Bearer ***"
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": safe_headers,
                "body": body.decode("utf-8") if body else None,
            }
        )
        if not self.responses:
            raise AssertionError(f"Unexpected request: {method} {url}")
        return self.responses.pop(0)


class GitHubIssueTests(unittest.TestCase):
    def _json_response(
        self,
        status: int,
        payload: object,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        return HttpResponse(
            status=status,
            headers=headers or {},
            body=json.dumps(payload).encode("utf-8"),
        )

    def _observation(
        self,
        *,
        status: WatchExit = WatchExit.REVIEW_REQUIRED,
        fork_state: ForkState = ForkState.BEHIND,
        author_head: str = "b" * 40,
    ) -> WatchObservation:
        return WatchObservation(
            status=status,
            author_repository="Ypsos/ORTHO4XP_V3",
            author_branch="ORTHO4XP_V3",
            baseline_sha="a" * 40,
            author_head=author_head,
            passive_repository="tvproductions/ORTHO4XP_V3",
            passive_branch="ORTHO4XP_V3",
            passive_head="a" * 40,
            passive_state=fork_state,
        )

    def _issue(
        self,
        observation: WatchObservation,
        *,
        state: str = "open",
        body: str | None = None,
        number: int = 100,
    ) -> dict[str, object]:
        return {
            "number": number,
            "title": "[Upstream Watch] ORTHO4XP_V3 review status",
            "body": body if body is not None else render_observation_body(observation),
            "state": state,
            "labels": [{"name": "upstream-watch"}],
        }

    def test_creates_label_and_single_tracking_issue(self) -> None:
        observation = self._observation()
        transport = FakeTransport(
            [
                self._json_response(404, {"message": "Not Found"}),
                self._json_response(201, {"name": "upstream-watch"}),
                self._json_response(200, []),
                self._json_response(201, self._issue(observation)),
            ]
        )
        client = GitHubClient("secret-token", transport=transport)
        result = reconcile_tracking_issue(
            client,
            repository="tvproductions/Ortho4XP",
            observation=observation,
        )
        self.assertEqual(result.action, "created")
        self.assertEqual(result.issue_number, 100)
        self.assertNotIn("secret-token", repr(transport.requests))
        self.assertEqual(
            [request["method"] for request in transport.requests],
            ["GET", "POST", "GET", "POST"],
        )

    def test_unchanged_fingerprint_makes_no_issue_mutation(self) -> None:
        observation = self._observation()
        transport = FakeTransport(
            [
                self._json_response(200, {"name": "upstream-watch"}),
                self._json_response(200, [self._issue(observation)]),
            ]
        )
        result = reconcile_tracking_issue(
            GitHubClient("token", transport=transport),
            repository="tvproductions/Ortho4XP",
            observation=observation,
        )
        self.assertEqual(result.action, "unchanged")
        self.assertEqual(len(transport.requests), 2)

    def test_changed_fingerprint_updates_and_comments_once(self) -> None:
        previous = self._observation(author_head="c" * 40)
        current = self._observation()
        transport = FakeTransport(
            [
                self._json_response(200, {"name": "upstream-watch"}),
                self._json_response(200, [self._issue(previous)]),
                self._json_response(201, {"id": 1}),
                self._json_response(200, self._issue(current)),
            ]
        )
        result = reconcile_tracking_issue(
            GitHubClient("token", transport=transport),
            repository="tvproductions/Ortho4XP",
            observation=current,
        )
        self.assertEqual(result.action, "updated")
        self.assertEqual(
            [request["method"] for request in transport.requests],
            ["GET", "GET", "POST", "PATCH"],
        )

    def test_reopens_or_closes_existing_issue_from_status(self) -> None:
        cases = (
            (
                self._observation(),
                "closed",
                "reopened",
                "open",
            ),
            (
                self._observation(status=WatchExit.CURRENT),
                "open",
                "closed",
                "closed",
            ),
        )
        for observation, initial_state, action, final_state in cases:
            with self.subTest(action=action):
                previous_body = render_observation_body(
                    self._observation(author_head="c" * 40)
                )
                transport = FakeTransport(
                    [
                        self._json_response(200, {"name": "upstream-watch"}),
                        self._json_response(
                            200,
                            [
                                self._issue(
                                    observation,
                                    state=initial_state,
                                    body=previous_body,
                                )
                            ],
                        ),
                        self._json_response(201, {"id": 1}),
                        self._json_response(
                            200, self._issue(observation, state=final_state)
                        ),
                    ]
                )
                result = reconcile_tracking_issue(
                    GitHubClient("token", transport=transport),
                    repository="tvproductions/Ortho4XP",
                    observation=observation,
                )
                self.assertEqual(result.action, action)
                patch_body = json.loads(cast(str, transport.requests[-1]["body"]))
                self.assertEqual(patch_body["state"], final_state)

    def test_paginates_only_same_origin_links(self) -> None:
        observation = self._observation()
        next_url = (
            "https://api.github.com/repos/tvproductions/Ortho4XP/issues?"
            "state=all&labels=upstream-watch&per_page=100&page=2"
        )
        transport = FakeTransport(
            [
                self._json_response(
                    200,
                    [],
                    {"Link": f'<{next_url}>; rel="next"'},
                ),
                self._json_response(200, [self._issue(observation)]),
            ]
        )
        issues = GitHubClient("token", transport=transport).list_issues(
            "tvproductions/Ortho4XP", label="upstream-watch"
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(len(transport.requests), 2)

    def test_reports_rate_limits_and_malformed_json_without_token(self) -> None:
        cases = (
            HttpResponse(
                status=403,
                headers={"X-RateLimit-Remaining": "0"},
                body=b'{"message":"rate limit exceeded"}',
            ),
            HttpResponse(status=200, headers={}, body=b"not-json"),
        )
        for response in cases:
            with self.subTest(status=response.status):
                transport = FakeTransport([response])
                client = GitHubClient("secret-token", transport=transport)
                with self.assertRaises(GitHubApiError) as context:
                    client.ensure_label("tvproductions/Ortho4XP")
                self.assertNotIn("secret-token", str(context.exception))

    def test_fingerprint_is_canonical_and_fork_lag_is_informational(self) -> None:
        observation = self._observation()
        self.assertEqual(
            observation_fingerprint(observation),
            observation_fingerprint(self._observation()),
        )
        body = render_observation_body(observation)
        self.assertIn("informational", body.casefold())
        self.assertIn("Ypsos/ORTHO4XP_V3", body)
        self.assertIn("tvproductions/ORTHO4XP_V3", body)


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.state_path = self.root / "state.json"
        self.state = WatchState.from_dict(
            {
                "schema_version": 1,
                "author": {
                    "repository": "Ypsos/ORTHO4XP_V3",
                    "branch": "ORTHO4XP_V3",
                },
                "passive_fork": {
                    "repository": "tvproductions/ORTHO4XP_V3",
                    "branch": "ORTHO4XP_V3",
                },
                "baseline": {
                    "reviewed_sha": "a" * 40,
                    "audit_id": "bootstrap-existing-baseline",
                    "audit_date": "2026-06-16",
                    "manifest_sha256": EMPTY_SHA256,
                    "path_count": 0,
                },
            }
        )
        self.state_path.write_bytes(canonical_json_bytes(self.state.to_dict()) + b"\n")
        self.observation = WatchObservation(
            status=WatchExit.CURRENT,
            author_repository=self.state.author.repository,
            author_branch=self.state.author.branch,
            baseline_sha=self.state.baseline.reviewed_sha,
            author_head=self.state.baseline.reviewed_sha,
            passive_repository=self.state.passive_fork.repository,
            passive_branch=self.state.passive_fork.branch,
            passive_head="9" * 40,
            passive_state=ForkState.BEHIND,
        )

    def test_help_lists_all_subcommands(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as context:
            main(["--help"])
        self.assertEqual(context.exception.code, 0)
        for command in ("check", "audit", "validate", "accept"):
            self.assertIn(command, stdout.getvalue())

    def test_audit_requires_explicit_sha_arguments(self) -> None:
        with (
            redirect_stderr(StringIO()),
            self.assertRaises(SystemExit) as context,
        ):
            main(["audit", "--state", str(self.state_path)])
        self.assertEqual(context.exception.code, 2)

    def test_check_writes_canonical_json_and_preserves_status(self) -> None:
        for status in WatchExit:
            with self.subTest(status=status):
                observation = WatchObservation(
                    status=status,
                    author_repository=self.observation.author_repository,
                    author_branch=self.observation.author_branch,
                    baseline_sha=self.observation.baseline_sha,
                    author_head=self.observation.author_head,
                    passive_repository=self.observation.passive_repository,
                    passive_branch=self.observation.passive_branch,
                    passive_head=self.observation.passive_head,
                    passive_state=self.observation.passive_state,
                )
                stdout = StringIO()
                with (
                    patch(
                        "scripts.upstream_watch_core.cli.perform_check",
                        return_value=observation,
                    ),
                    redirect_stdout(stdout),
                ):
                    result = main(["check", "--state", str(self.state_path), "--json"])
                self.assertEqual(result, status)
                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["status"], int(status))
                self.assertEqual(payload["passive_fork"]["state"], "behind")

    def test_manage_issue_requires_token_only_when_requested(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "scripts.upstream_watch_core.cli.perform_check",
                return_value=self.observation,
            ),
        ):
            self.assertEqual(
                main(["check", "--state", str(self.state_path)]),
                WatchExit.CURRENT,
            )
            stderr = StringIO()
            with redirect_stderr(stderr):
                result = main(
                    [
                        "check",
                        "--state",
                        str(self.state_path),
                        "--manage-issue",
                        "--repository",
                        "tvproductions/Ortho4XP",
                    ]
                )
            self.assertEqual(result, WatchExit.ERROR)
            self.assertIn("GITHUB_TOKEN", stderr.getvalue())

    def test_audit_writes_report_atomically_without_network_in_cli(self) -> None:
        report = AuditReport(
            schema_version=1,
            audit_id="ypsos-aaaaaaaaaaaa-bbbbbbbbbbbb",
            base_sha="a" * 40,
            head_sha="b" * 40,
            generated_at="2026-07-19T12:00:00Z",
            ancestry="fast-forward",
            commits=(),
            changes=(),
        )
        output = self.root / "report.json"
        with patch(
            "scripts.upstream_watch_core.cli.create_audit_from_remotes",
            return_value=report,
        ):
            result = main(
                [
                    "audit",
                    "--state",
                    str(self.state_path),
                    "--base",
                    report.base_sha,
                    "--head",
                    report.head_sha,
                    "--output",
                    str(output),
                ]
            )
        self.assertEqual(result, WatchExit.CURRENT)
        self.assertEqual(load_report(output), report)

    def test_keyboard_interrupt_returns_130(self) -> None:
        with patch(
            "scripts.upstream_watch_core.cli.perform_check",
            side_effect=KeyboardInterrupt,
        ):
            self.assertEqual(
                main(["check", "--state", str(self.state_path)]),
                130,
            )
