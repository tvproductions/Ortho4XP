import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Coastal_Artifact_Policy as CAP


class CoastalArtifactPolicyTests(unittest.TestCase):
    def test_missing_ocean_mask_selects_native_water_before_pool_selection(self):
        decision = CAP.decide_coastal_mask(
            tri_type=2,
            imprint_masks_to_dds=False,
            mask_file_name=None,
            explicit_provider_extent=False,
        )
        self.assertEqual(
            decision.disposition,
            CAP.CoastalMaskDisposition.NATIVE_WATER,
        )
        self.assertFalse(decision.creates_custom_terrain)
        self.assertFalse(decision.is_overlay)

    def test_external_mask_is_retained_border_resource(self):
        decision = CAP.decide_coastal_mask(
            tri_type=2,
            imprint_masks_to_dds=False,
            mask_file_name="48_32_ZL16.png",
            explicit_provider_extent=False,
        )
        self.assertEqual(
            decision.disposition,
            CAP.CoastalMaskDisposition.EXTERNAL_BORDER,
        )
        self.assertTrue(decision.creates_custom_terrain)
        self.assertTrue(decision.is_overlay)
        self.assertFalse(decision.cleanup_after_conversion)

    def test_imprinted_mask_is_success_only_conversion_input(self):
        decision = CAP.decide_coastal_mask(
            tri_type=2,
            imprint_masks_to_dds=True,
            mask_file_name="48_32_ZL16.png",
            explicit_provider_extent=False,
        )
        self.assertEqual(
            decision.disposition,
            CAP.CoastalMaskDisposition.IMPRINTED_ALPHA,
        )
        self.assertTrue(decision.creates_custom_terrain)
        self.assertFalse(decision.is_overlay)
        self.assertTrue(decision.cleanup_after_conversion)

    def test_explicit_extent_suppresses_inferred_mask_in_both_modes(self):
        for imprint in (False, True):
            with self.subTest(imprint=imprint):
                decision = CAP.decide_coastal_mask(
                    tri_type=2,
                    imprint_masks_to_dds=imprint,
                    mask_file_name="48_32_ZL16.png",
                    explicit_provider_extent=True,
                )
                self.assertEqual(
                    decision.disposition,
                    CAP.CoastalMaskDisposition.NATIVE_WATER,
                )

    def test_provider_extent_classifier_handles_simple_and_combined_providers(self):
        providers = {
            "BI": {"extent": "global"},
            "LOCAL": {"extent": "county"},
        }
        combined = {
            "COMB": [
                {"layer_code": "BI", "extent_code": "global"},
                {"layer_code": "LOCAL", "extent_code": "!county"},
            ]
        }
        self.assertFalse(CAP.provider_uses_explicit_extent("BI", providers, combined))
        self.assertTrue(CAP.provider_uses_explicit_extent("LOCAL", providers, combined))
        self.assertTrue(CAP.provider_uses_explicit_extent("COMB", providers, combined))

    def test_coordinate_contract_distinguishes_border_and_imprinted_water(self):
        external = CAP.CoastalMaskDecision.external_border("mask.png")
        imprinted = CAP.CoastalMaskDecision.imprinted_alpha("mask.png")
        self.assertEqual(
            CAP.water_texture_coordinates(external, (0.2, 0.3), (1.0, 0.4)),
            (0.2, 0.3, 0.2, 0.3),
        )
        self.assertEqual(
            CAP.water_texture_coordinates(imprinted, (0.2, 0.3), (1.0, 0.4)),
            (1.0, 0.4, 0.2, 0.3),
        )

    def test_native_water_has_no_custom_water_coordinate_contract(self):
        decision = CAP.decide_coastal_mask(
            tri_type=2,
            imprint_masks_to_dds=False,
            mask_file_name=None,
            explicit_provider_extent=False,
        )
        with self.assertRaises(ValueError):
            CAP.water_texture_coordinates(decision, (0.2, 0.3), (1.0, 0.4))


if __name__ == "__main__":
    unittest.main()
