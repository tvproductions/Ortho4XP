import importlib.util
import sys
import unittest
from pathlib import Path


QUALITY_CHECK_PATH = (
    Path(__file__).resolve().parents[1]
    / ".codex"
    / "skills"
    / "quality-check"
    / "scripts"
    / "quality_check.py"
)


spec = importlib.util.spec_from_file_location("quality_check", QUALITY_CHECK_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load quality check module from {QUALITY_CHECK_PATH}")
quality_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = quality_check
spec.loader.exec_module(quality_check)


class QualityCheckTests(unittest.TestCase):
    def test_severity_for_high_is_worse_metric(self):
        config = {"polarity": "high", "advise": 4.0, "warn": 7.0, "block": 11.0}

        self.assertIsNone(quality_check.severity_for(3.0, config))
        self.assertEqual(quality_check.severity_for(4.0, config), "advise")
        self.assertEqual(quality_check.severity_for(7.0, config), "warn")
        self.assertEqual(quality_check.severity_for(11.0, config), "block")

    def test_severity_for_low_is_worse_metric(self):
        config = {"polarity": "low", "advise": 85.0, "warn": 70.0, "block": 50.0}

        self.assertIsNone(quality_check.severity_for(90.0, config))
        self.assertEqual(quality_check.severity_for(85.0, config), "advise")
        self.assertEqual(quality_check.severity_for(70.0, config), "warn")
        self.assertEqual(quality_check.severity_for(50.0, config), "block")

    def test_baseline_comparison_blocks_new_block_finding(self):
        finding = quality_check.Finding(
            metric="radon_cc",
            path="src/example.py",
            name="build",
            value=12.0,
            severity="block",
        )
        thresholds = {"radon_cc": {"polarity": "high"}}

        regressions = quality_check.compare_to_baseline([finding], {}, thresholds)

        self.assertEqual(len(regressions), 1)
        self.assertIn("new block", regressions[0].reason)

    def test_baseline_comparison_blocks_worse_existing_finding(self):
        finding = quality_check.Finding(
            metric="radon_mi",
            path="src/example.py",
            name="<module>",
            value=45.0,
            severity="block",
        )
        baseline = {finding.key: {"value": 50.0}}
        thresholds = {"radon_mi": {"polarity": "low"}}

        regressions = quality_check.compare_to_baseline([finding], baseline, thresholds)

        self.assertEqual(len(regressions), 1)
        self.assertEqual(regressions[0].baseline_value, 50.0)

    def test_baseline_comparison_allows_existing_equal_finding(self):
        finding = quality_check.Finding(
            metric="lizard_ccn",
            path="src/example.py",
            name="build",
            value=11.0,
            severity="block",
        )
        baseline = {finding.key: {"value": 11.0}}
        thresholds = {"lizard_ccn": {"polarity": "high"}}

        regressions = quality_check.compare_to_baseline([finding], baseline, thresholds)

        self.assertEqual(regressions, [])


if __name__ == "__main__":
    unittest.main()
