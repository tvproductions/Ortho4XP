import json
import os
import tempfile
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Scenery_Manager import SceneryManager


class TestPackageDetection(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.cs_dir = os.path.join(self._temp.name, "Custom Scenery")
        os.makedirs(self.cs_dir)

    def _make_package(self, name: str, with_json: bool = True, json_data: dict | None = None) -> str:
        pkg_dir = os.path.join(self.cs_dir, name)
        os.makedirs(os.path.join(pkg_dir, "Earth nav data"))
        if with_json:
            data = json_data or {
                "name": name,
                "type": "mesh",
                "generation": {"tool": "Ortho4XP", "tool_version": "1.0.0", "timestamp": "2026-06-13T00:00:00Z"},
                "compatibility": {"min_xplane_version": "12.0.0"},
            }
            with open(os.path.join(pkg_dir, "package.json"), "w") as f:
                json.dump(data, f)
        return pkg_dir

    def _make_ini(self, entries: list[str]) -> str:
        ini_path = os.path.join(self._temp.name, "scenery_packs.ini")
        with open(ini_path, "w", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            for e in entries:
                f.write(f"SCENERY_PACK Custom Scenery/{e}/\n")
        return ini_path

    def test_detects_by_package_json(self):
        self._make_package("Ortho4XP_Mesh_+43-079")
        ini_path = self._make_ini(["Ortho4XP_Mesh_+43-079"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_detects_by_current_naming(self):
        self._make_package("Ortho4XP_Mesh_+43-079", with_json=False)
        ini_path = self._make_ini(["Ortho4XP_Mesh_+43-079"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_detects_legacy_zortho4xp(self):
        self._make_package("zOrtho4XP_+43-079", with_json=False)
        ini_path = self._make_ini(["zOrtho4XP_+43-079"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_detects_legacy_yortho4xp(self):
        self._make_package("yOrtho4XP_Overlays", with_json=False)
        ini_path = self._make_ini(["yOrtho4XP_Overlays"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_detects_overlay_package(self):
        self._make_package("Ortho4XP_Overlays")
        ini_path = self._make_ini(["Ortho4XP_Overlays"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_ignores_non_ortho4xp(self):
        self._make_package("Global Airports", with_json=False)
        ini_path = self._make_ini(["Global Airports"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 0)

    def test_ignores_other_providers(self):
        self._make_package("simHeaven_X-World_Europe-1-vfr", with_json=False)
        ini_path = self._make_ini(["simHeaven_X-World_Europe-1-vfr"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 0)
