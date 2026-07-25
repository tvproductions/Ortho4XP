"""Portable mode contracts for atomic terrain staging.

Forward candidates and rollback backups both replace the original terrain on
different transaction paths, so each must inherit its mode. Mode-copy failures
are preparation failures and may not leave transaction-owned files behind.
"""

import shutil
import stat
import tempfile
import unittest
from pathlib import Path
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

    def test_staged_candidate_and_backup_preserve_original_mode(self):
        terrain_file = self._terrain_file()
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
            for _terrain, candidate, backup in staged:
                candidate.chmod(stat.S_IREAD | stat.S_IWRITE)
                backup.chmod(stat.S_IREAD | stat.S_IWRITE)
            TAT._cleanup_staged_files(staged)
            terrain_file.chmod(stat.S_IREAD | stat.S_IWRITE)

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
