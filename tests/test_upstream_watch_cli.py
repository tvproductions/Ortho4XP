from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts.upstream_watch_core.cli import main
from scripts.upstream_watch_core.github_api import (
    WatchObservation,
)
from scripts.upstream_watch_core.models import (
    AuditReport,
    ForkState,
    WatchExit,
    WatchState,
    canonical_json_bytes,
    load_report,
)
from tests._path import ROOT_DIR  # noqa: F401
from tests._upstream_watch_helpers import state_payload as _state_payload


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.state_path = self.root / "state.json"
        self.state = WatchState.from_dict(_state_payload("a" * 40))
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
