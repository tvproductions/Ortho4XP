import asyncio
import contextlib
import io
import queue
import unittest
from dataclasses import FrozenInstanceError
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Provider_Failover as FAILOVER
import O4_Texture_Download_Scheduler as TDS
import O4_Tile_Utils as TILE
from O4_Texture_Source import TextureBuildResult, TextureSource


class ProviderFailoverSchedulerTests(unittest.TestCase):
    def setUp(self):
        FAILOVER.default_registry.reset()
        self.addCleanup(FAILOVER.default_registry.reset)

    def test_download_request_replaces_only_active_identity(self):
        request = TDS.TextureDownloadRequest(
            [1, 2, 16, "BI"],
            [1, 2, 16, "BI"],
        )

        replacement = request.with_active_attrs((1, 2, 16, "Arc"))

        self.assertEqual(request.requested_attrs, (1, 2, 16, "BI"))
        self.assertEqual(request.active_attrs, (1, 2, 16, "BI"))
        self.assertIsInstance(request.requested_attrs, tuple)
        self.assertIsInstance(request.active_attrs, tuple)
        self.assertEqual(replacement.requested_attrs, (1, 2, 16, "BI"))
        self.assertEqual(replacement.active_attrs, (1, 2, 16, "Arc"))
        with self.assertRaises(FrozenInstanceError):
            request.active_attrs = (1, 2, 16, "LOCAL")

    def test_async_download_accepts_request_payload_with_distinct_identities(self):
        tile = _tile()
        calls = []
        convert_queue = queue.Queue()
        download_queue = queue.Queue()
        download_queue.put(
            TDS.TextureDownloadRequest(
                (1, 2, 16, "BI"),
                (1, 2, 16, "Arc"),
            )
        )

        with _patched_download_dependencies(tile, calls):
            result = asyncio.run(
                TILE.async_download_textures(
                    tile,
                    download_queue,
                    convert_queue,
                    TDS.DownloadTextureOptions(
                        max_download_slots=1,
                        max_texture_download_retries=3,
                        workers=1,
                    ),
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(calls, [(1, 2, 16, "Arc")])
        _assert_arc_conversion(self, tile, convert_queue)

    def test_async_download_requeues_blacklisted_provider_with_replacement(self):
        tile = _tile()
        calls = []
        convert_queue = queue.Queue()

        with _patched_download_dependencies(tile, calls):
            result = asyncio.run(
                TILE.async_download_textures(
                    tile,
                    _queue(),
                    convert_queue,
                    TDS.DownloadTextureOptions(
                        max_download_slots=1,
                        max_texture_download_retries=5,
                        workers=1,
                    ),
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(calls, _expected_failover_calls())
        self.assertTrue(FAILOVER.default_registry.is_blacklisted("BI"))
        _assert_arc_conversion(self, tile, convert_queue)

    def test_async_download_skips_provider_already_blacklisted(self):
        tile = _tile()
        calls = []
        convert_queue = queue.Queue()
        _blacklist_bi()

        with _patched_download_dependencies(tile, calls):
            result = asyncio.run(
                TILE.async_download_textures(
                    tile,
                    _queue(),
                    convert_queue,
                    TDS.DownloadTextureOptions(
                        max_download_slots=1,
                        max_texture_download_retries=5,
                        workers=1,
                    ),
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(calls, [(1, 2, 16, "Arc")])
        _assert_arc_conversion(self, tile, convert_queue)

    def test_async_download_never_uses_extent_incompatible_replacement(self):
        tile = _tile()
        calls = []
        convert_queue = queue.Queue()
        providers = {
            "BI": {"code": "BI", "in_GUI": True, "extent": "global"},
            "LOCAL": {"code": "LOCAL", "in_GUI": True, "extent": "county"},
        }

        with _patched_download_dependencies(tile, calls, providers):
            result = asyncio.run(
                TILE.async_download_textures(
                    tile,
                    _queue(),
                    convert_queue,
                    TDS.DownloadTextureOptions(
                        max_download_slots=1,
                        max_texture_download_retries=3,
                        workers=1,
                    ),
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(calls, [(1, 2, 16, "BI")] * 3)
        self.assertTrue(convert_queue.empty())

    def test_async_download_preflight_rejects_extent_incompatible_replacement(self):
        tile = _tile()
        calls = []
        providers = {
            "BI": {"code": "BI", "in_GUI": True, "extent": "global"},
            "LOCAL": {"code": "LOCAL", "in_GUI": True, "extent": "county"},
        }
        _blacklist_bi()

        with _patched_download_dependencies(tile, calls, providers):
            result = asyncio.run(
                TILE.async_download_textures(
                    tile,
                    _queue(),
                    queue.Queue(),
                    TDS.DownloadTextureOptions(
                        max_download_slots=1,
                        max_texture_download_retries=1,
                        workers=1,
                    ),
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(calls, [(1, 2, 16, "BI")])


@contextlib.contextmanager
def _patched_download_dependencies(tile, calls, providers=None):
    with (
        mock.patch.dict(
            TDS.IMG.providers_dict,
            providers or _providers(),
            clear=True,
        ),
        mock.patch.object(TDS.IMG, "async_build_texture_source", _build(tile, calls)),
        mock.patch.object(TDS.IMG, "imagery_download_summary", return_value=None),
        mock.patch.object(TDS.IMG, "failures_for_texture", return_value=[]),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        yield


def _build(tile, calls):
    async def build(_tile, *attrs):
        calls.append(attrs)
        if attrs[3] == "BI":
            return TextureBuildResult.failure(tuple(attrs), "download failed")
        source = TextureSource(tile, tuple(attrs), Image.new("RGB", (4, 4)))
        return TextureBuildResult.success(source)

    return build


def _providers():
    return {
        "BI": {"code": "BI", "in_GUI": True, "extent": "global"},
        "Arc": {"code": "Arc", "in_GUI": True, "extent": "global"},
        "LOCAL": {"code": "LOCAL", "in_GUI": True, "extent": "county"},
    }


def _expected_failover_calls():
    return [
        (1, 2, 16, "BI"),
        (1, 2, 16, "BI"),
        (1, 2, 16, "BI"),
        (1, 2, 16, "Arc"),
    ]


def _blacklist_bi():
    with (
        mock.patch.object(FAILOVER.LOG.UI, "vprint"),
        mock.patch.object(FAILOVER.LOG.UI, "log_event"),
    ):
        for _ in range(3):
            FAILOVER.default_registry.record_failure("BI")


def _assert_arc_conversion(test_case, tile, convert_queue):
    queued_tile, queued_source = convert_queue.get_nowait()
    test_case.assertIs(queued_tile, tile)
    test_case.assertEqual(queued_source.attrs, (1, 2, 16, "Arc"))
    test_case.assertEqual(queued_source.terrain_attrs, (1, 2, 16, "BI"))


def _tile():
    return type("Tile", (), {"lat": 1, "lon": 2})()


def _queue():
    download_queue = queue.Queue()
    download_queue.put((1, 2, 16, "BI"))
    return download_queue


if __name__ == "__main__":
    unittest.main()
