import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_skills_stack.py"


class SkillsStackTests(unittest.TestCase):
    def _components(self):
        return [
            {
                "name": "superpowers",
                "repository": "https://github.com/obra/superpowers",
                "revision": "a" * 40,
                "enabled_by_default": True,
            },
            {
                "name": "gz-skills",
                "repository": "https://github.com/tvproductions/gz-skills",
                "revision": "b" * 40,
                "enabled_by_default": True,
            },
            {
                "name": "superpowers-backplane",
                "repository": "https://github.com/tvproductions/superpowers-backplane",
                "revision": "c" * 40,
                "enabled_by_default": False,
            },
        ]

    def _catalog(self, components, revision_key):
        return {
            "name": "fixture-skills-first",
            "plugins": [
                {
                    "name": component["name"],
                    "source": {
                        "source": "url",
                        "url": f"{component['repository']}.git",
                        revision_key: component["revision"],
                    },
                }
                for component in components
            ],
        }

    def _project(self, root):
        components = self._components()
        lock = {
            "starter": {"revision": "d" * 40},
            "components": components,
            "catalog": {"name": "fixture-skills-first"},
        }
        catalogs = {
            ".agents/plugins/marketplace.json": "ref",
            ".claude-plugin/marketplace.json": "sha",
        }
        files = {".skills-first/bundle.lock.json": lock}
        for path, revision_key in catalogs.items():
            files[path] = self._catalog(components, revision_key)
        for path, value in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value), encoding="utf-8")
        config = root / ".codex/config.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            "\n".join(
                f'[plugins."{c["name"]}@fixture-skills-first"]\n'
                f"enabled = {str(c['enabled_by_default']).lower()}\n"
                for c in components
            ),
            encoding="utf-8",
        )

    def _check(self, root):
        return subprocess.run(  # noqa: S603
            [sys.executable, str(CHECKER), "--project", str(root)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_coherent_immutable_sources_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._project(root)
            result = self._check(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_moving_catalog_revision_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._project(root)
            catalog_path = root / ".agents/plugins/marketplace.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["plugins"][0]["source"]["ref"] = "main"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            result = self._check(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_catalog_repository_drift_fails(self):
        for path in (
            ".agents/plugins/marketplace.json",
            ".claude-plugin/marketplace.json",
        ):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._project(root)
                catalog_path = root / path
                catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                catalog["plugins"][0]["source"]["url"] = (
                    "https://example.invalid/wrong-repository.git"
                )
                catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
                result = self._check(root)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("FAIL:", result.stdout)

    def test_catalog_source_kind_drift_fails(self):
        for path in (
            ".agents/plugins/marketplace.json",
            ".claude-plugin/marketplace.json",
        ):
            for kind in ("path", "github", None):
                with (
                    self.subTest(path=path, kind=kind),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = Path(directory)
                    self._project(root)
                    catalog_path = root / path
                    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
                    catalog["plugins"][0]["source"]["source"] = kind
                    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
                    result = self._check(root)
                    self.assertEqual(
                        result.returncode, 1, result.stdout + result.stderr
                    )
                    self.assertIn("FAIL:", result.stdout)

    def test_malformed_catalog_repository_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._project(root)
            catalog_path = root / ".agents/plugins/marketplace.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["plugins"][0]["source"]["url"] = None
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            result = self._check(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("validation failed", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_duplicate_vendored_discovery_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._project(root)
            (root / ".agents/skills/superpowers").mkdir(parents=True)
            result = self._check(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_direct_and_renamed_upstream_skills_fail(self):
        for surface in (
            ".agents/skills",
            ".codex/skills",
            ".claude/skills",
            ".github/skills",
        ):
            for folder, identity in (
                ("using-superpowers", "using-superpowers"),
                ("local-copy", "using-superpowers"),
                ("local-copy", '"gzs-router"'),
                ("local-copy", "'managing-superpowers-backlog'"),
                ("alias/skills/writing-plans", "writing-plans"),
            ):
                with (
                    self.subTest(surface=surface, folder=folder, identity=identity),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = Path(directory)
                    self._project(root)
                    skill = root / surface / folder / "SKILL.md"
                    skill.parent.mkdir(parents=True)
                    skill.write_text(
                        f"---\nname: {identity}\ndescription: Copied skill\n---\n",
                        encoding="utf-8",
                    )
                    result = self._check(root)
                    self.assertEqual(
                        result.returncode, 1, result.stdout + result.stderr
                    )
                    self.assertIn("FAIL:", result.stdout)

    def test_project_skill_examples_do_not_count_as_upstream_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._project(root)
            skill = root / ".agents/skills/local-workflow/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: local-workflow\ndescription: Project workflow\n---\n"
                "Example:\n```yaml\nname: using-superpowers\n```\n",
                encoding="utf-8",
            )
            result = self._check(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_backplane_activation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._project(root)
            config = root / ".codex/config.toml"
            config.write_text(
                config.read_text(encoding="utf-8").replace(
                    "enabled = false", "enabled = true"
                ),
                encoding="utf-8",
            )
            result = self._check(root)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
