import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Models as MODELS
import O4_CLI_Run as RUN


class CliRunTests(unittest.TestCase):
    def _job_file(self, temp_dir):
        path = Path(temp_dir, "build_job.toml")
        path.write_text(
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
        return path

    def _plan(self):
        tile = MODELS.BuildTilePlan(
            lat=0,
            lon=0,
            provider="BI",
            zoom_level=16,
            output_dir="Tiles",
            custom_build_dir="Tiles/",
            steps=MODELS.DEFAULT_STEPS,
            override_tile_config=False,
        )
        return MODELS.BuildPlan((tile,))

    def test_validate_job_prints_human_summary_and_returns_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    RUN,
                    "_provider_inventory",
                    return_value=({"BI"}, set(), {"BI": {}}),
                ),
                mock.patch.object(RUN.JOBS, "load_build_plan", return_value=self._plan()),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["validate-job", str(job_file)])

        self.assertEqual(code, 0)
        self.assertIn("Build job valid: 1 tile", stdout.getvalue())

    def test_validate_job_json_prints_json_and_returns_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    RUN,
                    "_provider_inventory",
                    return_value=({"BI"}, set(), {"BI": {}}),
                ),
                mock.patch.object(RUN.JOBS, "load_build_plan", return_value=self._plan()),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["validate-job", str(job_file), "--json"])

        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])

    def test_validation_error_returns_two(self):
        error = RUN.JOBS.ValidationError("provider", "unknown provider", "NOPE")
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    RUN, "_provider_inventory", return_value=(set(), set(), {})
                ),
                mock.patch.object(
                    RUN.JOBS,
                    "load_build_plan",
                    side_effect=RUN.JOBS.JobValidationError([error]),
                ),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["validate-job", str(job_file)])

        self.assertEqual(code, 2)
        self.assertIn("provider", stdout.getvalue())

    def test_build_job_dry_run_does_not_import_runtime_modules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    RUN,
                    "_provider_inventory",
                    return_value=({"BI"}, set(), {"BI": {}}),
                ),
                mock.patch.object(RUN.JOBS, "load_build_plan", return_value=self._plan()),
                mock.patch.object(
                    RUN, "_run_build", side_effect=AssertionError("should not build")
                ),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["build-job", str(job_file), "--dry-run"])

        self.assertEqual(code, 0)
        self.assertIn("Build job valid: 1 tile", stdout.getvalue())

    def test_build_job_maps_failed_batch_to_exit_one(self):
        failed = MODELS.BuildBatchResult(
            ok=False,
            tiles=(MODELS.BuildTileResult(0, 0, False, "mesh", "mesh failed"),),
            message="mesh failed",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    RUN,
                    "_provider_inventory",
                    return_value=({"BI"}, set(), {"BI": {}}),
                ),
                mock.patch.object(RUN.JOBS, "load_build_plan", return_value=self._plan()),
                mock.patch.object(RUN, "_run_build", return_value=failed),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["build-job", str(job_file)])

        self.assertEqual(code, 1)
        self.assertIn("mesh failed", stdout.getvalue())

    def test_build_job_maps_success_to_exit_zero(self):
        result = MODELS.BuildBatchResult(
            ok=True,
            tiles=(MODELS.BuildTileResult(0, 0, True, "all"),),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    RUN,
                    "_provider_inventory",
                    return_value=({"BI"}, set(), {"BI": {}}),
                ),
                mock.patch.object(RUN.JOBS, "load_build_plan", return_value=self._plan()),
                mock.patch.object(RUN, "_run_build", return_value=result),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["build-job", str(job_file)])

        self.assertEqual(code, 0)
        self.assertIn("Build job completed: 1 tile", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
