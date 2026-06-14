import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

QUALITY_CHECK_PATH = (
    Path(__file__).resolve().parents[1]
    / ".codex"
    / "skills"
    / "quality-check"
    / "scripts"
    / "quality_check.py"
)

spec = importlib.util.spec_from_file_location(
    "quality_check_targets", QUALITY_CHECK_PATH
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load quality check module from {QUALITY_CHECK_PATH}")
quality_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = quality_check
spec.loader.exec_module(quality_check)


class QualityCheckTargetTests(unittest.TestCase):
    def test_changed_complexity_targets_match_all_source_universe(self):
        with (
            mock.patch.object(
                quality_check,
                "changed_python_files",
                return_value=[
                    "src/O4_CLI_Run.py",
                    "Providers/O4_Custom_URL.py",
                    "Utils/run/configure.py",
                    ".agents/example.py",
                ],
            ),
            mock.patch.object(
                quality_check,
                "all_python_files",
                return_value=[
                    "src/O4_CLI_Run.py",
                    ".codex/skills/quality-check/scripts/quality_check.py",
                ],
            ),
            mock.patch.object(
                quality_check,
                "existing_paths",
                side_effect=lambda paths: paths,
            ),
        ):
            targets = quality_check.complexity_targets("changed")

        self.assertEqual(
            targets,
            [
                "src/O4_CLI_Run.py",
                ".codex/skills/quality-check/scripts/quality_check.py",
            ],
        )


if __name__ == "__main__":
    unittest.main()
