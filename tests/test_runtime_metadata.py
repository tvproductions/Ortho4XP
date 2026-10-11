"""Keep the supported interpreter and native dependency surfaces coherent."""

import tomllib
import unittest
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import parse_wheel_filename
from packaging.version import Version

ROOT_DIR = Path(__file__).resolve().parents[1]


class RuntimeMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text())

    def test_supported_runtime_is_python_314(self):
        selected = Version((ROOT_DIR / ".python-version").read_text().strip())
        self.assertEqual(selected.release[:2], (3, 14))
        supported = SpecifierSet(self.metadata["project"]["requires-python"])
        self.assertIn(selected, supported)
        self.assertNotIn(Version("3.13.99"), supported)
        self.assertNotIn(Version("3.15.0"), supported)
        self.assertEqual(self.metadata["tool"]["ruff"]["target-version"], "py314")
        self.assertEqual(
            self.metadata["tool"]["ty"]["environment"]["python-version"], "3.14"
        )

    def test_windows_sources_match_supported_interpreter(self):
        for name in ("gdal", "scikit-fmm"):
            source = self.metadata["tool"]["uv"]["sources"][name][0]
            path = ROOT_DIR / source["path"]
            with self.subTest(dependency=name):
                self.assertTrue(path.is_file())
                self._assert_windows_tags(path)

    def _assert_windows_tags(self, path):
        _, _, _, tags = parse_wheel_filename(path.name)
        self.assertTrue(tags)
        self.assertTrue(all(tag.interpreter == "cp314" for tag in tags))
        self.assertTrue(all(tag.abi == "cp314" for tag in tags))
        self.assertTrue(all(tag.platform == "win_amd64" for tag in tags))

    def test_gdal_bindings_use_one_supported_native_release(self):
        gdal = self._gdal_bindings()
        self.assertTrue(gdal)
        for system in ("Linux", "Darwin", "Windows"):
            applicable = self._bindings_for_system(gdal, system)
            with self.subTest(system=system):
                self.assertEqual(len(applicable), 1)
                self.assertIn(Version("3.13.3"), applicable[0].specifier)
                self.assertNotIn(Version("3.9.0"), applicable[0].specifier)

    def _gdal_bindings(self):
        requirements = map(Requirement, self.metadata["project"]["dependencies"])
        return [item for item in requirements if item.name.lower() == "gdal"]

    def _bindings_for_system(self, bindings, system):
        return [item for item in bindings if self._matches_system(item, system)]

    def _matches_system(self, requirement, system):
        if requirement.marker is None:
            return True
        return requirement.marker.evaluate({"platform_system": system})

    def test_ci_and_mac_install_use_selected_runtime(self):
        selected = (ROOT_DIR / ".python-version").read_text().strip()
        workflow = (ROOT_DIR / ".github/workflows/ci.yml").read_text()
        python_selections = [
            line.strip().split(":", 1)[1].strip().strip('"')
            for line in workflow.splitlines()
            if "python-version:" in line
        ]
        self.assertEqual(python_selections, [selected] * 3)
        installer = (ROOT_DIR / "install_mac.sh").read_text()
        self.assertIn("python@3.14 python-tk@3.14", installer)
        self.assertNotIn("python@3.13", installer)

    def test_linux_native_bootstrap_matches_python_binding_pin(self):
        bootstrap = ROOT_DIR / "scripts/install_linux_gdal.sh"
        self.assertTrue(bootstrap.is_file())
        script = bootstrap.read_text()
        self.assertIn("GDAL_VERSION=3.13.3", script)
        self.assertIn("sha256sum --check", script)
        self.assertRegex(script, r'gdal-config"? --version')


if __name__ == "__main__":
    unittest.main()
