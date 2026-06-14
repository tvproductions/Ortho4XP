import json
import os
import tempfile
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Scenery_Manager import SceneryManager, SceneryError


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


class TestSymlinkOperations(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.xplane_root = os.path.join(self._temp.name, "X-Plane")
        self.cs_dir = os.path.join(self.xplane_root, "Custom Scenery")
        os.makedirs(self.cs_dir)
        self.build_dir = os.path.join(self._temp.name, "Tiles")
        os.makedirs(self.build_dir)

    def _make_tile_dir(self, lat, lon):
        tile_name = "Ortho4XP_Mesh_{:+03d}{:+04d}".format(lat, lon)
        path = os.path.join(self.build_dir, tile_name)
        os.makedirs(os.path.join(path, "Earth nav data"))
        with open(os.path.join(path, "package.json"), "w") as f:
            json.dump({"name": tile_name, "type": "mesh", "generation": {"tool": "Ortho4XP"}}, f)
        return path

    def _ini_path(self):
        ini_dir = os.path.join(self.xplane_root, "Output", "preferences")
        os.makedirs(ini_dir, exist_ok=True)
        return os.path.join(ini_dir, "scenery_packs.ini")

    def _make_mgr(self, cs_dir=None):
        return SceneryManager(
            custom_scenery_dir=cs_dir or self.cs_dir,
            ini_path=self._ini_path(),
        )

    def test_add_tile_creates_symlink_ini_entry(self):
        self._make_tile_dir(43, -79)
        mgr = self._make_mgr()
        mgr.add_tile(lat=43, lon=-79, build_dir=self.build_dir)
        link_path = os.path.join(self.cs_dir, "Ortho4XP_Mesh_+43-079")
        self.assertTrue(os.path.exists(link_path))
        mgr.refresh()
        entries = mgr.ortho4xp_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("Ortho4XP_Mesh_+43-079", entries[0].path)

    def test_remove_tile_removes_symlink_ini_entry(self):
        self._make_tile_dir(43, -79)
        mgr = self._make_mgr()
        mgr.add_tile(lat=43, lon=-79, build_dir=self.build_dir)
        result = mgr.remove_tile(lat=43, lon=-79)
        self.assertTrue(result)
        link_path = os.path.join(self.cs_dir, "Ortho4XP_Mesh_+43-079")
        self.assertFalse(os.path.exists(link_path))
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 0)

    def test_add_tile_no_symlink_when_same_dir(self):
        self._make_tile_dir(43, -79)
        mgr = self._make_mgr(cs_dir=self.build_dir)
        mgr.add_tile(lat=43, lon=-79, build_dir=self.build_dir)
        tile_path = os.path.join(self.build_dir, "Ortho4XP_Mesh_+43-079")
        self.assertTrue(os.path.exists(tile_path))
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_add_tile_raises_on_missing_dir(self):
        mgr = self._make_mgr()
        with self.assertRaises(SceneryError):
            mgr.add_tile(lat=99, lon=99, build_dir=self.build_dir)

    def test_add_overlay_creates_symlink_ini_entry(self):
        overlay_dir = os.path.join(self._temp.name, "Ortho4XP_Overlays")
        os.makedirs(os.path.join(overlay_dir, "Earth nav data"))
        mgr = self._make_mgr()
        mgr.add_overlay(overlay_dir=overlay_dir)
        link_path = os.path.join(self.cs_dir, "Ortho4XP_Overlays")
        self.assertTrue(os.path.exists(link_path))
        mgr.refresh()
        entries = mgr.ortho4xp_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("Ortho4XP_Overlays", entries[0].path)

    def test_remove_overlay_removes_symlink_ini_entry(self):
        overlay_dir = os.path.join(self._temp.name, "Ortho4XP_Overlays")
        os.makedirs(os.path.join(overlay_dir, "Earth nav data"))
        mgr = self._make_mgr()
        mgr.add_overlay(overlay_dir=overlay_dir)
        result = mgr.remove_overlay()
        self.assertTrue(result)
        link_path = os.path.join(self.cs_dir, "Ortho4XP_Overlays")
        self.assertFalse(os.path.exists(link_path))

    def test_remove_nonexistent_returns_false(self):
        mgr = self._make_mgr()
        self.assertFalse(mgr.remove_tile(lat=99, lon=99))
        self.assertFalse(mgr.remove_overlay())

    def test_add_tile_does_not_duplicate_entries(self):
        self._make_tile_dir(43, -79)
        mgr = self._make_mgr()
        mgr.add_tile(lat=43, lon=-79, build_dir=self.build_dir)
        mgr.add_tile(lat=43, lon=-79, build_dir=self.build_dir)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)


