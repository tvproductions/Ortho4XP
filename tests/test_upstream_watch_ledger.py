"""Durable audit-ledger coverage and baseline-transition contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.upstream_watch_core.ledger import (
    LedgerValidationError,
    advance_baseline,
    parse_ledger,
    validate_coverage,
)
from scripts.upstream_watch_core.models import (
    AuditReport,
    ChangeStatus,
    PathChange,
    WatchState,
    canonical_json_bytes,
    load_state,
)
from tests._path import ROOT_DIR  # noqa: F401
from tests._upstream_watch_helpers import state_payload as _state_payload


def _ledger_report() -> AuditReport:
    return AuditReport(
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


class LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.state_path = self.root / "state.json"
        self.ledger_path = self.root / "ledger.md"
        self.report = _ledger_report()
        self.state = WatchState.from_dict(_state_payload(self.report.base_sha))
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
        overrides: dict[str, object] | None = None,
    ) -> dict[str, object]:
        finding: dict[str, object] = {
            "audit_id": self.report.audit_id,
            "finding_id": finding_id,
            "paths": paths,
            "disposition": "reject",
            "rationale": "Not compatible with the local architecture.",
            "work_items": [],
            "xp12_compatibility": "Reviewed for strict XP12 behavior.",
        }
        finding.update(overrides or {})
        return finding

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
        # Every manifest path receives one semantic disposition.
        self._write_ledger(
            [
                self._finding(
                    "provider",
                    ["Providers/Global/Test.lay"],
                    {"disposition": "reject"},
                ),
                self._finding(
                    "source",
                    ["src/O4_Example.py"],
                    {
                        "disposition": "reimplement",
                        "work_items": ["TODO-999", "#999"],
                    },
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
        # Missing, repeated, or fabricated paths invalidate the audit.
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
        # Decisions require rationale and trackable accepted work.
        cases = (
            self._finding(
                "empty",
                ["Providers/Global/Test.lay"],
                {"rationale": ""},
            ),
            self._finding(
                "unlinked",
                ["Providers/Global/Test.lay"],
                {"disposition": "adopt"},
            ),
        )
        for finding in cases:
            with self.subTest(finding=finding["finding_id"]):
                self._write_ledger([finding])
                with self.assertRaises(LedgerValidationError):
                    parse_ledger(self.ledger_path)

    def test_investigate_blocks_baseline_advancement(self) -> None:
        # Investigation is evidence but cannot authorize state advancement.
        self._write_ledger(
            [
                self._finding(
                    "provider",
                    ["Providers/Global/Test.lay"],
                    {
                        "disposition": "investigate",
                        "work_items": ["TODO-041-4", "#41"],
                    },
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
        # Ledger decisions bind to the exact canonical report manifest.
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
        # Complete review advances every baseline evidence field together.
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
        # Replacement failure preserves the accepted baseline byte for byte.
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
