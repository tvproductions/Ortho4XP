import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Core as CORE
import O4_Event_Bus as EVENTS


def _tile():
    return SimpleNamespace(lat=12, lon=-123, build_dir="build")


def _event_summary(events):
    return [
        (
            event.name.value,
            event.payload.get("step"),
            event.payload.get("status"),
            event.payload.get("message"),
        )
        for event in events
    ]


class BuildAllEventTests(unittest.TestCase):
    def setUp(self):
        EVENTS.event_bus().clear()
        self.events = []
        for name in EVENTS.EventName:
            EVENTS.subscribe(name, self.events.append)

    def tearDown(self):
        EVENTS.event_bus().clear()

    def test_build_tile_all_emits_lifecycle_events(self):
        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=1),
            mock.patch.object(CORE.MASK, "build_masks", return_value=1),
            mock.patch.object(CORE.TILE, "build_tile", return_value=1),
            mock.patch.object(CORE.UI, "lvprint"),
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
        ):
            result = CORE.build_tile_all(_tile())

        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        self.assertEqual(
            _event_summary(self.events),
            [
                ("TILE_START", None, None, None),
                ("PIPELINE_STEP", "vector", "start", None),
                ("PIPELINE_STEP", "vector", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("PIPELINE_STEP", "mesh", "start", None),
                ("PIPELINE_STEP", "mesh", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("PIPELINE_STEP", "masks", "start", None),
                ("PIPELINE_STEP", "masks", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("PIPELINE_STEP", "tile", "start", None),
                ("PIPELINE_STEP", "tile", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("TILE_COMPLETE", "all", None, None),
            ],
        )
        self.assertTrue(all(event.payload["lat"] == 12 for event in self.events))
        self.assertTrue(all(event.payload["lon"] == -123 for event in self.events))
        self.assertTrue(all(event.payload["mode"] == "all" for event in self.events))
        progress_payloads = [
            event.payload
            for event in self.events
            if event.name == EVENTS.EventName.TILE_PROGRESS
        ]
        self.assertEqual(
            [(p["completed_steps"], p["total_steps"]) for p in progress_payloads],
            [(1, 4), (2, 4), (3, 4), (4, 4)],
        )

    def test_interrupted_all_in_one_emits_tile_error_not_complete(self):
        def interrupting_mesh(_tile, ctx=None):
            ctx.red_flag = True
            return 0

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", side_effect=interrupting_mesh),
            mock.patch.object(CORE.MASK, "build_masks", return_value=1),
            mock.patch.object(CORE.TILE, "build_tile", return_value=1),
            mock.patch.object(CORE.UI, "lvprint"),
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
        ):
            result = CORE.build_tile_all(_tile())

        self.assertEqual(result, CORE.BuildResult(False, "mesh", "interrupted"))
        self.assertIn(
            ("TILE_ERROR", "mesh", None, "interrupted"),
            _event_summary(self.events),
        )
        self.assertNotIn("TILE_COMPLETE", [event.name.value for event in self.events])

