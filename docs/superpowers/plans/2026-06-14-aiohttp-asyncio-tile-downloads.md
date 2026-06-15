# aiohttp + asyncio Tile Downloads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the imagery tile download HTTP path and texture download worker loop with `aiohttp` and `asyncio` while preserving current synchronous callers and failure semantics.

**Architecture:** Add async HTTP primitives in `O4_Imagery_Utils.py` behind the existing `http_request_to_image()` wrapper, then replace `O4_Tile_Utils.download_textures()` internals with an async scheduler wrapped by the same synchronous API. Tests drive the async behavior without real network access by using fake async sessions and patched build functions.

**Tech Stack:** Python 3.13, `unittest`, `asyncio`, `aiohttp`, Pillow, `uv`, Ruff, ty.

---

## File Structure

- Modify `pyproject.toml`: add `aiohttp` runtime dependency.
- Modify `uv.lock`: regenerate through `uv lock` after adding `aiohttp`.
- Modify `src/O4_Imagery_Utils.py`: import `asyncio` and `aiohttp`; add async HTTP request helper, response adapter helpers, async sleep hook, and synchronous wrapper.
- Modify `src/O4_Tile_Utils.py`: import `asyncio`; replace thread worker launch/join usage in `download_textures()` with `async_download_textures()`.
- Create `tests/test_imagery_async_downloads.py`: async HTTP and async texture scheduler tests.
- Modify `tests/test_imagery_failures.py`: adjust request exception test to use `aiohttp.ClientError` once the sync wrapper delegates to async HTTP.
- Modify `TODO.md`: mark TODO-030 completed after verification.

---

### Task 1: Add Async HTTP Tests

**Files:**
- Create: `tests/test_imagery_async_downloads.py`
- Modify: none

- [ ] **Step 1: Write the failing async HTTP tests**

Add these imports, fakes, and test cases to `tests/test_imagery_async_downloads.py`:

```python
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

        with mock.patch.object(IMG.asyncio, "to_thread", wraps=asyncio.to_thread) as to_thread:
            success, data, failure = asyncio.run(
                IMG.async_http_request_to_image(
                    256,
                    256,
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
                    256,
                    256,
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
                256,
                256,
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
        session = FakeAsyncSession([FakeAsyncResponse(404, {"Content-Type": "text/plain"})])

        success, data, failure = asyncio.run(
            IMG.async_http_request_to_image(
                256,
                256,
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
```

- [ ] **Step 2: Run the async HTTP tests to verify RED**

Run:

```powershell
uv run python -m unittest tests.test_imagery_async_downloads.AsyncHttpRequestTests -q
```

Expected: FAIL with `AttributeError: module 'O4_Imagery_Utils' has no attribute 'async_http_request_to_image'` or `ModuleNotFoundError: No module named 'aiohttp'` before the dependency is synced.

---

### Task 2: Add aiohttp Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Add dependency**

Add the runtime dependency in `pyproject.toml`:

```toml
dependencies = [
  "aiohttp>=3.13,<4",
  "numpy==2.4.4",
```

- [ ] **Step 2: Regenerate the lockfile**

Run:

```powershell
uv lock
```

Expected: exit 0 and `uv.lock` contains `name = "aiohttp"` plus its transitive dependencies.

- [ ] **Step 3: Re-run the RED test**

Run:

```powershell
uv run python -m unittest tests.test_imagery_async_downloads.AsyncHttpRequestTests -q
```

Expected: FAIL because `async_http_request_to_image` is not implemented yet.

---

### Task 3: Implement Async HTTP Request Helper

**Files:**
- Modify: `src/O4_Imagery_Utils.py`
- Test: `tests/test_imagery_async_downloads.py`
- Test: `tests/test_imagery_failures.py`

- [ ] **Step 1: Add imports and async sleep hook**

Near the top of `src/O4_Imagery_Utils.py`, add:

```python
import asyncio

import aiohttp
```

After the imagery retry configuration globals, add:

```python
async def async_request_sleep(delay):
    await asyncio.sleep(delay)
```

- [ ] **Step 2: Add async response helpers**

