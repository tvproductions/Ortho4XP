"""Git-history, diff, and host-isolation contracts for upstream watch."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from scripts.upstream_watch_core.git_repo import (
    GitCommandError,
    GitRunner,
    classify_author_history,
    classify_passive_fork,
    ensure_authoritative_candidate,
    fetch_required_objects,
    list_changes,
    read_blob,
)
from scripts.upstream_watch_core.models import (
    ChangeStatus,
    ForkState,
    WatchExit,
)
from tests._path import ROOT_DIR  # noqa: F401
from tests._upstream_watch_helpers import (
    run_test_git as _run_test_git,
)
from tests._upstream_watch_helpers import (
    write_test_file as _write_test_file,
)


class GitRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repo = Path(self.temporary_directory.name, "repo")
        self.repo.mkdir()
        self._git("init", "-q")
        self._git("config", "user.name", "Upstream Watch Tests")
        self._git("config", "user.email", "upstream-watch@example.invalid")
        self.base = self._create_base()
        self.author_head = self._create_author_history()
        self.fork_ahead, self.fork_diverged = self._create_forks()
        self.runner = GitRunner(self.repo)

    def _create_base(self) -> str:
        self._write("tracked.txt", "base\n")
        self._write("renamed-before.txt", "rename me\n")
        self._write("delete-me.txt", "delete me\n")
        self._write("copy-source.txt", "copy me\n")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "base")
        base = self._git("rev-parse", "HEAD")
        self._git("branch", "fork-behind", base)
        return base

    def _create_author_history(self) -> str:
        self._write("tracked.txt", "author\n")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "author first")
        self._git("mv", "renamed-before.txt", "renamed-after.txt")
        Path(self.repo, "delete-me.txt").unlink()
        self._write("new.txt", "new\n")
        self._write("copy-target.txt", "copy me\n")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "author second")
        return self._git("rev-parse", "HEAD")

    def _create_forks(self) -> tuple[str, str]:
        self._git("checkout", "-q", "-b", "fork-ahead")
        self._write("fork.txt", "fork-only\n")
        self._git("add", "fork.txt")
        self._git("commit", "-q", "-m", "fork ahead")
        fork_ahead = self._git("rev-parse", "HEAD")

        self._git("checkout", "-q", "-b", "fork-diverged", self.base)
        self._write("diverged.txt", "diverged\n")
        self._git("add", "diverged.txt")
        self._git("commit", "-q", "-m", "fork diverged")
        return fork_ahead, self._git("rev-parse", "HEAD")

    def _git(self, *args: str) -> str:
        return _run_test_git(self.repo, *args)

    def _write(self, relative: str, content: str) -> None:
        _write_test_file(self.repo, relative, content)

    def test_classifies_author_history(self) -> None:
        # A missing accepted object is rewritten history, not tool failure.
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
        self.assertEqual(
            classify_author_history(self.runner, "f" * 40, self.author_head),
            WatchExit.HISTORY_REWRITE,
        )

    def test_rejects_passive_only_audit_candidate(self) -> None:
        ensure_authoritative_candidate(self.runner, self.author_head, self.author_head)
        with self.assertRaisesRegex(GitCommandError, "authoritative"):
            ensure_authoritative_candidate(
                self.runner, self.fork_ahead, self.author_head
            )

    def test_fetches_orphaned_required_object_by_exact_sha(self) -> None:
        # A rewritten branch can still be audited when either remote retains
        # the immutable reviewed object outside its current branch history.
        target = Path(self.temporary_directory.name, "target.git")
        self._git("init", "--bare", str(target))
        target_runner = GitRunner(target)
        target_runner.run(
            [
                "fetch",
                "--no-tags",
                str(self.repo),
                f"{self.author_head}:refs/upstream-watch/author",
            ]
        )
        with self.assertRaises(GitCommandError):
            target_runner.run(["cat-file", "-e", f"{self.fork_diverged}^{{commit}}"])
        fetch_required_objects(
            target_runner,
            (self.fork_diverged,),
            (str(self.repo),),
        )
        target_runner.run(["cat-file", "-e", f"{self.fork_diverged}^{{commit}}"])

    def test_reports_unavailable_required_object_for_full_tree_audit(self) -> None:
        # When both repositories have discarded the object, operators receive
        # an explicit recovery failure instead of a misleading Git error.
        target = Path(self.temporary_directory.name, "missing.git")
        self._git("init", "--bare", str(target))
        with self.assertRaisesRegex(GitCommandError, "full-tree"):
            fetch_required_objects(
                GitRunner(target),
                ("e" * 40,),
                (str(self.repo),),
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
        # Rename and copy evidence retains both paths and deterministic counts.
        changes = list_changes(self.runner, self.base, self.author_head)
        by_path = {change.path: change for change in changes}
        self.assertEqual(by_path["new.txt"].status, ChangeStatus.ADDED)
        self.assertEqual(by_path["delete-me.txt"].status, ChangeStatus.DELETED)
        self.assertEqual(by_path["renamed-after.txt"].status, ChangeStatus.RENAMED)
        self.assertEqual(by_path["copy-target.txt"].status, ChangeStatus.COPIED)
        self.assertEqual(by_path["copy-target.txt"].previous_path, "copy-source.txt")
        self.assertEqual(
            by_path["renamed-after.txt"].previous_path, "renamed-before.txt"
        )
        self.assertEqual(by_path["tracked.txt"].additions, 1)
        self.assertEqual(by_path["tracked.txt"].deletions, 1)

    def test_git_runner_neutralizes_host_configuration_and_hooks(self) -> None:
        with patch("scripts.upstream_watch_core.git_repo.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=["git"], returncode=0, stdout="", stderr=""
            )
            GitRunner(self.repo).run(["status", "--porcelain"])
        environment = cast(dict[str, str], run.call_args.kwargs["env"])
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(environment["GIT_CONFIG_KEY_0"], "core.hooksPath")
        hooks_path = Path(environment["GIT_CONFIG_VALUE_0"])
        self.assertTrue(hooks_path.is_absolute())
        self.assertNotEqual(hooks_path, self.repo / ".git" / "hooks")

    def test_reads_blob_without_checkout(self) -> None:
        self.assertEqual(read_blob(self.runner, self.author_head, "new.txt"), b"new\n")

    def test_redacts_credentials_from_git_errors(self) -> None:
        with self.assertRaises(GitCommandError) as context:
            self.runner.run(
                ["show", "https://secret-token@github.com/example/repo.git"]
            )
        self.assertNotIn("secret-token", str(context.exception))
