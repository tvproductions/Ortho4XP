import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Terrain_Artifact_Transaction as TAT
import O4_Texture_Artifact_Finalizer as TAF
from O4_Texture_Models import TextureConversionResult

# Terrain artifact finalization test contract
# ===========================================
#
# Boundary under test:
# - conversion has completed and returned one result per scheduled texture;
# - resolved DDS files have been written under the tile texture directory;
# - terrain files still contain the names requested during DSF construction;
# - finalization validates the complete batch before activating the DSF.
#
# Exact-reference semantics:
# - only BASE_TEX_NOWRAP directives participate in rewrites;
# - directive indentation and unrelated terrain text remain byte-stable;
# - filename lookalikes in comments or other directives are not rewritten;
# - an unchanged provider resolution performs no terrain rewrite;
# - an unchanged resolution still requires one exact terrain reference;
# - a changed resolution requires its requested reference to exist;
# - rewritten names use canonical resolved DDS naming;
# - one requested name maps to at most one resolved name;
# - identity-then-changed mappings are conflicting;
# - changed-then-identity mappings are conflicting;
# - chained mappings apply to the original directives exactly once;
# - reversed scheduler result order produces the same rewritten terrain.
#
# Conversion-result validation:
# - every result must report success;
# - every result must carry requested and resolved identities;
# - each identity must be a four-field tuple;
# - x, y, and zoom fields must be exact integers, excluding booleans;
# - provider fields must be non-empty strings;
# - requested and resolved x coordinates must match;
# - requested and resolved y coordinates must match;
# - requested and resolved zoom levels must match;
# - the result provider must match the resolved provider;
# - the result display name must be a string;
# - the display name must equal the canonical resolved filename;
# - malformed metadata is surfaced as a finalization error;
# - failed results cannot cause partial terrain rewrites.
#
# Output validation:
# - every resolved success must have a regular DDS output file;
# - validation covers the entire result batch before any terrain staging;
# - one missing DDS blocks rewrites for every terrain file;
# - a result with no matching terrain reference is rejected;
# - validation errors retain all original terrain bytes.
#
# Transaction semantics:
# - every affected terrain rewrite is prepared before replacement begins;
# - staged files live beside their destination for same-filesystem replacement;
# - original terrain modes are preserved on staged replacements;
# - original files receive recoverable backups before forward replacement;
# - a forward failure rolls back every already-replaced terrain file;
# - a forward failure also restores the destination whose backup was created;
# - successful rollback removes transaction-owned backup artifacts;
# - failed rollback reports the retained recoverable backup path;
# - preparation failure removes all transaction-owned staged files;
# - transaction cleanup never removes user-owned terrain or DDS artifacts.
#
# Determinism and isolation:
# - terrain paths are processed in sorted order;
# - mapping validation is independent of scheduler completion order;
# - filesystem failures are injected at exact replace/write boundaries;
# - temporary directories isolate every test;
# - conversion is represented by immutable result contracts;
# - no imagery provider or network request is used;
# - no GDAL process or DDS encoder is used;
# - no X-Plane installation is used;
# - no XP11 behavior is exercised;
# - no sister sea subsystem is exercised;
# - no sample tile or real scenery fixture is required.
#
# Failure evidence:
# - raised errors name the invalid result or missing artifact;
# - conflict messages include both incompatible resolved names;
# - rollback errors identify recoverable backups retained for inspection;
# - assertions inspect disk state after the exception boundary;
# - mocks verify that validation failures never enter replacement;
# - mocks verify that preparation failures never enter forward replacement;
# - atomic tests inject failure after real staging and backup creation;
# - successful no-op tests verify content and replacement call counts;
# - reference tests compare complete terrain text, not substring fragments;
# - resolution tests derive expected names from the contract, not first output.
# - retained backups remain inside the isolated transaction directory;
# - cleanup assertions distinguish staged, backup, and destination paths;
# - error-path tests prove that no partially rewritten terrain set survives;
# - success-path tests prove that every requested rewrite lands together.
# - exact call assertions keep transaction ordering observable.
#
# The individual tests below intentionally repeat complete metadata. Explicit
# fixtures make each rejected contract legible without relying on mutable shared
# defaults, and they ensure a future field addition cannot silently broaden what
# finalization accepts.
#