Place these helpers immediately before `http_request_to_image()`:

```python
def _response_status_code(response):
    return getattr(response, "status", getattr(response, "status_code", None))


async def _response_content(response):
    if hasattr(response, "read"):
        content = response.read()
        if hasattr(content, "__await__"):
            return await content
        return content
    return response.content


def _open_image_from_bytes(content):
    return Image.open(io.BytesIO(content))
```

- [ ] **Step 3: Implement the coroutine**

Replace the current body of `http_request_to_image()` with a call to the new
coroutine, and add this coroutine above it:

```python
async def async_http_request_to_image(
    width,
    height,
    url,
    request_headers,
    http_session,
):
    request_headers, request_context = IFAIL.split_request_headers(request_headers)
    UI.vprint(3, "HTTP request issued :", url, "\nRequest headers :", request_headers)
    tentative_request = 0
    tentative_image = 0
    status_code = None
    reason = "request_failed"

    while True:
        try:
            kwargs = {"timeout": http_timeout}
            if request_headers:
                kwargs["headers"] = request_headers
            async with http_session.get(url, **kwargs) as response:
                status_code = _response_status_code(response)
                status_text = IFAIL.response_status_text(response)
                headers = response.headers
                content = await _response_content(response)
            if ("Content-Length" in headers) and int(headers["Content-Length"]) <= 2521:
                if (headers["Content-Length"] == "1033") and ("virtualearth" in url):
                    UI.vprint(3, url, headers)
                    status_code = 404
                    reason = "provider_no_data_image"
                    break
                if (headers["Content-Length"] == "2521") and ("arcgisonline" in url):
                    UI.vprint(3, url, headers)
                    status_code = 404
                    reason = "provider_no_data_image"
                    break
            content_type = headers.get("Content-Type", "")
            if status_code == 200 and "image" in content_type:
                try:
                    small_image = await asyncio.to_thread(_open_image_from_bytes, content)
                    return (1, small_image, None)
                except (OSError, UnidentifiedImageError):
                    reason = "corrupted_image"
                    UI.vprint(
                        2,
                        "Server said 'OK', but the received ",
                        "image was corrupted.",
                    )
                    UI.vprint(3, url, headers)
            elif status_code == 404:
                reason = "not_found"
                UI.vprint(2, "Server said 'Not Found'")
                UI.vprint(3, url, headers)
                break
            elif status_code == 200:
                reason = "wrong_content_type"
                UI.vprint(2, "Server said 'OK' but sent us the wrong Content-Type.")
                UI.vprint(3, url, headers, content)
                break
            elif status_code == 403:
                reason = "forbidden"
                UI.vprint(2, "Server said 'Forbidden' ! (IP banned?)")
                UI.vprint(3, url, headers, content)
                break
            elif isinstance(status_code, int) and 500 <= status_code < 600:
                reason = "server_error"
                UI.vprint(2, "Server said 'Internal Error'.", status_text)
                if not check_tms_response:
                    break
                await async_request_sleep(2)
            else:
                reason = "unmanaged_status"
                UI.vprint(2, "Unmanaged Server answer:", status_text)
                UI.vprint(3, url, headers)
                break
            if UI.red_flag:
                return (0, "Stopped", None)
            tentative_image += 1
        except (aiohttp.ClientError, TimeoutError, OSError) as e:
            status_code = "connection_failure"
            reason = "connection_failure"
            UI.vprint(2, "Server could not be connected, retrying in 2 secs")
            UI.vprint(3, e)
            if not check_tms_response:
                break
            await async_request_sleep(2)
            if UI.red_flag:
                return (0, "Stopped", None)
            tentative_request += 1
        if (
            tentative_request == max_connect_retries
            or tentative_image == max_baddata_retries
        ):
            break
    failure = IFAIL.record_failure(
        url,
        status_code,
        tentative_request,
        tentative_image,
        reason,
        request_context,
    )
    if status_code == 404:
        return (0, "[404]", failure)
    return (0, str(status_code), failure)
```

- [ ] **Step 4: Implement the synchronous wrapper**

Use this body for `http_request_to_image()`:

```python
def http_request_to_image(
    width,
    height,
    url,
    request_headers,
    http_session=None,
):
    async def _run_request():
        if http_session is not None:
            return await async_http_request_to_image(
                width, height, url, request_headers, http_session
            )
        async with aiohttp.ClientSession() as session:
            return await async_http_request_to_image(
                width, height, url, request_headers, session
            )

    return asyncio.run(_run_request())
```

- [ ] **Step 5: Update the legacy request exception test**

In `tests/test_imagery_failures.py`, remove the `requests` import and change
the connection failure responses from `requests.exceptions.ConnectionError(...)`
to `aiohttp.ClientError(...)`. Patch `IMG.async_request_sleep` with an
`AsyncMock` instead of patching `IMG.time.sleep` and `IMG.requests.Session`.

- [ ] **Step 6: Run tests to verify GREEN**

Run:

```powershell
uv run python -m unittest tests.test_imagery_failures tests.test_imagery_async_downloads.AsyncHttpRequestTests -q
```

Expected: PASS.

---

### Task 4: Add Async Texture Scheduler Tests

**Files:**
- Modify: `tests/test_imagery_async_downloads.py`

- [ ] **Step 1: Add scheduler tests**

Append these tests to `tests/test_imagery_async_downloads.py`:

```python
import queue

import O4_Tile_Utils as TILE


class AsyncTextureDownloadTests(unittest.TestCase):
    def setUp(self):
        self.original_retries = TILE.max_texture_download_retries
        self.addCleanup(self._restore_state)
        TILE.max_texture_download_retries = 3

    def _restore_state(self):
        TILE.max_texture_download_retries = self.original_retries

    def test_async_download_textures_limits_concurrency_and_enqueues_conversions(self):
        active = 0
        max_active = 0
        lock = asyncio.Lock()
        convert_queue = queue.Queue()

        async def build(_tile, *_attrs):
            nonlocal active, max_active
            async with lock:
                active += 1
                max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            async with lock:
                active -= 1
            return 1

        download_queue = queue.Queue()
        download_queue.put((1, 2, 16, "BI"))
        download_queue.put((17, 18, 16, "BI"))
        download_queue.put((33, 34, 16, "BI"))

        with (
            mock.patch.object(TILE.IMG, "async_build_jpeg_ortho", side_effect=build),
            mock.patch.object(TILE.IMG, "imagery_download_summary", return_value=None),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = asyncio.run(
                TILE.async_download_textures(
                    self._tile(), download_queue, convert_queue, workers=2
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(max_active, 2)
        self.assertEqual(convert_queue.qsize(), 3)

    def test_async_download_textures_retries_and_summarizes_final_failures_once(self):
        TILE.max_texture_download_retries = 2
        calls = []
        summaries = []

        async def fail_build(_tile, *attrs):
            calls.append(attrs)
            return 0

        def summary(tile_coords, final_failures):
            summaries.append((tile_coords, final_failures))
            return None

        with (
            mock.patch.object(TILE.IMG, "async_build_jpeg_ortho", side_effect=fail_build),
            mock.patch.object(TILE.IMG, "imagery_download_summary", side_effect=summary),
            mock.patch.object(TILE.IMG, "failures_for_texture", return_value=[]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = asyncio.run(
                TILE.async_download_textures(
                    self._tile(), self._queue(), queue.Queue(), workers=2
                )
            )

        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(len(summaries[0][1]), 1)

    def _tile(self):
        return type("Tile", (), {"lat": 1, "lon": 2})()

    def _queue(self):
        download_queue = queue.Queue()
        download_queue.put((1, 2, 16, "BI"))
        return download_queue
```

- [ ] **Step 2: Run scheduler tests to verify RED**

Run:

```powershell
uv run python -m unittest tests.test_imagery_async_downloads.AsyncTextureDownloadTests -q
```

Expected: FAIL with `AttributeError` for missing `async_download_textures` or
`async_build_jpeg_ortho`.

---

### Task 5: Implement Async Texture Scheduler

