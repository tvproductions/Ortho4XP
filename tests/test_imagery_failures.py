import contextlib
import io
import json
import os
import queue
import tempfile
import unittest
from unittest import mock

import _path  # noqa: F401

import requests

import O4_Imagery_Utils as IMG
import O4_Imagery_Failures as IFAIL
import O4_Tile_Utils as TILE
import O4_UI_Utils as UI


class FakeResponse:
    def __init__(self, status_code, headers=None, content=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content

    def __str__(self):
        return f"<Response [{self.status_code}]>"


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, *_args, **_kwargs):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class ImageryFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_log = UI.log
        self.original_verbosity = UI.verbosity
        self.original_check = IMG.check_tms_response
        self.original_max_connect = IMG.max_connect_retries
        self.original_max_baddata = IMG.max_baddata_retries
        self.original_failures = list(IMG.imagery_failure_records)
        self.original_incomplete = dict(IMG.incomplete_imgs)
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
        IMG.incomplete_imgs.clear()

    def _restore_state(self):
        UI.log = self.original_log
        UI.verbosity = self.original_verbosity
        IMG.check_tms_response = self.original_check
        IMG.max_connect_retries = self.original_max_connect
        IMG.max_baddata_retries = self.original_max_baddata
        IMG.imagery_failure_records.clear()
        IMG.imagery_failure_records.extend(self.original_failures)
        IMG.incomplete_imgs.clear()
        IMG.incomplete_imgs.update(self.original_incomplete)

    def test_http_404_records_sanitized_failure_at_normal_verbosity(self):
        session = FakeSession([FakeResponse(404, {"Content-Type": "text/plain"})])
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            success, data, failure = IMG.http_request_to_image(
                256,
                256,
                "https://tiles.example.test/abc/1/2/3.jpg?apikey=secret",
                IFAIL.request_headers_with_context({}, self._request_context()),
                session,
            )

        event = self._events()[0]
        self.assertEqual(success, 0)
        self.assertEqual(data, "[404]")
        self.assertEqual(failure.status_code, 404)
        self.assertEqual(failure.provider_code, "BI")
        self.assertEqual(failure.request_type, "tms")
        self.assertEqual(failure.connect_retries, 0)
        self.assertEqual(event["message"], "Imagery request failed")
        self.assertEqual(event["context"]["url_origin"], "https://tiles.example.test")
        self.assertEqual(event["context"]["url_path"], "/abc/1/2/3.jpg")
        self.assertNotIn("full_url", event["context"])
        self.assertEqual(stdout.getvalue(), "")

    def test_forbidden_server_error_and_wrong_content_type_are_structured(self):
        cases = [
            (403, "forbidden", "text/plain"),
            (503, "server_error", "text/plain"),
            (200, "wrong_content_type", "text/html"),
        ]
        for status_code, reason, content_type in cases:
            with self.subTest(status_code=status_code):
                session = FakeSession(
                    [FakeResponse(status_code, {"Content-Type": content_type}, b"bad")]
                )

                _success, _data, failure = IMG.http_request_to_image(
                    256,
                    256,
                    f"https://tiles.example.test/{status_code}",
                    IFAIL.request_headers_with_context({}, self._request_context()),
                    session,
                )

                self.assertEqual(failure.status_code, status_code)
                self.assertEqual(failure.reason, reason)

    def test_corrupted_image_retries_bad_data_and_records_final_failure(self):
        IMG.check_tms_response = True
        IMG.max_baddata_retries = 2
        session = FakeSession(
            [
                FakeResponse(200, {"Content-Type": "image/jpeg"}, b"not an image"),
                FakeResponse(200, {"Content-Type": "image/jpeg"}, b"still bad"),
            ]
        )

        with mock.patch.object(IMG.time, "sleep"):
            _success, _data, failure = IMG.http_request_to_image(
                256,
                256,
                "https://tiles.example.test/corrupt",
                IFAIL.request_headers_with_context({}, self._request_context()),
                session,
            )

        self.assertEqual(session.calls, 2)
        self.assertEqual(failure.status_code, 200)
        self.assertEqual(failure.reason, "corrupted_image")
        self.assertEqual(failure.bad_data_retries, 2)

    def test_request_exception_retries_connect_and_records_failure(self):
        IMG.check_tms_response = True
        IMG.max_connect_retries = 2
        session = FakeSession(
            [
                requests.exceptions.ConnectionError("down"),
                requests.exceptions.ConnectionError("still down"),
            ]
        )

        with (
            mock.patch.object(IMG.time, "sleep"),
            mock.patch.object(IMG.requests, "Session", return_value=session),
        ):
            _success, _data, failure = IMG.http_request_to_image(
                256,
                256,
                "https://tiles.example.test/connect",
                IFAIL.request_headers_with_context({}, self._request_context()),
                session,
            )

        self.assertEqual(session.calls, 2)
        self.assertEqual(failure.status_code, "connection_failure")
        self.assertEqual(failure.connect_retries, 2)

    def test_debug_verbosity_includes_full_url(self):
        UI.verbosity = 3
        session = FakeSession([FakeResponse(404, {"Content-Type": "text/plain"})])

        with contextlib.redirect_stdout(io.StringIO()):
            IMG.http_request_to_image(
                256,
                256,
                "https://tiles.example.test/path?token=secret",
                IFAIL.request_headers_with_context({}, self._request_context()),
                session,
            )

        self.assertEqual(
            self._events()[0]["context"]["full_url"],
            "https://tiles.example.test/path?token=secret",
        )

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


