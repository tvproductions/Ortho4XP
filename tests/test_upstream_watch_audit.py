from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from scripts.upstream_watch_core.audit import (
    _run_targeted_ruff,
    build_audit_report,
    inspect_python_blob,
    write_report,
)
from scripts.upstream_watch_core.git_repo import (
    GitRunner,
)
from scripts.upstream_watch_core.models import (
    WatchState,
    load_report,
)
from tests._path import ROOT_DIR  # noqa: F401
from tests._upstream_watch_helpers import (
    run_test_git as _run_test_git,
)
from tests._upstream_watch_helpers import (
    state_payload as _state_payload,
)
from tests._upstream_watch_helpers import (
    write_test_file as _write_test_file,
)


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
        self.state = WatchState.from_dict(_state_payload(self.base))

    def _git(self, *args: str) -> str:
        return _run_test_git(self.repo, *args)

    def _write(self, relative: str, content: str) -> None:
        _write_test_file(self.repo, relative, content)

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

    def test_ruff_materializes_blobs_under_safe_generated_names(self) -> None:
        observed_files: list[str] = []

        def fake_ruff(command: list[str], **_kwargs: object):
            root = Path(command[-1])
            materialized = sorted(root.rglob("*.py"))
            observed_files.extend(path.name for path in materialized)
            findings = [
                {"filename": str(path), "code": "E999"} for path in materialized
            ]
            return subprocess.CompletedProcess(
                args=command,
                returncode=1,
                stdout=json.dumps(findings),
                stderr="",
            )

        with patch(
            "scripts.upstream_watch_core.audit.subprocess.run",
            side_effect=fake_ruff,
        ):
            result = _run_targeted_ruff(
                {
                    "src/Foo.py": b"UPPER = True\n",
                    "src/foo.py": b"lower = True\n",
                    "src/con.py": b"device = False\n",
                },
                "ruff",
            )
        self.assertEqual(observed_files, ["0000.py", "0001.py", "0002.py"])
        findings = cast(list[dict[str, object]], result["findings"])
        self.assertEqual(
            sorted(cast(str, finding["filename"]) for finding in findings),
            ["src/Foo.py", "src/con.py", "src/foo.py"],
        )

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
