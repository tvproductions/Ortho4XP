import json
import os
import tempfile
import unittest
from types import SimpleNamespace

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class PackageMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_write_mesh_package_metadata_creates_json(self):
        from O4_Package_Metadata import write_package_metadata

        tile = SimpleNamespace(
            lat=43,
            lon=-79,
            zoomlevel=17,
            provider_code="BI",
            build_dir=self.tmpdir,
        )
        write_package_metadata(self.tmpdir, tile, "mesh")
        meta_file = os.path.join(self.tmpdir, "package.json")
        self.assertTrue(os.path.isfile(meta_file))

    def test_mesh_metadata_has_required_fields(self):
        from O4_Package_Metadata import write_package_metadata

        tile = SimpleNamespace(
            lat=43,
            lon=-79,
            zoomlevel=17,
            provider_code="BI",
            build_dir=self.tmpdir,
        )
        write_package_metadata(self.tmpdir, tile, "mesh")
        with open(os.path.join(self.tmpdir, "package.json")) as f:
            meta = json.load(f)
        self.assertEqual(meta["type"], "mesh")
        self.assertIn("name", meta)
        self.assertIn("version", meta)
        self.assertIn("tile", meta)
        self.assertEqual(meta["compatibility"]["min_xplane_version"], "12.0.0")

    def test_overlay_metadata_has_type_overlay(self):
        from O4_Package_Metadata import write_package_metadata

        tile = SimpleNamespace(
            lat=43,
            lon=-79,
            zoomlevel=17,
            provider_code="BI",
            build_dir=self.tmpdir,
        )
        write_package_metadata(self.tmpdir, tile, "overlay")
        with open(os.path.join(self.tmpdir, "package.json")) as f:
            meta = json.load(f)
        self.assertEqual(meta["type"], "overlay")

    def test_metadata_includes_generation_timestamp(self):
        from O4_Package_Metadata import write_package_metadata

        tile = SimpleNamespace(
            lat=43,
            lon=-79,
            zoomlevel=17,
            provider_code="BI",
            build_dir=self.tmpdir,
        )
        write_package_metadata(self.tmpdir, tile, "mesh")
        with open(os.path.join(self.tmpdir, "package.json")) as f:
            meta = json.load(f)
        self.assertIn("generation", meta)
        self.assertIn("timestamp", meta["generation"])
        self.assertIn("tool", meta["generation"])
        self.assertEqual(meta["generation"]["tool"], "Ortho4XP")


if __name__ == "__main__":
    unittest.main()