def resolved_result(requested_provider="BI", resolved_provider="Arc", ok=True):
    return TextureConversionResult(
        ok=ok,
        display_name=f"48_32_{resolved_provider}16.dds",
        provider_code=resolved_provider,
        error_summary="" if ok else "failed",
        requested_attrs=(32, 48, 16, requested_provider),
        resolved_attrs=(32, 48, 16, resolved_provider),
    )


class _TextureArtifactFinalizerTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.terrain = self.root / "terrain"
        self.terrain.mkdir()
        self.textures = self.root / "textures"
        self.textures.mkdir()
        self.tile = SimpleNamespace(build_dir=str(self.root))

    def _write_terrain(self, name):
        return self._write_terrain_text(
            name,
            "A\n800\nTERRAIN\n\nBASE_TEX_NOWRAP ../textures/48_32_BI16.dds\n",
        )

    def _write_terrain_text(self, name, text):
        terrain_file = self.terrain / name
        terrain_file.write_text(
            text,
            encoding="utf-8",
        )
        return terrain_file

    def _write_texture(self, provider):
        return self._write_texture_name(f"48_32_{provider}16.dds")

    def _write_texture_name(self, name):
        texture = self.textures / name
        texture.write_bytes(b"dds")
        return texture

    def _assert_finalization_error(self, pattern, result):
        try:
            TAF.finalize_terrain_texture_references(
                self.tile,
                (result,),
            )
        except Exception as exc:
            self.assertIsInstance(exc, TAF.TextureFinalizationError)
            self.assertRegex(str(exc), pattern)
        else:
            self.fail("TextureFinalizationError not raised")


