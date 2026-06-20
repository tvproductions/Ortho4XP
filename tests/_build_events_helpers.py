from contextlib import ExitStack
from unittest import mock

import O4_Build_Core as CORE
import O4_Event_Bus as EVENTS

EXPECTED_ALL_IN_ONE_EVENT_SUMMARY = [
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
]

EXPECTED_ALL_IN_ONE_PROGRESS = [(1, 4), (2, 4), (3, 4), (4, 4)]


def event_summary(events):
    return [
        (
            event.name.value,
            event.payload.get("step"),
            event.payload.get("status"),
            event.payload.get("message"),
        )
        for event in events
    ]


def run_all_in_one_build(mesh_side_effect=None):
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(CORE.UI, "red_flag", False))
        stack.enter_context(mock.patch.object(CORE.IMG, "incomplete_imgs", {}))
        stack.enter_context(
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1)
        )
        if mesh_side_effect is None:
            stack.enter_context(
                mock.patch.object(CORE.MESH, "build_mesh", return_value=1)
            )
        else:
            stack.enter_context(
                mock.patch.object(CORE.MESH, "build_mesh", side_effect=mesh_side_effect)
            )
        stack.enter_context(mock.patch.object(CORE.MASK, "build_masks", return_value=1))
        stack.enter_context(mock.patch.object(CORE.TILE, "build_tile", return_value=1))
        stack.enter_context(mock.patch.object(CORE.UI, "lvprint"))
        stack.enter_context(mock.patch.object(CORE.UI, "exit_message_and_bottom_line"))
        return CORE.build_tile_all(_tile())


def assert_all_in_one_lifecycle_events(testcase, events):
    testcase.assertEqual(event_summary(events), EXPECTED_ALL_IN_ONE_EVENT_SUMMARY)
    lat_values = set()
    lon_values = set()
    mode_values = set()
    progress_pairs = []
    for event in events:
        lat_values.add(event.payload["lat"])
        lon_values.add(event.payload["lon"])
        mode_values.add(event.payload["mode"])
        if event.name == EVENTS.EventName.TILE_PROGRESS:
            progress_pairs.append(
                (event.payload["completed_steps"], event.payload["total_steps"])
            )
    testcase.assertEqual(lat_values, {12})
    testcase.assertEqual(lon_values, {-123})
    testcase.assertEqual(mode_values, {"all"})
    testcase.assertEqual(progress_pairs, EXPECTED_ALL_IN_ONE_PROGRESS)


def _tile():
    from types import SimpleNamespace

    return SimpleNamespace(lat=12, lon=-123, build_dir="build")
