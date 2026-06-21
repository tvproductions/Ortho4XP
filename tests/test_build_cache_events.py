import unittest
from contextlib import ExitStack, contextmanager
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
            event.payload.get("pipeline"),
            event.payload.get("step"),
            event.payload.get("status"),
        )
        for event in events
    ]


class BuildCacheEventTests(unittest.TestCase):
    def setUp(self):
        EVENTS.event_bus().clear()
        self.events = []
        for name in EVENTS.EventName:
            EVENTS.subscribe(name, self.events.append)

    def tearDown(self):
        EVENTS.event_bus().clear()

    def test_build_tile_all_cache_hit_emits_cache_event_without_steps(self):
        with _patched_cache_hit():
            result = CORE.build_tile_all(_tile())

        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        self.assertEqual(
            _event_summary(self.events),
            [
                ("TILE_START", None, None, None),
                ("CACHE_HIT", None, None, None),
                ("TILE_COMPLETE", None, "all", None),
            ],
        )
        self.assertEqual(_cache_hit_payloads(self.events), [_expected_cache_payload()])


@contextmanager
def _patched_cache_hit():
    hit = SimpleNamespace(
        metadata_path="build/tile_meta.json",
        parameter_hash="abc123",
    )
    patchers = (
        mock.patch.object(CORE.CACHE, "read_cache_hit", return_value=hit),
        mock.patch.object(CORE.CACHE, "write_cache_metadata"),
        mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
        mock.patch.object(CORE.VMAP, "build_poly_file"),
        mock.patch.object(CORE.MESH, "build_mesh"),
        mock.patch.object(CORE.MASK, "build_masks"),
        mock.patch.object(CORE.TILE, "build_tile"),
        mock.patch.object(CORE.UI, "lvprint"),
        mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
    )
    with ExitStack() as stack:
        for patcher in patchers:
            stack.enter_context(patcher)
        yield


def _cache_hit_payloads(events):
    return [
        event.payload for event in events if event.name == EVENTS.EventName.CACHE_HIT
    ]


def _expected_cache_payload():
    return {
        "lat": 12,
        "lon": -123,
        "mode": "all",
        "metadata_path": "build/tile_meta.json",
        "parameter_hash": "abc123",
    }


if __name__ == "__main__":
    unittest.main()
