import asyncio
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import aiohttp
from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Async_HTTP as AHTTP
import O4_Imagery_Failures as IFAIL
import O4_Imagery_Utils as IMG
import O4_UI_Utils as UI


def jpeg_bytes():
    image = Image.new("RGB", (4, 4), (10, 20, 30))
    stream = io.BytesIO()
    image.save(stream, format="JPEG")
    return stream.getvalue()


class FakeAsyncResponse:
    def __init__(self, status, headers=None, content=b""):
        self.status = status
        self.headers = headers or {}
        self._content = content

    async def read(self):
        return self._content

    def __str__(self):
        return f"<Response [{self.status}]>"


class FakeAsyncRequest:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False


class FakeAsyncSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.call_kwargs = []

    def get(self, *_args, **kwargs):
        self.calls += 1
        self.call_kwargs.append(kwargs)
        return FakeAsyncRequest(self.responses.pop(0))


class AsyncHttpRequestTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_log = UI.log
        self.original_verbosity = UI.verbosity
        self.original_check = IMG.check_tms_response
        self.original_max_connect = IMG.max_connect_retries
        self.original_max_baddata = IMG.max_baddata_retries
        self.original_failures = list(IMG.imagery_failure_records)
        self.addCleanup(self._restore_state)
        self.path_patch = mock.patch.object(
            UI.FNAMES,
            "resource_path",
            side_effect=lambda relative: os.path.join(self.temp_dir.name, relative),
        )
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        UI.log = True
        UI.verbosity = 1
        IMG.check_tms_response = False
        IMG.max_connect_retries = 5
        IMG.max_baddata_retries = 5
        IMG.imagery_failure_records.clear()

    def _restore_state(self):
        UI.log = self.original_log
        UI.verbosity = self.original_verbosity
        IMG.check_tms_response = self.original_check
        IMG.max_connect_retries = self.original_max_connect
        IMG.max_baddata_retries = self.original_max_baddata
        IMG.imagery_failure_records.clear()
        IMG.imagery_failure_records.extend(self.original_failures)

    def test_async_http_request_decodes_image_in_thread(self):
        session = FakeAsyncSession(
            [FakeAsyncResponse(200, {"Content-Type": "image/jpeg"}, jpeg_bytes())]
        )

        with mock.patch.object(
            AHTTP.asyncio, "to_thread", wraps=asyncio.to_thread
        ) as to_thread:
            success, data, failure = asyncio.run(
                IMG.async_http_request_to_image(
                    "https://tiles.example.test/success.jpg",
                    IFAIL.request_headers_with_context({}, self._request_context()),
                    session,
                )
            )

        self.assertEqual(success, 1)
        self.assertEqual(data.size, (4, 4))
        self.assertIsNone(failure)
        self.assertEqual(session.calls, 1)
        self.assertEqual(to_thread.call_count, 1)

    def test_async_connection_error_retries_and_records_failure(self):
        IMG.check_tms_response = True
        IMG.max_connect_retries = 2
        session = FakeAsyncSession(
            [
                aiohttp.ClientError("down"),
                aiohttp.ClientError("still down"),
            ]
        )

        with mock.patch.object(IMG, "async_request_sleep", new=mock.AsyncMock()):
            success, data, failure = asyncio.run(
                IMG.async_http_request_to_image(
                    "https://tiles.example.test/connect",
                    IFAIL.request_headers_with_context({}, self._request_context()),
                    session,
                )
            )

        self.assertEqual(success, 0)
        self.assertEqual(data, "connection_failure")
        self.assertEqual(session.calls, 2)
        self.assertEqual(failure.status_code, "connection_failure")
        self.assertEqual(failure.connect_retries, 2)

    def test_async_connection_error_honors_zero_retry_limit(self):
        IMG.check_tms_response = True
        IMG.max_connect_retries = 0
        session = FakeAsyncSession([aiohttp.ClientError("down")])

        with mock.patch.object(IMG, "async_request_sleep", new=mock.AsyncMock()):
            success, data, failure = asyncio.run(
                IMG.async_http_request_to_image(
                    "https://tiles.example.test/connect",
                    IFAIL.request_headers_with_context({}, self._request_context()),
                    session,
                )
            )

        self.assertEqual(success, 0)
        self.assertEqual(data, "connection_failure")
        self.assertEqual(session.calls, 1)
        self.assertEqual(failure.status_code, "connection_failure")
        self.assertEqual(failure.connect_retries, 1)

    def test_async_corrupted_image_retries_bad_data_and_records_failure(self):
        IMG.check_tms_response = True
        IMG.max_baddata_retries = 2
        session = FakeAsyncSession(
            [
                FakeAsyncResponse(200, {"Content-Type": "image/jpeg"}, b"bad"),
                FakeAsyncResponse(200, {"Content-Type": "image/jpeg"}, b"still bad"),
            ]
        )

        success, data, failure = asyncio.run(
            IMG.async_http_request_to_image(
                "https://tiles.example.test/corrupt",
                IFAIL.request_headers_with_context({}, self._request_context()),
                session,
            )
        )

        self.assertEqual(success, 0)
        self.assertEqual(data, "200")
        self.assertEqual(session.calls, 2)
        self.assertEqual(failure.status_code, 200)
        self.assertEqual(failure.reason, "corrupted_image")
        self.assertEqual(failure.bad_data_retries, 2)

    def test_async_http_404_records_sanitized_failure(self):
        session = FakeAsyncSession(
            [FakeAsyncResponse(404, {"Content-Type": "text/plain"})]
        )

        success, data, failure = asyncio.run(
            IMG.async_http_request_to_image(
                "https://tiles.example.test/abc/1/2/3.jpg?apikey=secret",
                IFAIL.request_headers_with_context({}, self._request_context()),
                session,
            )
        )

        event = self._events()[0]
        self.assertEqual(success, 0)
        self.assertEqual(data, "[404]")
        self.assertEqual(failure.status_code, 404)
        self.assertEqual(event["context"]["url_origin"], "https://tiles.example.test")
        self.assertEqual(event["context"]["url_path"], "/abc/1/2/3.jpg")
        self.assertNotIn("full_url", event["context"])

    def _request_context(self):
        return {
            "provider_code": "BI",
            "request_type": "tms",
            "url_type": "tms",
            "texture_filename": "tex.jpg",
            "tile_x": 1,
            "tile_y": 2,
            "zoomlevel": 16,
        }

    def _events(self):
        with open(UI.log_path(), encoding="utf-8") as f:
            return [json.loads(line) for line in f]


if __name__ == "__main__":
    unittest.main()
