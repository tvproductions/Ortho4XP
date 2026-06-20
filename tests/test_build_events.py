import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Context as BC
import O4_Build_Core as CORE
import O4_Event_Bus as EVENTS


def _tile():
    return SimpleNamespace(lat=12, lon=-123, build_dir="build")


# The event assertions only care about the stable lifecycle fields.
def _event_summary(events):
    return [
        (
            event.name.value,
            event.payload.get("pipeline"),
            event.payload.get("step"),
            event.payload.get("status"),
            event.payload.get("message"),
        )
        for event in events
    ]


def _assert_event_payloads(test_case, events, mode):
    test_case.assertTrue(all(event.payload["lat"] == 12 for event in events))
    test_case.assertTrue(all(event.payload["lon"] == -123 for event in events))
    test_case.assertTrue(all(event.payload["mode"] == mode for event in events))


# This sequence is the exact all-in-one lifecycle contract.
ALL_MODE_LIFECYCLE_EVENTS = [
    ("TILE_START", None, None, None, None),
    ("PIPELINE_STEP", "all", "vector", "running", None),
    ("PIPELINE_STEP", "all", "vector", "complete", None),
    ("TILE_PROGRESS", None, None, None, None),
    ("PIPELINE_STEP", "all", "mesh", "running", None),
    ("PIPELINE_STEP", "all", "mesh", "complete", None),
    ("TILE_PROGRESS", None, None, None, None),
    ("PIPELINE_STEP", "all", "masks", "running", None),
    ("PIPELINE_STEP", "all", "masks", "complete", None),
    ("TILE_PROGRESS", None, None, None, None),
    ("PIPELINE_STEP", "all", "tile", "running", None),
    ("PIPELINE_STEP", "all", "tile", "complete", None),
    ("TILE_PROGRESS", None, None, None, None),
    ("TILE_COMPLETE", None, "all", None, None),
]


BATCH_MODE_SELECTED_STEP_EVENTS = [
    ("TILE_START", None, None, None, None),
    ("PIPELINE_STEP", "batch", "vector", "running", None),
    ("PIPELINE_STEP", "batch", "vector", "complete", None),
    ("TILE_PROGRESS", None, None, None, None),
    ("PIPELINE_STEP", "batch", "mesh", "running", None),
    ("PIPELINE_STEP", "batch", "mesh", "complete", None),
    ("TILE_PROGRESS", None, None, None, None),
    ("TILE_COMPLETE", None, "all", None, None),
]


def _tile_plan(*, steps=("vector", "mesh")):
    import O4_Build_Models as MODELS

    return MODELS.BuildTilePlan(
        lat=12,
        lon=-123,
        provider="BI",
        zoom_level=16,
        output_dir="Tiles",
        custom_build_dir="Tiles/",
        steps=steps,
        override_tile_config=False,
    )


class EventSubscriptionTests(unittest.TestCase):
    # Each test captures the full event stream and asserts on the published order.
    def setUp(self):
        EVENTS.event_bus().clear()
        self.events = []
        for name in EVENTS.EventName:
            EVENTS.subscribe(name, self.events.append)

    def tearDown(self):
        EVENTS.event_bus().clear()


class BuildAllEventTests(EventSubscriptionTests):
    def _run_build_tile_all(self):
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
            return CORE.build_tile_all(_tile())

    def test_build_tile_all_emits_lifecycle_events(self):
        result = self._run_build_tile_all()
        progress_payloads = [
            event.payload
            for event in self.events
            if event.name == EVENTS.EventName.TILE_PROGRESS
        ]

        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        self.assertEqual(_event_summary(self.events), ALL_MODE_LIFECYCLE_EVENTS)
        _assert_event_payloads(self, self.events, "all")
        self.assertEqual(
            [(p["completed_steps"], p["total_steps"]) for p in progress_payloads],
            [(1, 4), (2, 4), (3, 4), (4, 4)],
        )

    def test_interrupted_all_in_one_emits_tile_error_not_complete(self):
        def interrupting_mesh(_tile, ctx: BC.BuildContext | None = None):
            if ctx is None:
                raise AssertionError("ctx is required")
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
            ("PIPELINE_STEP", "all", "mesh", "error", "interrupted"),
            _event_summary(self.events),
        )
        self.assertIn(
            ("TILE_ERROR", None, "mesh", None, "interrupted"),
            _event_summary(self.events),
        )
        self.assertNotIn("TILE_COMPLETE", [event.name.value for event in self.events])


class BuildBatchEventTests(EventSubscriptionTests):
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
        ):
            result = CORE.build_batch(
                MODELS.BuildPlan((_tile_plan(steps=("vector", "mesh")),)),
                on_tile_complete=completed.append,
            )

        self.assertTrue(result.ok)
        self.assertEqual(completed, list(result.tiles))
        self.assertEqual(_event_summary(self.events), BATCH_MODE_SELECTED_STEP_EVENTS)
        _assert_event_payloads(self, self.events, "batch")

    def test_falsey_batch_step_emits_tile_error(self):
        import O4_Build_Models as MODELS

        with (
            self._patch_tile_class(),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=0),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
        ):
            result = CORE.build_batch(MODELS.BuildPlan((_tile_plan(steps=("mesh",)),)))

        self.assertFalse(result.ok)
        self.assertEqual(result.tiles[0].message, "mesh failed")
        self.assertIn(
            ("PIPELINE_STEP", "batch", "mesh", "error", "mesh failed"),
            _event_summary(self.events),
        )
        self.assertIn(
            ("TILE_ERROR", None, "mesh", None, "mesh failed"),
            _event_summary(self.events),
        )
        self.assertNotIn("TILE_COMPLETE", [event.name.value for event in self.events])
