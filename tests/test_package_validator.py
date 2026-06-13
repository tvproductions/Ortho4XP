import json
import os
import tempfile
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class PackageValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_package_json(self, data):
        path = os.path.join(self.tmpdir, "package.json")
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_valid_mesh_package_passes_validation(self):
        from O4_Package_Validator import validate_package
        data = {
            "name": "Ortho4XP_Mesh_+43-079",
            "version": "1.0.0",
            "author": "Ortho4XP",
            "description": "Test",
            "type": "mesh",
            "compatibility": {"min_xplane_version": "12.0.0"},
            "generation": {
                "tool": "Ortho4XP",
                "tool_version": "1.0.0",
                "timestamp": "2026-06-13T12:00:00Z",
            },
            "tile": {"lat": 43, "lon": -79, "lat_rounded": 40, "lon_rounded": -80},
        }
        self._write_package_json(data)
        result = validate_package(self.tmpdir)
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)

    def test_missing_required_field_fails_validation(self):
        from O4_Package_Validator import validate_package
        data = {
            "name": "Ortho4XP_Mesh_+43-079",
            "type": "mesh",
        }
        self._write_package_json(data)
        result = validate_package(self.tmpdir)
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)

    def test_invalid_type_fails_validation(self):
        from O4_Package_Validator import validate_package
        data = {
            "name": "Test",
            "version": "1.0.0",
            "author": "Test",
            "description": "Test",
            "type": "invalid_type",
            "compatibility": {"min_xplane_version": "12.0.0"},
            "generation": {
                "tool": "Test",
                "tool_version": "1.0.0",
                "timestamp": "2026-06-13T12:00:00Z",
            },
        }
        self._write_package_json(data)
        result = validate_package(self.tmpdir)
        self.assertFalse(result["valid"])

    def test_missing_package_json_file_fails(self):
        from O4_Package_Validator import validate_package
        result = validate_package(self.tmpdir)
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
