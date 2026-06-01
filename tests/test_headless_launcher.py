import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class HeadlessLauncherTests(unittest.TestCase):
    def test_validate_job_from_non_repo_cwd_does_not_create_generated_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            job_file = temp_path / "build_job.toml"
            job_file.write_text(
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(_path.ROOT_DIR / "Ortho4XP.py"),
                    "validate-job",
                    str(job_file),
                ],
                cwd=temp_dir,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Build job valid", result.stdout)
            for generated in (
                "Ortho4XP.cfg",
                "Tiles",
                "OSM_data",
                "Masks",
                "Orthophotos",
                "Elevation_data",
                "Geotiffs",
                "tmp",
                "yOrtho4XP_Overlays",
            ):
                self.assertFalse((temp_path / generated).exists(), generated)

    def test_validate_job_json_failure_returns_two(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = Path(temp_dir) / "build_job.toml"
            job_file.write_text(
                """
provider = "NOPE"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(_path.ROOT_DIR / "Ortho4XP.py"),
                    "validate-job",
                    str(job_file),
                    "--json",
                ],
                cwd=temp_dir,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn('"ok": false', result.stdout.lower())
            self.assertIn("provider", result.stdout)

    def test_build_job_dry_run_from_non_repo_cwd_creates_no_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            job_file = temp_path / "build_job.toml"
            job_file.write_text(
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(_path.ROOT_DIR / "Ortho4XP.py"),
                    "build-job",
                    str(job_file),
                    "--dry-run",
                ],
                cwd=temp_dir,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((temp_path / "Tiles").exists())
            self.assertFalse((temp_path / "Ortho4XP.cfg").exists())

    def test_legacy_help_mentions_headless_commands(self):
        result = subprocess.run(
            [sys.executable, str(_path.ROOT_DIR / "Ortho4XP.py"), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("validate-job", result.stdout)
        self.assertIn("build-job", result.stdout)


if __name__ == "__main__":
    unittest.main()