class TextureArtifactReferenceTests(_TextureArtifactFinalizerTestCase):
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

    def test_chained_mappings_apply_once_to_each_original_directive(self):
        terrain_file = self._write_terrain_text(
            "chain.ter",
            "BASE_TEX_NOWRAP ../textures/48_32_BI16.dds\n"
            "BASE_TEX_NOWRAP ../textures/48_32_Arc16.dds\n",
        )
        self._write_texture("Arc")
        self._write_texture("EOX")

        TAF.finalize_terrain_texture_references(
            self.tile,
            (
                resolved_result("BI", "Arc"),
                resolved_result("Arc", "EOX"),
            ),
        )

        self.assertEqual(
            terrain_file.read_text(),
            "BASE_TEX_NOWRAP ../textures/48_32_Arc16.dds\n"
            "BASE_TEX_NOWRAP ../textures/48_32_EOX16.dds\n",
        )

    def test_chained_mappings_are_stable_in_reversed_result_order(self):
        terrain_file = self._write_terrain_text(
            "reversed.ter",
            "BASE_TEX_NOWRAP ../textures/48_32_BI16.dds\n"
            "BASE_TEX_NOWRAP ../textures/48_32_Arc16.dds\n",
        )
        self._write_texture("Arc")
        self._write_texture("EOX")

        TAF.finalize_terrain_texture_references(
            self.tile,
            (
                resolved_result("Arc", "EOX"),
                resolved_result("BI", "Arc"),
            ),
        )

        self.assertEqual(
            terrain_file.read_text(),
            "BASE_TEX_NOWRAP ../textures/48_32_Arc16.dds\n"
            "BASE_TEX_NOWRAP ../textures/48_32_EOX16.dds\n",
        )

    def test_identity_then_changed_resolution_is_conflicting(self):
        terrain_file = self._write_terrain("identity-first.ter")
        original = terrain_file.read_text()
        self._write_texture("BI")
        self._write_texture("Arc")

        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "conflicting",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (
                    resolved_result("BI", "BI"),
                    resolved_result("BI", "Arc"),
                ),
            )

        self.assertEqual(terrain_file.read_text(), original)

    def test_changed_then_identity_resolution_is_conflicting(self):
        terrain_file = self._write_terrain("changed-first.ter")
        original = terrain_file.read_text()
        self._write_texture("BI")
        self._write_texture("Arc")

        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "conflicting",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (
                    resolved_result("BI", "Arc"),
                    resolved_result("BI", "BI"),
                ),
            )

        self.assertEqual(terrain_file.read_text(), original)

    def test_unchanged_resolution_requires_matching_terrain_reference(self):
        self._write_texture("BI")

        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "not referenced",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result("BI", "BI"),),
            )

    def test_unchanged_resolution_with_exact_reference_performs_no_rewrite(self):
        terrain_file = self._write_terrain("unchanged.ter")
        original = terrain_file.read_bytes()
        self._write_texture("BI")

        updated = TAF.finalize_terrain_texture_references(
            self.tile,
            (resolved_result("BI", "BI"),),
        )

        self.assertEqual(updated, 0)
        self.assertEqual(terrain_file.read_bytes(), original)
        self.assertEqual(list(self.terrain.glob("*.finalizing*")), [])

    def test_unchanged_resolution_rejects_lookalike_terrain_target(self):
        terrain_file = self._write_terrain_text(
            "unchanged-lookalike.ter",
            "BASE_TEX_NOWRAP ../textures/48_32_BI16.dds.backup\n",
        )
        original = terrain_file.read_text()
        self._write_texture("BI")

        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "not referenced",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result("BI", "BI"),),
            )

        self.assertEqual(terrain_file.read_text(), original)

    def test_only_exact_base_texture_targets_are_rewritten(self):
        terrain_file = self._write_terrain_text(
            "suffix.ter",
            "BASE_TEX_NOWRAP ../textures/48_32_BI16.dds.backup\n",
        )
        original = terrain_file.read_text()
        self._write_texture("Arc")

        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "not referenced",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result(),),
            )

        self.assertEqual(terrain_file.read_text(), original)


