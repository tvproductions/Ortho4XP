"""Portable mode contracts for atomic terrain staging.

Forward candidates and rollback backups both replace the original terrain on
different transaction paths, so each must inherit its mode. Mode-copy failures
are preparation failures and may not leave transaction-owned files behind.

Windows additionally rejects replacing an existing read-only destination.
These tests therefore cover the complete mode lifecycle: make the destination
writable only for replacement, restore its exact mode on every path, retry
read-only staging cleanup, and preserve a failed rollback backup unchanged as
recoverable evidence.
"""

import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Terrain_Artifact_Transaction as TAT


class TerrainArtifactTransactionModeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def _terrain_file(self, name="mode.ter"):
        terrain_file = self.root / name
        terrain_file.write_bytes(b"original")
        return terrain_file

    def _make_writable(self, path):
        if path.exists():
            path.chmod(stat.S_IREAD | stat.S_IWRITE)

    def _read_only_terrain_pair(self):
        first = self._terrain_file("first.ter")
        second = self._terrain_file("second.ter")
        self.addCleanup(self._make_writable, first)
        self.addCleanup(self._make_writable, second)
        first.chmod(stat.S_IREAD)
        second.chmod(stat.S_IREAD)
        modes = (
            stat.S_IMODE(first.stat().st_mode),
            stat.S_IMODE(second.stat().st_mode),
        )
        return first, second, modes

    def _forward_and_rollback_failure(self, writable_during_replace):
        real_replace = os.replace

        def inject_failures(source, destination):
            writable_during_replace.append(
                bool(destination.stat().st_mode & stat.S_IWRITE)
            )
            if source.name == "second.ter.finalizing":
                raise OSError("injected forward failure")
            if source.name == "first.ter.finalizing-backup":
                raise OSError("injected rollback failure")
            real_replace(source, destination)

        return inject_failures

    def _assert_retained_backup(self, terrain_files, modes, error):
        first, second = terrain_files
        backup = first.with_name("first.ter.finalizing-backup")
        self.addCleanup(self._make_writable, backup)
        self.assertIn(str(backup), str(error))
        self.assertEqual(first.read_bytes(), b"first updated")
        self.assertEqual(second.read_bytes(), b"original")
        self.assertEqual(backup.read_bytes(), b"original")
        self.assertEqual(stat.S_IMODE(first.stat().st_mode), modes[0])
        self.assertEqual(stat.S_IMODE(second.stat().st_mode), modes[1])
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), modes[0])
        self.assertEqual(list(self.root.glob("*.finalizing*")), [backup])

    def test_staged_candidate_and_backup_preserve_original_mode(self):
        terrain_file = self._terrain_file()
        self.addCleanup(self._make_writable, terrain_file)
        terrain_file.chmod(stat.S_IREAD)
        original_mode = stat.S_IMODE(terrain_file.stat().st_mode)
        staged = []

        try:
            with mock.patch.object(
                shutil,
                "copymode",
                wraps=shutil.copymode,
            ) as copy_mode:
                staged = TAT._stage_terrain_files(
                    {terrain_file: (terrain_file.read_bytes(), b"updated")}
                )

            _terrain, candidate, backup = staged[0]
            self.assertEqual(
                copy_mode.call_args_list,
                [
                    mock.call(terrain_file, candidate),
                    mock.call(terrain_file, backup),
                ],
            )
            self.assertEqual(stat.S_IMODE(candidate.stat().st_mode), original_mode)
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), original_mode)
        finally:
            TAT._cleanup_staged_files(staged)
        self.assertEqual(list(self.root.glob("*.finalizing*")), [])

    @unittest.skipUnless(os.name == "nt", "Windows read-only replacement semantics")
    def test_read_only_terrain_replaces_successfully_and_preserves_mode(self):
        terrain_file = self._terrain_file("read-only-success.ter")
        self.addCleanup(self._make_writable, terrain_file)
        terrain_file.chmod(stat.S_IREAD)
        original_mode = stat.S_IMODE(terrain_file.stat().st_mode)

        TAT.replace_terrain_files_atomically({terrain_file: (b"original", b"updated")})

        self.assertEqual(terrain_file.read_bytes(), b"updated")
        self.assertEqual(stat.S_IMODE(terrain_file.stat().st_mode), original_mode)
        self.assertEqual(list(self.root.glob("*.finalizing*")), [])

    def test_forward_failure_restores_read_only_destination_and_cleans_staging(self):
        terrain_file = self._terrain_file("forward-failure.ter")
        self.addCleanup(self._make_writable, terrain_file)
        terrain_file.chmod(stat.S_IREAD)
        original_mode = stat.S_IMODE(terrain_file.stat().st_mode)
        writable_during_replace = []

        def fail_forward(_source, destination):
            writable_during_replace.append(
                bool(destination.stat().st_mode & stat.S_IWRITE)
            )
            raise OSError("injected forward failure")

        with (
            mock.patch.object(TAT.os, "replace", side_effect=fail_forward),
            self.assertRaisesRegex(
                TAT.TextureFinalizationError,
                "injected forward failure",
            ),
        ):
            TAT.replace_terrain_files_atomically(
                {terrain_file: (b"original", b"updated")}
            )

        self.assertEqual(writable_during_replace, [True])
        self.assertEqual(terrain_file.read_bytes(), b"original")
        self.assertEqual(stat.S_IMODE(terrain_file.stat().st_mode), original_mode)
        self.assertEqual(list(self.root.glob("*.finalizing*")), [])

    def test_rollback_failure_restores_modes_and_retains_original_backup(self):
        first, second, modes = self._read_only_terrain_pair()
        writable_during_replace = []

        with (
            mock.patch.object(
                TAT.os,
                "replace",
                side_effect=self._forward_and_rollback_failure(writable_during_replace),
            ),
            self.assertRaisesRegex(
                TAT.TextureFinalizationError,
                "rollback failed",
            ) as raised,
        ):
            TAT.replace_terrain_files_atomically(
                {
                    first: (b"original", b"first updated"),
                    second: (b"original", b"second updated"),
                }
            )

        self.assertEqual(writable_during_replace, [True, True, True])
        self._assert_retained_backup((first, second), modes, raised.exception)

    def test_read_only_cleanup_clears_write_bit_and_retries_unlink(self):
        candidate = mock.Mock()
        candidate.stat.return_value = SimpleNamespace(st_mode=stat.S_IREAD)
        candidate.unlink.side_effect = [PermissionError("read only"), None]
        backup = mock.sentinel.backup

        errors = TAT._cleanup_staged_files(
            [(mock.sentinel.terrain, candidate, backup)],
            preserve={backup},
        )

        candidate.chmod.assert_called_once_with(stat.S_IREAD | stat.S_IWRITE)
        self.assertEqual(candidate.unlink.call_count, 2)
        self.assertEqual(errors, [])

    def test_mode_copy_failure_removes_staged_files(self):
        terrain_file = self._terrain_file("mode-failure.ter")
        original = terrain_file.read_bytes()

        with (
            mock.patch.object(
                TAT.shutil,
                "copymode",
                side_effect=OSError("mode copy failed"),
            ),
            self.assertRaisesRegex(
                TAT.TextureFinalizationError,
                "before replacement",
            ),
        ):
            TAT.replace_terrain_files_atomically({terrain_file: (original, b"updated")})

        self.assertEqual(terrain_file.read_bytes(), original)
        self.assertEqual(list(self.root.glob("*.finalizing*")), [])


if __name__ == "__main__":
    unittest.main()