class TestReorder(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.cs_dir = os.path.join(self._temp.name, "Custom Scenery")
        os.makedirs(self.cs_dir)

    def _make_ini(self, entries: list[str]) -> str:
        ini_path = os.path.join(self._temp.name, "scenery_packs.ini")
        with open(ini_path, "w", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            for e in entries:
                f.write(f"SCENERY_PACK Custom Scenery/{e}/\n")
        return ini_path

    def _content(self, ini_path: str) -> list[str]:
        with open(ini_path) as f:
            return [line.strip() for line in f if "SCENERY_PACK" in line]

    def test_reorder_moves_overlays_above_meshes(self):
        ini_path = self._make_ini([
            "Ortho4XP_Mesh_+43-079",
            "Ortho4XP_Overlays",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        lines = self._content(ini_path)
        overlay_idx = next(i for i, l in enumerate(lines) if "Overlays" in l)
        mesh_idx = next(i for i, l in enumerate(lines) if "Mesh" in l)
        self.assertLess(overlay_idx, mesh_idx)

    def test_reorder_preserves_non_ortho4xp(self):
        ini_path = self._make_ini([
            "Global Airports",
            "Ortho4XP_Mesh_+44-080",
            "Ortho4XP_Mesh_+43-079",
            "simHeaven_X-World",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        lines = self._content(ini_path)
        self.assertIn("Global Airports", lines[0])
        self.assertIn("simHeaven_X-World", lines[-1])

    def test_reorder_sorts_mesh_entries(self):
        ini_path = self._make_ini([
            "Ortho4XP_Mesh_+44-080",
            "Ortho4XP_Mesh_+43-079",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        lines = self._content(ini_path)
        self.assertIn("+43-079", lines[0])
        self.assertIn("+44-080", lines[1])

    def test_reorder_no_ortho4xp_does_nothing(self):
        ini_path = self._make_ini([
            "Global Airports",
            "simHeaven_X-World",
        ])
        original = list(self._content(ini_path))
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        self.assertEqual(self._content(ini_path), original)

    def test_reorder_preserves_interleaved_non_ortho4xp(self):
        ini_path = self._make_ini([
            "Global Airports",
            "Ortho4XP_Mesh_+44-080",
            "simHeaven_X-World",
            "Ortho4XP_Mesh_+43-079",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        lines = self._content(ini_path)
        self.assertIn("Global Airports", lines[0])
        self.assertIn("simHeaven_X-World", lines[-1])
        self.assertEqual(len(lines), 4)

    def test_reorder_preserves_disabled_entry(self):
        ini_path = os.path.join(self._temp.name, "scenery_packs.ini")
        with open(ini_path, "w", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            f.write("SCENERY_PACK Custom Scenery/Global Airports/\n")
            f.write("SCENERY_PACK_DISABLED Custom Scenery/Ortho4XP_Mesh_+43-079/\n")
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        with open(ini_path) as f:
            content = f.read()
        self.assertIn("SCENERY_PACK_DISABLED", content)
        self.assertIn("Ortho4XP_Mesh_+43-079", content)

    def test_reorder_multiple_overlays_and_meshes(self):
        ini_path = self._make_ini([
            "Ortho4XP_Mesh_+45-081",
            "Ortho4XP_Overlay_+44-080",
            "Ortho4XP_Overlays",
            "Ortho4XP_Mesh_+43-079",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        lines = self._content(ini_path)
        overlays = [l for l in lines if "Overlay" in l or "Overlays" in l]
        meshes = [l for l in lines if "Mesh" in l]
        self.assertEqual(len(overlays), 2)
        self.assertEqual(len(meshes), 2)
        overlay_indices = [i for i, l in enumerate(lines) if "Overlay" in l or "Overlays" in l]
        mesh_indices = [i for i, l in enumerate(lines) if "Mesh" in l]
        self.assertLess(max(overlay_indices), min(mesh_indices))


class TestValidate(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.cs_dir = os.path.join(self._temp.name, "Custom Scenery")
        os.makedirs(self.cs_dir)

    def _make_package_dir(self, name):
        p = os.path.join(self.cs_dir, name)
        os.makedirs(os.path.join(p, "Earth nav data"))
        return p

    def _make_ini(self, entries: list[str]) -> str:
        ini_path = os.path.join(self._temp.name, "scenery_packs.ini")
        with open(ini_path, "w", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            for e in entries:
                f.write(f"SCENERY_PACK Custom Scenery/{e}/\n")
        return ini_path

    def test_validate_missing_directory(self):
        ini_path = self._make_ini(["Ortho4XP_Mesh_+43-079"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        issues = mgr.validate()
        missing = [i for i in issues if "not found" in i.message.lower()]
        self.assertTrue(len(missing) >= 1)

    def test_validate_wrong_order_is_warning(self):
        self._make_package_dir("Ortho4XP_Overlays")
        self._make_package_dir("Ortho4XP_Mesh_+43-079")
        ini_path = self._make_ini([
            "Ortho4XP_Mesh_+43-079",
            "Ortho4XP_Overlays",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        issues = mgr.validate()
        order_issues = [i for i in issues if "order" in i.message.lower()]
        self.assertTrue(len(order_issues) >= 1)

    def test_validate_disabled_entry_is_warning(self):
        self._make_package_dir("Ortho4XP_Mesh_+43-079")
        ini_path = os.path.join(self._temp.name, "scenery_packs.ini")
        with open(ini_path, "w", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            f.write("SCENERY_PACK_DISABLED Custom Scenery/Ortho4XP_Mesh_+43-079/\n")
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        issues = mgr.validate()
        disabled = [i for i in issues if "disabled" in i.message.lower()]
        self.assertTrue(len(disabled) >= 1)

    def test_validate_clean_returns_no_issues(self):
        self._make_package_dir("Ortho4XP_Overlays")
        self._make_package_dir("Ortho4XP_Mesh_+43-079")
        ini_path = self._make_ini([
            "Ortho4XP_Overlays",
            "Ortho4XP_Mesh_+43-079",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        issues = mgr.validate()
        self.assertEqual(len(issues), 0)

    def test_validate_duplicate_entries(self):
        self._make_package_dir("Ortho4XP_Mesh_+43-079")
        ini_path = self._make_ini([
            "Ortho4XP_Mesh_+43-079",
            "Ortho4XP_Mesh_+43-079",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        issues = mgr.validate()
        dup = [i for i in issues if "duplicate" in i.message.lower()]
        self.assertTrue(len(dup) >= 1)

    def test_validate_empty_cs_dir(self):
        mgr = SceneryManager(custom_scenery_dir="", ini_path=self._make_ini([]))
        mgr.refresh()
        issues = mgr.validate()
        cs_issues = [i for i in issues if "custom_scenery_dir" in i.message.lower()]
        self.assertTrue(len(cs_issues) >= 1)