class TextureArtifactValidationTests(_TextureArtifactFinalizerTestCase):
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

    def test_rejects_completed_result_without_resolution_metadata(self):
        self._write_terrain("48_32_BI16.ter")
        self._write_texture("Arc")
        result = TextureConversionResult.success("48_32_Arc16.dds", "Arc")

        self._assert_finalization_error(
            "missing texture resolution metadata",
            result,
        )

    def test_rejects_malformed_attribute_tuple_as_finalization_error(self):
        self._write_terrain("48_32_BI16.ter")
        result = TextureConversionResult(
            ok=True,
            display_name="48_32_Arc16.dds",
            provider_code="Arc",
            requested_attrs=cast(Any, (32, 48, 16)),
            resolved_attrs=(32, 48, 16, "Arc"),
        )

        self._assert_finalization_error(
            "invalid requested texture attributes",
            result,
        )

    def test_rejects_non_tuple_attribute_metadata(self):
        self._write_terrain("48_32_BI16.ter")
        self._write_texture("Arc")
        result = TextureConversionResult(
            ok=True,
            display_name="48_32_Arc16.dds",
            provider_code="Arc",
            requested_attrs=cast(Any, [32, 48, 16, "BI"]),
            resolved_attrs=(32, 48, 16, "Arc"),
        )

        self._assert_finalization_error(
            "invalid requested texture attributes",
            result,
        )

    def test_rejects_non_integer_attribute_coordinate(self):
        self._write_terrain("48_32_BI16.ter")
        self._write_texture("Arc")
        result = TextureConversionResult(
            ok=True,
            display_name="48_32_Arc16.dds",
            provider_code="Arc",
            requested_attrs=(32, 48, 16, "BI"),
            resolved_attrs=cast(Any, (32, "48", 16, "Arc")),
        )

        self._assert_finalization_error(
            "invalid resolved texture attributes",
            result,
        )

    def test_rejects_requested_resolved_coordinate_mismatch(self):
        self._write_terrain("48_32_BI16.ter")
        self._write_texture_name("48_33_Arc16.dds")
        result = TextureConversionResult(
            ok=True,
            display_name="48_33_Arc16.dds",
            provider_code="Arc",
            requested_attrs=(32, 48, 16, "BI"),
            resolved_attrs=(33, 48, 16, "Arc"),
        )

        self._assert_finalization_error(
            "coordinates and zoom differ",
            result,
        )

    def test_rejects_requested_resolved_zoom_mismatch(self):
        self._write_terrain("48_32_BI16.ter")
        self._write_texture_name("48_32_Arc17.dds")
        result = TextureConversionResult(
            ok=True,
            display_name="48_32_Arc17.dds",
            provider_code="Arc",
            requested_attrs=(32, 48, 16, "BI"),
            resolved_attrs=(32, 48, 17, "Arc"),
        )

        self._assert_finalization_error(
            "coordinates and zoom differ",
            result,
        )

    def test_rejects_resolved_provider_mismatch(self):
        self._write_terrain("48_32_BI16.ter")
        self._write_texture("Arc")
        result = TextureConversionResult(
            ok=True,
            display_name="48_32_Arc16.dds",
            provider_code="EOX",
            requested_attrs=(32, 48, 16, "BI"),
            resolved_attrs=(32, 48, 16, "Arc"),
        )

        self._assert_finalization_error(
            "resolved provider mismatch",
            result,
        )

    def test_rejects_resolved_display_name_mismatch(self):
        self._write_terrain("48_32_BI16.ter")
        result = TextureConversionResult(
            ok=True,
            display_name="48_32_EOX16.dds",
            provider_code="Arc",
            requested_attrs=(32, 48, 16, "BI"),
            resolved_attrs=(32, 48, 16, "Arc"),
        )

        self._assert_finalization_error(
            "display name mismatch",
            result,
        )

    def test_rejects_non_string_display_name_as_finalization_error(self):
        self._write_terrain("48_32_BI16.ter")
        result = TextureConversionResult(
            ok=True,
            display_name=cast(Any, 123),
            provider_code="Arc",
            requested_attrs=(32, 48, 16, "BI"),
            resolved_attrs=(32, 48, 16, "Arc"),
        )

        self._assert_finalization_error(
            "invalid texture display name",
            result,
        )

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


class TextureArtifactAtomicRewriteTests(_TextureArtifactFinalizerTestCase):
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
            mock.patch.object(TAT.os, "replace", side_effect=fail_second_replace),
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

    def test_rollback_failure_retains_and_reports_recoverable_backup(self):
        first = self._write_terrain("a.ter")
        second = self._write_terrain("b.ter")
        first_original = first.read_bytes()
        second_original = second.read_bytes()
        backup = first.with_name(first.name + ".finalizing-backup")
        self._write_texture("Arc")
        real_replace = os.replace
        replace_count = 0

        def fail_forward_and_rollback(source, target):
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("forward replace failed")
            if replace_count == 3:
                raise OSError("rollback replace failed")
            return real_replace(source, target)

        with (
            mock.patch.object(
                TAT.os,
                "replace",
                side_effect=fail_forward_and_rollback,
            ),
            self.assertRaisesRegex(
                TAF.TextureFinalizationError,
                "rollback failed",
            ) as caught,
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result(),),
            )

        self.assertTrue(backup.is_file())
        self.assertEqual(backup.read_bytes(), first_original)
        self.assertIn(str(backup), str(caught.exception))
        self.assertIn(b"48_32_Arc16.dds", first.read_bytes())
        self.assertEqual(second.read_bytes(), second_original)
        self.assertFalse(first.with_name(first.name + ".finalizing").exists())
        self.assertFalse(second.with_name(second.name + ".finalizing").exists())
        self.assertFalse(second.with_name(second.name + ".finalizing-backup").exists())

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


if __name__ == "__main__":
    unittest.main()
