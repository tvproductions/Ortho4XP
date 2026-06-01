import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Models as MODELS


class BuildModelsTests(unittest.TestCase):
    def test_build_tile_plan_stores_normalized_values(self):
        plan = MODELS.BuildTilePlan(
            lat=43,
            lon=-79,
            provider="BI",
            zoom_level=16,
            output_dir="D:/jobs/Tiles",
            custom_build_dir="D:/jobs/Tiles/",
            steps=("vector", "mesh", "masks", "tile"),
            override_tile_config=False,
        )

        self.assertEqual(plan.lat, 43)
        self.assertEqual(plan.lon, -79)
        self.assertEqual(plan.provider, "BI")
        self.assertEqual(plan.zoom_level, 16)
        self.assertEqual(plan.steps, ("vector", "mesh", "masks", "tile"))

    def test_build_plan_groups_tile_plans(self):
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

        plan = MODELS.BuildPlan(tiles=(tile,))

        self.assertEqual(plan.tiles, (tile,))

    def test_batch_result_ok_requires_all_tile_results_ok(self):
        success = MODELS.BuildTileResult(0, 0, True, "all")
        failure = MODELS.BuildTileResult(0, 1, False, "mesh", "mesh failed")

        self.assertTrue(MODELS.batch_ok((success,)))
        self.assertFalse(MODELS.batch_ok((success, failure)))

    def test_step_constants_are_in_execution_order(self):
        self.assertEqual(
            MODELS.ALL_STEPS,
            ("vector", "mesh", "masks", "tile", "overlays"),
        )
        self.assertEqual(
            MODELS.DEFAULT_STEPS,
            ("vector", "mesh", "masks", "tile"),
        )


if __name__ == "__main__":
    unittest.main()
