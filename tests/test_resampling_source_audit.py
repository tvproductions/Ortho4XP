import unittest
from pathlib import Path


class ResamplingSourceAuditTests(unittest.TestCase):
    def test_runtime_sources_do_not_hardcode_pillow_or_gdal_resampling(self):
        violations = []
        for path in _audited_runtime_sources():
            source = path.read_text()
            violations.extend(_source_resampling_violations(path, source))

        self.assertEqual(violations, [])

    def test_numpy_resize_remains_allowed_for_array_capacity_management(self):
        bathymetry = Path("src/O4_Bathymetry.py").read_text()
        recut_water = Path("src/O4_Recut_Water.py").read_text()

        self.assertIn("numpy.resize", bathymetry)
        self.assertIn("numpy.resize", recut_water)


def _audited_runtime_sources():
    policy_path = Path("src/O4_Resampling_Policy.py")
    return (path for path in Path("src").glob("O4_*.py") if path != policy_path)


def _source_resampling_violations(path, source):
    forbidden_tokens = (
        "Image.Resampling.BICUBIC",
        "Image.Resampling.BILINEAR",
        "Image.Resampling.NEAREST",
        "Image.Resampling.LANCZOS",
        'resampleAlg="',
    )
    return [f"{path}:{token}" for token in forbidden_tokens if token in source]


if __name__ == "__main__":
    unittest.main()
