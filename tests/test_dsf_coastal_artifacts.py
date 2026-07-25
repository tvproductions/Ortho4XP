import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Coastal_Artifact_Policy as CAP
import O4_DSF_Coastal_Artifacts as DCA
import O4_DSF_Utils as DSF


class DsfCoastalArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        build_dir = Path(self.temp_dir.name)
        (build_dir / "textures").mkdir()
        self.tile = SimpleNamespace(
            build_dir=str(build_dir),
            lat=45,
            lon=-90,
            mask_zl=14,
            imprint_masks_to_dds=False,
            use_decal_on_terrain=True,
            terrain_casts_shadows=True,
        )

    def _terrain_text(self, tri_type, decision=None):
        with (
            mock.patch.object(
                DSF.GEO,
                "gtile_to_wgs84",
                return_value=(45.0, -90.0),
            ),
            mock.patch.object(
                DSF.GEO,
                "webmercator_pixel_size",
                return_value=2.0,
            ),
        ):
            name = DSF.create_terrain_file(
                self.tile,
                "48_32_BI16.dds",
                32,
                48,
                16,
                tri_type,
                bool(decision and decision.is_overlay),
                coastal_decision=decision,
            )
        return (Path(self.tile.build_dir) / "terrain" / name).read_text()

    def _first_coastal_lookup(self, texture_attributes, artifacts, mask_image):
        with (
            mock.patch.object(
                DCA,
                "provider_uses_explicit_extent",
                return_value=False,
            ),
            mock.patch.object(
                DCA,
                "load_inferred_coastal_mask",
                return_value=mask_image,
            ),
        ):
            return DCA.coastal_artifact(
                self.tile,
                texture_attributes,
                2,
                artifacts,
            )

    def test_existing_external_mask_emits_border_reference(self):
        mask_name = "48_32_ZL16.png"
        (Path(self.tile.build_dir) / "textures" / mask_name).write_bytes(b"mask")
        text = self._terrain_text(
            2,
            CAP.CoastalMaskDecision.external_border(mask_name),
        )
        self.assertIn(f"BORDER_TEX ../textures/{mask_name}\n", text)
        self.assertNotIn("WATER_COLOR_MASK\n", text)

    def test_disappeared_external_mask_fails_instead_of_changing_directive(self):
        with self.assertRaises(FileNotFoundError):
            self._terrain_text(
                2,
                CAP.CoastalMaskDecision.external_border("missing.png"),
            )

    def test_unreadable_inferred_mask_is_unavailable_before_decision(self):
        texture_attributes = (32, 48, 16, "BI")
        with mock.patch.object(
            DSF.MASK,
            "needs_mask",
            side_effect=OSError("unreadable"),
        ):
            mask = DCA.load_inferred_coastal_mask(
                self.tile,
                texture_attributes,
                explicit_extent=False,
            )
        self.assertFalse(mask)

    def test_cache_retains_only_decision_and_returns_mask_once(self):
        texture_attributes = (32, 48, 16, "BI")
        terrain_attributes = (texture_attributes, 2)
        artifacts = {}
        mask_image = Image.new("L", (4, 4), 255)
        self.addCleanup(mask_image.close)

        first_decision, first_mask = self._first_coastal_lookup(
            texture_attributes,
            artifacts,
            mask_image,
        )

        self.assertIs(first_mask, mask_image)
        self.assertIsInstance(artifacts[terrain_attributes], CAP.CoastalMaskDecision)

        with mock.patch.object(
            DCA,
            "load_inferred_coastal_mask",
            side_effect=AssertionError("cache hit reloaded a mask"),
        ):
            second_decision, second_mask = DCA.coastal_artifact(
                self.tile,
                texture_attributes,
                2,
                artifacts,
            )

        self.assertIs(second_decision, first_decision)
        self.assertIsNone(second_mask)
        self.assertFalse(
            any(isinstance(value, Image.Image) for value in artifacts.values())
        )

    def test_inferred_mask_source_is_closed_after_crop(self):
        source_image = mock.Mock()
        cropped_image = Image.new("L", (4, 4), 255)
        self.addCleanup(cropped_image.close)
        source_image.crop.return_value = cropped_image

        with (
            mock.patch.object(DSF.MASK.os.path, "isfile", return_value=True),
            mock.patch.object(DSF.MASK.Image, "open", return_value=source_image),
        ):
            result = DSF.MASK.needs_mask(
                self.tile,
                32,
                48,
                self.tile.mask_zl,
            )

        self.assertIs(result, cropped_image)
        source_image.close.assert_called_once_with()

    def test_land_decal_is_never_emitted_for_ocean(self):
        ocean = self._terrain_text(
            2,
            CAP.CoastalMaskDecision.imprinted_alpha("mask.png"),
        )
        inland = self._terrain_text(1)
        land = self._terrain_text(0)
        self.assertNotIn("DECAL_LIB", ocean)
        self.assertNotIn("DECAL_LIB", inland)
        self.assertIn("DECAL_LIB", land)


if __name__ == "__main__":
    unittest.main()
