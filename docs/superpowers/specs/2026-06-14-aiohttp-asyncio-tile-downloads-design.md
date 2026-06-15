# TODO-030 aiohttp + asyncio Tile Downloads Design

## Context

TODO-030 replaces the current `requests`-based imagery download path with
`aiohttp` and `asyncio`. The current implementation has two coupled surfaces:

- `src/O4_Imagery_Utils.py` owns provider request construction, HTTP response
  classification, image decoding, and imagery failure records.
- `src/O4_Tile_Utils.py` owns the texture download queue, configured texture
  retry limits, progress reporting, conversion queue handoff, and final imagery
  failure summaries.

The change must preserve the existing synchronous callers while moving the
network I/O and texture download worker execution to async primitives.

## Goals

- Add `aiohttp` as a runtime dependency.
- Use `aiohttp.ClientSession` for tile HTTP requests.
- Keep the public `http_request_to_image()` call compatible for existing WMS,
  WMTS, TMS, and tests.
- Add an async request implementation that performs CPU-bound Pillow image
  decoding through `asyncio.to_thread()`.
- Replace the threaded texture download worker loop with an async scheduler that
  uses `asyncio.gather()` and semaphore backpressure.
- Preserve imagery failure reasons, retry counters, final summary behavior,
  progress reporting, interruption handling, and conversion queue handoff.
- Add deterministic `unittest` coverage for async request and scheduler
  behavior.

## Non-Goals

- Do not rewrite provider URL construction.
- Do not change generated texture filenames, cache locations, or conversion
  queue payloads.
- Do not change DEM, OSM, mesh, or native encoder network paths that still use
  `requests`.
- Do not introduce network-dependent tests.

## Architecture

`O4_Imagery_Utils.py` will expose a coroutine for the new HTTP path and keep the
existing synchronous wrapper:

- `async_http_request_to_image(...)` performs the `aiohttp` request loop,
  response classification, retry sleeps, failure recording, and image decode.
- `http_request_to_image(...)` runs the coroutine for current synchronous
  callers. Existing call sites keep their tuple contract:
  `(success, image_or_status, failure_or_none)`.

The async implementation will use a small response adapter so tests can supply
deterministic fake async sessions without real network access. The adapter will
normalize `status`, `headers`, and `content` access across real `aiohttp`
responses and test fakes.

`O4_Tile_Utils.py` will keep the public `download_textures(...)` function and
delegate to an async scheduler:

- `async_download_textures(...)` drains the existing producer queue without
  changing DSF producer behavior.
- A semaphore bounds concurrent `IMG.build_jpeg_ortho(...)` calls to
  `worker_count`.
- Each texture attribute tuple is retried up to
  `max_texture_download_retries`.
- Successful downloads enqueue `(tile, *attrs)` onto `convert_queue`.
- Failed downloads contribute exactly one final failure context.
- The synchronous `download_textures(...)` wrapper runs the coroutine so the
  current build thread can still target it.

## Error Handling

The async HTTP path must preserve the existing failure model:

- `404` records `not_found` and returns `[404]`.
- `403` records `forbidden`.
- `5xx` records `server_error`, retrying only when `check_tms_response` allows.
- `200` with non-image content records `wrong_content_type`.
- `200` with undecodable image bytes records `corrupted_image`.
- `aiohttp.ClientError`, timeout errors, and low-level OS connection errors
  record `connection_failure`.
- Provider-specific no-data images keep the current `Content-Length` handling.
- `UI.red_flag` stops retry loops and download scheduling.

## Testing

Tests will be written first with `unittest`:

- Async HTTP tests will use fake async sessions and responses to prove success,
  corrupted image retry, connection retry, and sanitized failure recording.
- Texture scheduler tests will prove semaphore-bounded async execution, retry
  limits, one-time final summaries, successful retry exclusion from final
  failures, and conversion queue handoff.
- Existing imagery failure tests remain valid through the synchronous wrapper.

Verification commands:

- `uv run python -m unittest tests.test_imagery_failures tests.test_imagery_async_downloads -q`
- `uv run python -m unittest discover -s tests`
- `uv run ruff check Ortho4XP.py src tests`
- `uv run ruff format --check .`
- `uv run ty check src/O4_Imagery_Utils.py src/O4_Tile_Utils.py`
- `uv run python .codex/skills/quality-check/scripts/quality_check.py --skip-native`

## Tracking

GitHub Issue: #33
