import unittest
from types import SimpleNamespace

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Context as BC
import O4_Build_Core as CORE
import O4_Event_Bus as EVENTS
from tests._build_events_helpers import (
    assert_all_in_one_lifecycle_events,
    event_summary,
    run_all_in_one_build,
)


def _tile():
    return SimpleNamespace(lat=12, lon=-123, build_dir="build")


class BuildAllEventTests(unittest.TestCase):
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

    def test_build_tile_all_emits_lifecycle_events(self):
        result = run_all_in_one_build()
        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        assert_all_in_one_lifecycle_events(self, self.events)

    def test_interrupted_all_in_one_emits_tile_error_not_complete(self):
        def interrupting_mesh(_tile, ctx: BC.BuildContext | None = None):
            if ctx is not None:
                ctx.red_flag = True
            return 0

        result = run_all_in_one_build(mesh_side_effect=interrupting_mesh)

        self.assertEqual(result, CORE.BuildResult(False, "mesh", "interrupted"))
        self.assertIn(
            ("TILE_ERROR", "mesh", None, "interrupted"),
            event_summary(self.events),
        )
        self.assertNotIn("TILE_COMPLETE", [event.name.value for event in self.events])
