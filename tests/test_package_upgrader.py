import os
import tempfile
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class PackageUpgraderTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_legacy_package(self, name):
        pkg_dir = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.join(pkg_dir, "Earth nav data", "+40-080"))
        return pkg_dir

    def test_upgrade_renames_legacy_z_prefix_to_new_naming(self):
        from O4_Package_Upgrader import upgrade_package

        old_dir = self._create_legacy_package("zOrtho4XP_+43-079")
        result = upgrade_package(old_dir, dry_run=True)
        self.assertIn("Ortho4XP_Mesh", result["new_name"])

    def test_upgrade_generates_package_json(self):
        from O4_Package_Upgrader import upgrade_package

        old_dir = self._create_legacy_package("zOrtho4XP_+43-079")
        result = upgrade_package(old_dir, dry_run=False)
        self.assertTrue(result["metadata_written"])
        self.assertTrue(os.path.isfile(os.path.join(result["new_dir"], "package.json")))

    def test_upgrade_skips_none_z_named_directories(self):
        from O4_Package_Upgrader import upgrade_package

        result = upgrade_package("/nonexistent/non-z-folder")
        self.assertFalse(result["upgraded"])


if __name__ == "__main__":
    unittest.main()
