import asyncio
import contextlib
import io
import queue
import unittest
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Download_Scheduler as TDS
import O4_Tile_Utils as TILE
from O4_Texture_Source import TextureBuildResult, TextureSource


class AsyncTextureDownloadTests(unittest.TestCase):
    def test_async_download_textures_limits_concurrency_and_enqueues_conversions(self):
        active = 0
        max_active = 0
        lock = asyncio.Lock()
        convert_queue = queue.Queue()

        async def build(tile, *attrs):
            nonlocal active, max_active
            async with lock:
                active += 1
                max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            async with lock:
                active -= 1
            source = TextureSource(tile, tuple(attrs), Image.new("RGB", (4, 4)))
            return TextureBuildResult.success(source)

        download_queue = queue.Queue()
        download_queue.put((1, 2, 16, "BI"))
        download_queue.put((17, 18, 16, "BI"))
        download_queue.put((33, 34, 16, "BI"))
        tile = self._tile()

        with (
            mock.patch.object(
                TDS.IMG,
                "async_build_jpeg_ortho",
                side_effect=AssertionError("legacy build called"),
            ),
            mock.patch.object(TDS.IMG, "async_build_texture_source", side_effect=build),
            mock.patch.object(TDS.IMG, "imagery_download_summary", return_value=None),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = asyncio.run(
                TILE.async_download_textures(
                    tile,
                    download_queue,
                    convert_queue,
                    self._options(workers=2),
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(max_active, 2)
        self.assertEqual(convert_queue.qsize(), 3)
        queued_tile, queued_source = convert_queue.get_nowait()
        self.assertIs(queued_tile, tile)
        self.assertIsInstance(queued_source, TextureSource)
        self.assertEqual(queued_source.attrs, (1, 2, 16, "BI"))

    def test_async_download_textures_retries_and_summarizes_final_failures_once(self):
        calls = []
        summaries = []

        async def fail_build(_tile, *attrs):
            calls.append(attrs)
            return TextureBuildResult.failure(tuple(attrs), "download failed")

        def summary(tile_coords, final_failures):
            summaries.append((tile_coords, final_failures))
            return None

        with (
            mock.patch.object(
                TDS.IMG,
                "async_build_jpeg_ortho",
                side_effect=AssertionError("legacy build called"),
            ),
            mock.patch.object(
                TDS.IMG, "async_build_texture_source", side_effect=fail_build
            ),
            mock.patch.object(TDS.IMG, "imagery_download_summary", side_effect=summary),
            mock.patch.object(TDS.IMG, "failures_for_texture", return_value=[]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = asyncio.run(
                TILE.async_download_textures(
                    self._tile(),
                    self._queue(),
                    queue.Queue(),
                    self._options(workers=2, retries=2),
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(len(summaries[0][1]), 1)

    def _options(self, workers=None, retries=3):
        return TDS.DownloadTextureOptions(
            max_download_slots=1,
            max_texture_download_retries=retries,
            workers=workers,
        )

    def _tile(self):
        return type("Tile", (), {"lat": 1, "lon": 2})()

    def _queue(self):
        download_queue = queue.Queue()
        download_queue.put((1, 2, 16, "BI"))
        return download_queue


if __name__ == "__main__":
    unittest.main()
