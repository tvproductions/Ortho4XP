import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Artifact_Finalizer as TAF
from O4_Texture_Models import TextureConversionResult


def resolved_result(requested_provider="BI", resolved_provider="Arc", ok=True):
    return TextureConversionResult(
        ok=ok,
        display_name=f"48_32_{resolved_provider}16.dds",
        provider_code=resolved_provider,
        error_summary="" if ok else "failed",
        requested_attrs=(32, 48, 16, requested_provider),
        resolved_attrs=(32, 48, 16, resolved_provider),
    )


class TextureArtifactFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.terrain = self.root / "terrain"
        self.terrain.mkdir()
        self.textures = self.root / "textures"
        self.textures.mkdir()
        self.tile = SimpleNamespace(build_dir=str(self.root))

    def test_rewrites_requested_reference_to_resolved_dds(self):
        terrain_file = self._write_terrain("48_32_BI16_sea.ter")
        self._write_texture("Arc")

        updated = TAF.finalize_terrain_texture_references(
            self.tile,
            (resolved_result(),),
        )

        self.assertEqual(updated, 1)
        self.assertIn(
            "BASE_TEX_NOWRAP ../textures/48_32_Arc16.dds\n",
            terrain_file.read_text(),
        )

    def test_rejects_failed_conversion_without_rewriting(self):
        terrain_file = self._write_terrain("48_32_BI16.ter")
        original = terrain_file.read_text()

        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "conversion failed",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result(ok=False),),
            )

        self.assertEqual(terrain_file.read_text(), original)

    def test_rejects_reported_success_when_resolved_dds_is_missing(self):
        terrain_file = self._write_terrain("48_32_BI16.ter")
        original = terrain_file.read_text()

        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "missing DDS output",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result(),),
            )

        self.assertEqual(terrain_file.read_text(), original)

    def test_rejects_conflicting_resolutions_for_one_requested_texture(self):
        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "conflicting",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (
                    resolved_result(resolved_provider="Arc"),
                    resolved_result(resolved_provider="EOX"),
                ),
            )

    def test_rejects_resolution_with_no_matching_terrain_reference(self):
        self._write_texture("Arc")

        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "not referenced",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result(),),
            )

    def test_atomic_rewrite_failure_rolls_back_all_terrain_files(self):
        first = self._write_terrain("a.ter")
        second = self._write_terrain("b.ter")
        originals = {path: path.read_text() for path in (first, second)}
        self._write_texture("Arc")
        real_replace = os.replace
        replace_count = 0

        def fail_second_replace(source, target):
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("replace failed")
            return real_replace(source, target)

        with (
            mock.patch.object(TAF.os, "replace", side_effect=fail_second_replace),
            self.assertRaisesRegex(
                TAF.TextureFinalizationError,
                "atomic terrain rewrite failed",
            ),
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result(),),
            )

        self.assertEqual(
            {path: path.read_text() for path in (first, second)},
            originals,
        )
        self.assertEqual(list(self.terrain.glob("*.finalizing*")), [])

    def test_atomic_rewrite_preparation_failure_removes_staged_files(self):
        terrain_file = self._write_terrain("a.ter")
        original = terrain_file.read_text()
        self._write_texture("Arc")
        real_write_bytes = Path.write_bytes
        write_count = 0

        def fail_backup_write(path, data):
            nonlocal write_count
            write_count += 1
            if write_count == 2:
                raise OSError("backup write failed")
            return real_write_bytes(path, data)

        with (
            mock.patch.object(
                Path,
                "write_bytes",
                autospec=True,
                side_effect=fail_backup_write,
            ),
            self.assertRaisesRegex(
                TAF.TextureFinalizationError,
                "before replacement",
            ),
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result(),),
            )

        self.assertEqual(terrain_file.read_text(), original)
        self.assertEqual(list(self.terrain.glob("*.finalizing*")), [])

    def _write_terrain(self, name):
        terrain_file = self.terrain / name
        terrain_file.write_text(
            "A\n800\nTERRAIN\n\nBASE_TEX_NOWRAP ../textures/48_32_BI16.dds\n",
            encoding="utf-8",
        )
        return terrain_file

    def _write_texture(self, provider):
        texture = self.textures / f"48_32_{provider}16.dds"
        texture.write_bytes(b"dds")
        return texture


if __name__ == "__main__":
    unittest.main()
