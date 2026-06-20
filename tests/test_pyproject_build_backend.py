import tomllib
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT_DIR / "pyproject.toml"


class PyprojectBuildBackendTests(unittest.TestCase):
    def _pyproject(self):
        with PYPROJECT.open("rb") as pyproject_file:
            return tomllib.load(pyproject_file)

    def test_project_uses_uv_build_backend(self):
        pyproject = self._pyproject()

        self.assertEqual(pyproject["build-system"]["build-backend"], "uv_build")
        self.assertEqual(
            pyproject["build-system"]["requires"], ["uv_build>=0.11.21,<0.12"]
        )

    def test_project_package_mode_is_enabled_for_build_backend(self):
        pyproject = self._pyproject()

        self.assertIsNot(pyproject.get("tool", {}).get("uv", {}).get("package"), False)

    def test_uv_build_module_root_exists(self):
        pyproject = self._pyproject()
        uv_backend = pyproject["tool"]["uv"]["build-backend"]
        module_root = ROOT_DIR / uv_backend["module-root"]
        module_name = uv_backend["module-name"]

        self.assertTrue((module_root / module_name / "__init__.py").is_file())

    def test_uv_build_preserves_legacy_modules_without_unused_sources(self):
        pyproject = self._pyproject()
        uv_backend = pyproject["tool"]["uv"]["build-backend"]

        self.assertEqual(uv_backend["data"], {"purelib": "src"})
        self.assertIn("Ortho4XP.py", uv_backend["source-include"])
        self.assertIn("src/Unused/**", uv_backend["source-exclude"])


if __name__ == "__main__":
    unittest.main()
