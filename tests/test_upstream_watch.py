from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from scripts.upstream_watch_core.git_repo import (
    GitCommandError,
    GitRunner,
    classify_author_history,
    classify_passive_fork,
    list_changes,
    read_blob,
)
from scripts.upstream_watch_core.models import (
    ChangeStatus,
    ForkState,
    StateValidationError,
    WatchExit,
    canonical_json_bytes,
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
