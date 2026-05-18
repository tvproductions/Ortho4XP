import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class BathymetryWaterGateTests(unittest.TestCase):
    def test_all_land_tiles_do_not_require_bathymetry(self):
        from O4_DSF_Utils import mesh_requires_bathymetry

        self.assertFalse(mesh_requires_bathymetry([0, 0, 0]))

    def test_water_tiles_require_bathymetry(self):
        from O4_DSF_Utils import mesh_requires_bathymetry

        self.assertTrue(mesh_requires_bathymetry([0, 1, 0]))
        self.assertTrue(mesh_requires_bathymetry([0, 2, 0]))


if __name__ == "__main__":
    unittest.main()
