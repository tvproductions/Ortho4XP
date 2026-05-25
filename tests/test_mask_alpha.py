import inspect
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Mask_Alpha as MASK_ALPHA
import O4_Mask_Utils as MASK


class ProgressiveLogAlphaRatioTests(unittest.TestCase):
    def test_progressive_log_alpha_ratio_has_exact_clamped_endpoints(self):
        self.assertEqual(MASK_ALPHA.progressive_log_alpha_ratio(-0.25), 0.0)
        self.assertEqual(MASK_ALPHA.progressive_log_alpha_ratio(0.0), 0.0)
        self.assertEqual(MASK_ALPHA.progressive_log_alpha_ratio(1.0), 1.0)
        self.assertEqual(MASK_ALPHA.progressive_log_alpha_ratio(1.25), 1.0)

    def test_progressive_log_alpha_ratio_is_monotonic_and_bounded(self):
        samples = [
            MASK_ALPHA.progressive_log_alpha_ratio(ratio)
            for ratio in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)
        ]

        self.assertEqual(samples, sorted(samples))
        for value in samples:
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_progressive_log_alpha_ratio_preserves_more_alpha_than_linear_near_shore(
        self,
    ):
        self.assertLess(MASK_ALPHA.progressive_log_alpha_ratio(0.25), 0.25)
        self.assertLess(MASK_ALPHA.progressive_log_alpha_ratio(0.5), 0.5)
        self.assertGreater(
            MASK_ALPHA.progressive_log_alpha_ratio(0.75),
            MASK_ALPHA.progressive_log_alpha_ratio(0.5),
        )

    def test_blur_mask_final_sea_fade_uses_progressive_log_alpha_ratio(self):
        source = inspect.getsource(MASK.blur_mask)

        self.assertIn(
            "progressive_log_alpha_ratio((i + 1) / stepsout)",
            source,
        )
        self.assertNotIn(
            'sea_level * (1 - transition_profile((i + 1) / stepsout, "linear"))',
            source,
        )

    def test_progressive_alpha_helper_does_not_consume_distance_masks(self):
        source = inspect.getsource(MASK_ALPHA.progressive_log_alpha_ratio)

        self.assertNotIn("distance_masks_too", source)
        self.assertNotIn("distance_mask", source)


if __name__ == "__main__":
    unittest.main()
