import json
import tempfile
import unittest
from pathlib import Path

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Models as MODELS
import O4_CLI_Jobs as JOBS


PROVIDERS = {"BI", "Arc"}
COMBINED = {"EUR"}
PROVIDER_METADATA = {
    "BI": {"max_zl": 19},
    "Arc": {},
}


def _job_path(directory, text):
    path = Path(directory, "build_job.toml")
    path.write_text(text, encoding="utf-8")
    return path


class CliJobsValidationTests(unittest.TestCase):
    def test_explicit_tile_job_parses_to_build_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 43
lon = -79
""",
            )

            plan = JOBS.load_build_plan(
                path,
                provider_keys=PROVIDERS,
                combined_provider_keys=COMBINED,
                provider_metadata=PROVIDER_METADATA,
            )

        self.assertEqual(len(plan.tiles), 1)
        tile = plan.tiles[0]
        self.assertIsInstance(tile, MODELS.BuildTilePlan)
        self.assertEqual((tile.lat, tile.lon), (43, -79))
        self.assertEqual(tile.provider, "BI")
        self.assertEqual(tile.zoom_level, 16)
        self.assertEqual(tile.steps, MODELS.DEFAULT_STEPS)
        self.assertEqual(Path(tile.output_dir), Path(temp_dir, "Tiles"))
        self.assertTrue(tile.custom_build_dir.endswith(("/", "\\")))

    def test_bounds_expand_inclusive_ranges(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[bounds]
lat_min = 1
lat_max = 2
lon_min = -1
lon_max = 0
""",
            )

            plan = JOBS.load_build_plan(
                path,
                provider_keys=PROVIDERS,
                combined_provider_keys=COMBINED,
                provider_metadata=PROVIDER_METADATA,
            )

        self.assertEqual(
            [(tile.lat, tile.lon) for tile in plan.tiles],
            [(1, -1), (1, 0), (2, -1), (2, 0)],
        )

    def test_tiles_and_bounds_are_deduplicated_and_sorted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 2
lon = 0

[[tiles]]
lat = 1
lon = -1

[bounds]
lat_min = 1
lat_max = 1
lon_min = -1
lon_max = 0
""",
            )

            plan = JOBS.load_build_plan(
                path,
                provider_keys=PROVIDERS,
                combined_provider_keys=COMBINED,
                provider_metadata=PROVIDER_METADATA,
            )

        self.assertEqual(
            [(tile.lat, tile.lon) for tile in plan.tiles],
            [(1, -1), (1, 0), (2, 0)],
        )

    def test_combined_provider_key_is_valid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "EUR"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
            )

            plan = JOBS.load_build_plan(
                path,
                provider_keys=PROVIDERS,
                combined_provider_keys=COMBINED,
                provider_metadata=PROVIDER_METADATA,
            )

        self.assertEqual(plan.tiles[0].provider, "EUR")

    def test_rejects_reversed_bounds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[bounds]
lat_min = 2
lat_max = 1
lon_min = 0
lon_max = 0
""",
            )

            with self.assertRaises(JOBS.JobValidationError) as caught:
                JOBS.load_build_plan(
                    path,
                    provider_keys=PROVIDERS,
                    combined_provider_keys=COMBINED,
                    provider_metadata=PROVIDER_METADATA,
                )

        self.assertEqual(caught.exception.errors[0].field, "bounds.lat_min")

    def test_rejects_lat_lon_outside_tile_ranges(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 90
lon = 180
""",
            )

            with self.assertRaises(JOBS.JobValidationError) as caught:
                JOBS.load_build_plan(
                    path,
                    provider_keys=PROVIDERS,
                    combined_provider_keys=COMBINED,
                    provider_metadata=PROVIDER_METADATA,
                )

        self.assertEqual(
            [error.field for error in caught.exception.errors],
            ["tiles[0].lat", "tiles[0].lon"],
        )

    def test_rejects_unknown_step_and_per_tile_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"
steps = ["vector", "bogus"]

[[tiles]]
lat = 0
lon = 0
provider = "Arc"
""",
            )

            with self.assertRaises(JOBS.JobValidationError) as caught:
                JOBS.load_build_plan(
                    path,
                    provider_keys=PROVIDERS,
                    combined_provider_keys=COMBINED,
                    provider_metadata=PROVIDER_METADATA,
                )

        self.assertEqual(
            [error.field for error in caught.exception.errors],
            ["steps[1]", "tiles[0].provider"],
        )

    def test_rejects_zoom_above_provider_max_zl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 20
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
            )

            with self.assertRaises(JOBS.JobValidationError) as caught:
                JOBS.load_build_plan(
                    path,
                    provider_keys=PROVIDERS,
                    combined_provider_keys=COMBINED,
                    provider_metadata=PROVIDER_METADATA,
                )

        self.assertEqual(caught.exception.errors[0].field, "zoom_level")

    def test_json_success_and_failure_payloads_are_stable(self):
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
        success = json.loads(JOBS.validation_success_json(MODELS.BuildPlan((tile,))))

        self.assertEqual(success["ok"], True)
        self.assertEqual(success["tile_count"], 1)
        self.assertEqual(success["provider"], "BI")
        self.assertEqual(success["tiles"], [{"lat": 0, "lon": 0}])

        failure = json.loads(
            JOBS.validation_failure_json(
                [JOBS.ValidationError("provider", "unknown provider", "NOPE")]
            )
        )
        self.assertEqual(
            failure,
            {
                "ok": False,
                "errors": [
                    {
                        "field": "provider",
                        "message": "unknown provider",
                        "value": "NOPE",
                    }
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
