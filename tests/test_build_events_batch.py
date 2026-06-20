import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Core as CORE
import O4_Event_Bus as EVENTS
from tests._build_events_helpers import event_summary


def _tile_plan(
    lat=12,
    lon=-123,
    *,
    steps=("vector", "mesh"),
    override_tile_config=False,
):
    import O4_Build_Models as MODELS

    return MODELS.BuildTilePlan(
        lat=lat,
        lon=lon,
        provider="BI",
        zoom_level=19,
        output_dir="build",
        custom_build_dir="custom",
        steps=steps,
        override_tile_config=override_tile_config,
    )


class BuildBatchEventTests(unittest.TestCase):
    def setUp(self):
        self._red_flag = CORE.UI.red_flag
        self._is_working = CORE.UI.is_working
        EVENTS.event_bus().clear()
        self.events = []
        for name in EVENTS.EventName:
            EVENTS.subscribe(name, self.events.append)

    def tearDown(self):
        EVENTS.event_bus().clear()
        CORE.UI.red_flag = self._red_flag
        CORE.UI.is_working = self._is_working

    def _patch_tile_class(self):
        return mock.patch.object(
            CORE.CFG,
            "Tile",
            side_effect=lambda lat, lon, custom: SimpleNamespace(
                lat=lat,
                lon=lon,
                custom_build_dir=custom,
                build_dir=f"build-{lat}-{lon}",
                dem=None,
                default_website="",
                default_zl=0,
                make_dirs=mock.Mock(),
                read_from_config=mock.Mock(return_value=1),
            ),
        )

    def test_batch_build_emits_selected_step_events_and_completion_callback(self):
        import O4_Build_Models as MODELS

        completed = []
        with (
            self._patch_tile_class(),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=1),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
            mock.patch.object(CORE.TILE, "build_tile", return_value=1),
        ):
            result = CORE.build_batch(
                MODELS.BuildPlan(tiles=(_tile_plan(steps=("vector", "tile")),)),
                on_tile_complete=completed.append,
            )

        self.assertTrue(result.ok)
        self.assertEqual(len(completed), 1)
        self.assertEqual(
            event_summary(self.events),
            [
                ("TILE_START", None, None, None),
                ("PIPELINE_STEP", "vector", "start", None),
                ("PIPELINE_STEP", "vector", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("PIPELINE_STEP", "tile", "start", None),
                ("PIPELINE_STEP", "tile", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("TILE_COMPLETE", "all", None, None),
            ],
        )

    def test_batch_build_interrupts_emit_error(self):
        import O4_Build_Models as MODELS

        def interrupting_build_tile(_tile, ctx=None):
            if ctx is not None:
                ctx.red_flag = True
            return 1

        with (
            self._patch_tile_class(),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(
                CORE.MESH, "build_mesh", side_effect=interrupting_build_tile
            ),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
            mock.patch.object(CORE.TILE, "build_tile", return_value=1),
        ):
            result = CORE.build_batch(
                MODELS.BuildPlan(tiles=(_tile_plan(steps=("vector", "mesh")),))
            )

        self.assertFalse(result.ok)
        self.assertIn(
            ("TILE_ERROR", "mesh", None, "interrupted"),
            event_summary(self.events),
        )
