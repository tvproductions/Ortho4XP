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