class TextureDownloadRetryTests(unittest.TestCase):
    def setUp(self):
        self.original_retries = TILE.max_texture_download_retries
        self.addCleanup(self._restore_state)
        TILE.max_texture_download_retries = 3

    def _restore_state(self):
        TILE.max_texture_download_retries = self.original_retries

    def test_texture_retries_use_configured_limit(self):
        TILE.max_texture_download_retries = 2
        calls = []

        def fail_build(_tile, *attrs):
            calls.append(attrs)
            return 0

        with (
            mock.patch.object(IMG, "build_jpeg_ortho", side_effect=fail_build),
            mock.patch.object(IMG, "imagery_download_summary", return_value=None),
            mock.patch.object(IMG, "failures_for_texture", return_value=[]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            TILE.download_textures(
                self._tile(), self._queue(), queue.Queue(), workers=1
            )

        self.assertEqual(len(calls), 2)

    def test_failed_texture_attempts_are_summarized_once(self):
        TILE.max_texture_download_retries = 1
        summaries = []

        def summary(tile_coords, final_failures):
            summaries.append((tile_coords, final_failures))
            return {
                "total_textures": len(final_failures),
                "by_provider": {"BI": len(final_failures)},
                "by_status": {"download_failed": len(final_failures)},
                "by_request_type": {"unknown": len(final_failures)},
            }

        with (
            mock.patch.object(IMG, "build_jpeg_ortho", return_value=0),
            mock.patch.object(IMG, "imagery_download_summary", side_effect=summary),
            mock.patch.object(IMG, "failures_for_texture", return_value=[]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            download_queue = queue.Queue()
            download_queue.put((1, 2, 16, "BI"))
            download_queue.put((17, 18, 16, "BI"))
            TILE.download_textures(
                self._tile(), download_queue, queue.Queue(), workers=1
            )

        self.assertEqual(len(summaries), 1)
        self.assertEqual(len(summaries[0][1]), 2)

    def test_successful_retry_is_not_in_final_failure_summary(self):
        TILE.max_texture_download_retries = 3
        outcomes = [0, 1]

        def flaky_build(_tile, *_attrs):
            return outcomes.pop(0)

        with (
            mock.patch.object(IMG, "build_jpeg_ortho", side_effect=flaky_build),
            mock.patch.object(
                IMG, "imagery_download_summary", return_value=None
            ) as summary,
            mock.patch.object(IMG, "failures_for_texture", return_value=[]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            TILE.download_textures(
                self._tile(), self._queue(), queue.Queue(), workers=1
            )

        self.assertEqual(summary.call_args.args[1], [])

    def _tile(self):
        return type("Tile", (), {"lat": 1, "lon": 2})()

    def _queue(self):
        download_queue = queue.Queue()
        download_queue.put((1, 2, 16, "BI"))
        return download_queue


if __name__ == "__main__":
    unittest.main()