**Files:**
- Modify: `src/O4_Imagery_Utils.py`
- Modify: `src/O4_Tile_Utils.py`
- Test: `tests/test_imagery_async_downloads.py`
- Test: `tests/test_imagery_failures.py`

- [ ] **Step 1: Add async build wrapper**

In `src/O4_Imagery_Utils.py`, after `build_jpeg_ortho()`, add:

```python
async def async_build_jpeg_ortho(tile, *attrs):
    return await asyncio.to_thread(build_jpeg_ortho, tile, *attrs)
```

- [ ] **Step 2: Replace thread imports**

In `src/O4_Tile_Utils.py`, add:

```python
import asyncio
```

Remove:

```python
from O4_Parallel_Utils import parallel_join, parallel_launch
```

- [ ] **Step 3: Add async scheduler**

Replace the internals of `download_textures()` with a synchronous wrapper that
calls this coroutine:

```python
async def async_download_textures(
    tile,
    download_queue,
    convert_queue,
    workers=None,
    producer_done_event=None,
):
    worker_count = max(1, workers or max_download_slots)
    UI.vprint(1, f"-> Opening download queue with {worker_count} worker(s).")

    progress_lock = asyncio.Lock()
    progress_state = {"done": 0, "pending": 0}
    attempts = defaultdict(int)
    final_failures = []
    interrupted = False
    max_attempts = max(1, int(max_texture_download_retries))
    semaphore = asyncio.Semaphore(worker_count)

    def _texture_failure_context(attrs):
        til_x_left, til_y_top, zoomlevel, provider_code = attrs
        file_name = FNAMES.jpeg_file_name_from_attributes(
            til_x_left, til_y_top, zoomlevel, provider_code
        )
        request_failures = IMG.failures_for_texture(file_name, provider_code)
        context = {
            "file_name": file_name,
            "provider_code": provider_code,
            "til_x_left": til_x_left,
            "til_y_top": til_y_top,
            "zoomlevel": zoomlevel,
            "status_code": "download_failed",
            "request_type": None,
        }
        if request_failures:
            last_failure = request_failures[-1]
            context.update(
                {
                    "status_code": last_failure.status_code,
                    "request_type": last_failure.request_type,
                    "url_type": last_failure.url_type,
                    "reason": last_failure.reason,
                }
            )
        return context

    def _update_progress_locked():
        denom = (
            progress_state["done"] + progress_state["pending"] + download_queue.qsize()
        )
        UI.progress_bar(2, int(100 * progress_state["done"] / denom) if denom else 100)

    async def _download_task(attrs):
        nonlocal interrupted
        if UI.red_flag:
            interrupted = True
            return 0
        async with semaphore:
            async with progress_lock:
                progress_state["pending"] += 1
                _update_progress_locked()
            try:
                ok = await IMG.async_build_jpeg_ortho(tile, *attrs)
            except Exception as err:
                UI.vprint(2, f"Download failed: {err}")
                ok = 0
            should_retry = False
            async with progress_lock:
                progress_state["pending"] -= 1
                if ok:
                    progress_state["done"] += 1
                    attempts.pop(attrs, None)
                else:
                    attempt = attempts[attrs] + 1
                    attempts[attrs] = attempt
                    should_retry = attempt < max_attempts and not UI.red_flag
                    if not should_retry:
                        final_failures.append(_texture_failure_context(attrs))
                        attempts.pop(attrs, None)
                _update_progress_locked()
            if ok:
                convert_queue.put((tile, *attrs))
            elif should_retry:
                download_queue.put(attrs)
                async with progress_lock:
                    _update_progress_locked()
            if UI.red_flag:
                interrupted = True
            return 1 if ok else 0

    if producer_done_event is None:
        producer_done_event = threading.Event()
        producer_done_event.set()

    tasks = set()
    while True:
        while not download_queue.empty() and not UI.red_flag:
            attrs = download_queue.get()
            if isinstance(attrs, str) and attrs == "quit":
                continue
            tasks.add(asyncio.create_task(_download_task(tuple(attrs))))
        if tasks:
            done, tasks = await asyncio.wait(tasks, timeout=0.05)
            for task in done:
                task.result()
        elif producer_done_event.is_set() or UI.red_flag:
            break
        else:
            await asyncio.sleep(0.05)
        if producer_done_event.is_set() and download_queue.empty() and not tasks:
            break

    if tasks:
        await asyncio.gather(*tasks)

    UI.progress_bar(2, 100)
    if interrupted or UI.red_flag:
        UI.vprint(1, "Download process interrupted.")
        return 0
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    summary = IMG.imagery_download_summary(tile_coords, final_failures)
    if summary:
        provider_counts = ", ".join(
            f"{provider}={count}"
            for provider, count in sorted(summary["by_provider"].items())
        )
        status_counts = ", ".join(
            f"{status}={count}" for status, count in sorted(summary["by_status"].items())
        )
        request_counts = ", ".join(
            f"{request_type}={count}"
            for request_type, count in sorted(summary["by_request_type"].items())
        )
        UI.vprint(
            1,
            "Imagery download summary:",
            f"{summary['total_textures']} incomplete or failed texture(s)",
            f"for tile {tile_coords}.",
            f"Providers: {provider_counts}.",
            f"Statuses: {status_counts}.",
            f"Request types: {request_counts}.",
        )
    if progress_state["done"]:
        UI.vprint(1, " *Download of textures completed.")
    return 1
```

