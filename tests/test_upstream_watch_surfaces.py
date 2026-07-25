"""Repository-level consistency checks for the upstream-watch chore."""

import unittest

from scripts.upstream_watch_core.ledger import parse_ledger
from scripts.upstream_watch_core.models import load_state
from tests._path import ROOT_DIR


class RepositorySurfaceTests(unittest.TestCase):
    def test_committed_state_and_ledger_preserve_repository_roles(self) -> None:
        # Durable evidence keeps author and passive-fork roles unambiguous.
        state = load_state(ROOT_DIR / ".github" / "upstream-watch.json")
        self.assertEqual(state.author.repository, "Ypsos/ORTHO4XP_V3")
        self.assertEqual(state.passive_fork.repository, "tvproductions/ORTHO4XP_V3")
        self.assertEqual(
            state.baseline.reviewed_sha,
            "4ca0a8d404b078ad899979bafde84769a0fb235b",
        )

        entries = parse_ledger(ROOT_DIR / "docs" / "upstream" / "ORTHO4XP_V3-audit.md")
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry.audit.audit_id, "ypsos-4ca0a8d404b0-8a25af093af7")
        self.assertEqual(
            entry.audit.head_sha,
            "8a25af093af758292b4ef4c2caff93719cb1a54a",
        )
        paths: list[str] = []
        for finding in entry.findings:
            paths.extend(finding.paths)
        paths.extend(record.path for record in entry.reviewed_no_action)
        self.assertEqual(len(paths), 48)
        self.assertEqual(len(paths), len(set(paths)))

    def test_backlog_records_completion_and_independent_followup_requirements(
        self,
    ) -> None:
        # Follow-up work remains executable without deleted upstream files.
        text = (ROOT_DIR / "TODO.md").read_text(encoding="utf-8")
        section_041_3 = text.split("### TODO-041-3:", 1)[1].split("### ", 1)[0]
        section_044 = text.split("### TODO-044:", 1)[1].split("### ", 1)[0]
        section_045 = text.split("### TODO-045:", 1)[1].split("### ", 1)[0]
        self.assertIn("Status: Done", section_041_3)
        self.assertNotIn("O4_GPU_Backend", section_044)
        self.assertNotIn("O4_Backup_Manager", section_045)
        self.assertNotIn("rollback.py", section_045)
        self.assertIn("benchmark", section_044.casefold())
        self.assertIn("checksum", section_045.casefold())

    def test_workflow_has_narrow_permissions_and_expected_triggers(self) -> None:
        # The scheduled mutation boundary is limited to managed issues.
        workflow = (
            ROOT_DIR / ".github" / "workflows" / "upstream-watch.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('cron: "17 13 * * 1"', workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("concurrency:", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertNotIn("contents: write", workflow)
