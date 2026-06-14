import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_DEM_Utils as DEM


class DEMGDALDependencyTests(unittest.TestCase):
    def test_gdal_is_required_without_has_gdal_switch(self):
        self.assertIsNotNone(DEM.gdal.VersionInfo())
        self.assertNotIn("has_gdal", vars(DEM))


if __name__ == "__main__":
    unittest.main()