- [ ] **Step 4: Keep synchronous wrapper**

Implement `download_textures()` as:

```python
def download_textures(
    tile,
    download_queue,
    convert_queue,
    workers=None,
    producer_done_event=None,
):
    return asyncio.run(
        async_download_textures(
            tile,
            download_queue,
            convert_queue,
            workers,
            producer_done_event,
        )
    )
```

- [ ] **Step 5: Run scheduler and legacy tests**

Run:

```powershell
uv run python -m unittest tests.test_imagery_failures tests.test_imagery_async_downloads -q
```

Expected: PASS.

---

### Task 6: Update TODO Tracking and GitHub Evidence

**Files:**
- Modify: `TODO.md`

- [ ] **Step 1: Mark TODO-030 done**

Update the TODO-030 block to:

```markdown
### TODO-030: aiohttp + asyncio Tile Downloads

Status: Done

GitHub Issue: #33

Completion note: implemented by adding `aiohttp`, moving imagery HTTP requests
behind `async_http_request_to_image()`, preserving the synchronous
`http_request_to_image()` wrapper, adding `async_download_textures()` with
`asyncio.gather()` and semaphore backpressure, and preserving retry/failure
summary behavior with deterministic async tests.
```

- [ ] **Step 2: Add issue evidence comment**

Run:

```powershell
gh issue comment 33 --repo tvproductions/Ortho4XP --body "Implemented TODO-030 with aiohttp-backed async imagery requests, async texture download scheduling, retry/failure preservation, and deterministic unittest coverage. Verification: focused imagery async/failure tests, full unittest discovery, Ruff, format check, ty on changed files, and quality-check --skip-native."
```

Expected: exit 0.

---

### Task 7: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run focused tests**

Run:

```powershell
uv run python -m unittest tests.test_imagery_failures tests.test_imagery_async_downloads -q
```

Expected: PASS.

- [ ] **Step 2: Run full unittest suite**

Run:

```powershell
uv run python -m unittest discover -s tests
```

Expected: PASS.

- [ ] **Step 3: Run Ruff check**

Run:

```powershell
uv run ruff check Ortho4XP.py src tests
```

Expected: PASS.

- [ ] **Step 4: Run Ruff format check**

Run:

```powershell
uv run ruff format --check .
```

Expected: PASS.

- [ ] **Step 5: Run ty on changed Python files**

Run:

```powershell
uv run ty check src/O4_Imagery_Utils.py src/O4_Tile_Utils.py tests/test_imagery_async_downloads.py tests/test_imagery_failures.py
```

Expected: PASS.

- [ ] **Step 6: Run Python quality gate**

Run:

```powershell
uv run python .codex/skills/quality-check/scripts/quality_check.py --skip-native
```

Expected: PASS.

- [ ] **Step 7: Inspect final diff**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; only intentional TODO-030 files changed.

