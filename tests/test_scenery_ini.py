import os
import tempfile
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Scenery_INI import SceneryEntry, SceneryINI


class TestSceneryINIParse(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)

    def _path(self, name="scenery_packs.ini"):
        return os.path.join(self._temp.name, name)

    def _write(self, content: str) -> str:
        p = self._path()
        with open(p, "w", newline="\n") as f:
            f.write(content)
        return p

    def test_parses_basic_entries(self):
        p = self._write(
            "I\n"
            "1000 Version\n"
            "\n"
            "SCENERY_PACK Custom Scenery/Global Airports/\n"
            "SCENERY_PACK Custom Scenery/Ortho4XP_Mesh_+43-079/\n"
        )
        ini = SceneryINI(p)
        ini.read()
        self.assertEqual(len(ini.entries()), 2)
        self.assertEqual(ini.entries()[0].path, "Custom Scenery/Global Airports/")
        self.assertFalse(ini.entries()[0].disabled)

    def test_parses_disabled_entries(self):
        p = self._write(
            "I\n1000 Version\n\nSCENERY_PACK_DISABLED Custom Scenery/Old/\n"
        )
        ini = SceneryINI(p)
        ini.read()
        self.assertTrue(ini.entries()[0].disabled)

    def test_handles_no_file(self):
        ini = SceneryINI(self._path("missing.ini"))
        ini.read()
        self.assertEqual(ini.entries(), [])

    def test_handles_empty_file(self):
        p = self._write("I\n1000 Version\n\n")
        ini = SceneryINI(p)
        ini.read()
        self.assertEqual(ini.entries(), [])

    def test_ignores_comments_and_blanks(self):
        p = self._write(
            "I\n1000 Version\n\n# comment\nSCENERY_PACK Custom Scenery/A/\n\nSCENERY_PACK Custom Scenery/B/\n"
        )
        ini = SceneryINI(p)
        ini.read()
        self.assertEqual(len(ini.entries()), 2)


class TestSceneryINIWrite(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)

    def _path(self):
        return os.path.join(self._temp.name, "scenery_packs.ini")

    def _read_ini(self, content: str) -> SceneryINI:
        p = self._path()
        with open(p, "w", newline="\n") as f:
            f.write(content)
        ini = SceneryINI(p)
        ini.read()
        return ini

    def _written_content(self, ini: SceneryINI) -> str:
        ini.write()
        with open(self._path()) as f:
            return f.read()

    def test_write_produces_valid_format(self):
        ini = self._read_ini("")
        ini.add_entry("Custom Scenery/Test/")
        content = self._written_content(ini)
        self.assertIn("I\n1000 Version\n\n", content)
        self.assertIn("SCENERY_PACK Custom Scenery/Test/\n", content)

    def test_add_entry_at_end(self):
        ini = self._read_ini("I\n1000 Version\n\nSCENERY_PACK Custom Scenery/A/\n")
        ini.add_entry("Custom Scenery/B/")
        self.assertEqual(len(ini.entries()), 2)
        self.assertEqual(ini.entries()[-1].path, "Custom Scenery/B/")

    def test_add_entry_at_position(self):
        ini = self._read_ini(
            "I\n1000 Version\n\n"
            "SCENERY_PACK Custom Scenery/A/\n"
            "SCENERY_PACK Custom Scenery/C/\n"
        )
        ini.add_entry("Custom Scenery/B/", position=1)
        self.assertEqual(ini.entries()[1].path, "Custom Scenery/B/")

    def test_remove_entry(self):
        ini = self._read_ini(
            "I\n1000 Version\n\n"
            "SCENERY_PACK Custom Scenery/A/\n"
            "SCENERY_PACK Custom Scenery/B/\n"
        )
        self.assertTrue(ini.remove_entry("Custom Scenery/A/"))
        self.assertEqual(len(ini.entries()), 1)
        self.assertEqual(ini.entries()[0].path, "Custom Scenery/B/")

    def test_remove_nonexistent_returns_false(self):
        ini = self._read_ini("I\n1000 Version\n\nSCENERY_PACK Custom Scenery/A/\n")
        self.assertFalse(ini.remove_entry("Custom Scenery/NotHere/"))

    def test_remove_entry_and_write(self):
        ini = self._read_ini(
            "I\n1000 Version\n\n"
            "SCENERY_PACK Custom Scenery/A/\n"
            "SCENERY_PACK Custom Scenery/B/\n"
        )
        ini.remove_entry("Custom Scenery/A/")
        content = self._written_content(ini)
        self.assertNotIn("Custom Scenery/A/", content)
        self.assertIn("Custom Scenery/B/", content)

    def test_find_by_path(self):
        ini = self._read_ini(
            "I\n1000 Version\n\n"
            "SCENERY_PACK Custom Scenery/A/\n"
            "SCENERY_PACK Custom Scenery/B/\n"
        )
        self.assertEqual(ini.find_by_path("Custom Scenery/A/"), 0)
        self.assertEqual(ini.find_by_path("Custom Scenery/B/"), 1)
        self.assertIsNone(ini.find_by_path("Custom Scenery/C/"))

    def test_disable_entry(self):
        ini = self._read_ini("I\n1000 Version\n\nSCENERY_PACK Custom Scenery/A/\n")
        idx = ini.find_by_path("Custom Scenery/A/")
        self.assertIsNotNone(idx)
        if idx is None:
            self.fail("expected Custom Scenery/A/ to exist")
        ini.entries()[idx].disabled = True
        content = self._written_content(ini)
        self.assertIn("SCENERY_PACK_DISABLED Custom Scenery/A/", content)
