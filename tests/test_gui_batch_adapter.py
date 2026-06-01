import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Models as MODELS
import O4_GUI_Utils as GUI


class GuiBatchAdapterTests(unittest.TestCase):
    def test_batch_plan_from_gui_state_maps_steps_and_tiles(self):
        state = SimpleNamespace(
            custom_build_dir="D:/Tiles/",
            list_lat_lon=[(2, 3), (1, 4)],
            do_osm=True,
            do_mesh=False,
            do_mask=True,
            do_dsf=True,
            do_ovl=False,
            override_cfg=True,
            provider="BI",
            zoom_level=16,
        )

        plan = GUI.batch_plan_from_state(state)

        self.assertIsInstance(plan, MODELS.BuildPlan)
        self.assertEqual(
            [(tile.lat, tile.lon) for tile in plan.tiles], [(1, 4), (2, 3)]
        )
        self.assertEqual(plan.tiles[0].steps, ("vector", "masks", "tile"))
        self.assertTrue(plan.tiles[0].override_tile_config)

    def test_completion_callback_removes_completed_gui_tile(self):
        canvas = mock.Mock()
        dico_tiles_todo = {(1, 2): "rect-id"}
        gui = SimpleNamespace(
            earth_window=SimpleNamespace(
                canvas=canvas,
                dico_tiles_todo=dico_tiles_todo,
            )
        )
        callback = GUI.batch_completion_callback(gui)

        callback(MODELS.BuildTileResult(1, 2, True, "all"))

        canvas.delete.assert_called_once_with("rect-id")
        self.assertEqual(dico_tiles_todo, {})

    def test_completion_callback_does_not_remove_failed_tile(self):
        canvas = mock.Mock()
        dico_tiles_todo = {(1, 2): "rect-id"}
        gui = SimpleNamespace(
            earth_window=SimpleNamespace(
                canvas=canvas,
                dico_tiles_todo=dico_tiles_todo,
            )
        )
        callback = GUI.batch_completion_callback(gui)

        callback(MODELS.BuildTileResult(1, 2, False, "mesh", "mesh failed"))

        canvas.delete.assert_not_called()
        self.assertEqual(dico_tiles_todo, {(1, 2): "rect-id"})


if __name__ == "__main__":
    unittest.main()
