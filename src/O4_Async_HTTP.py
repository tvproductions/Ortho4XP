import asyncio
import io
from dataclasses import dataclass
from typing import Any

import aiohttp
from PIL import Image, UnidentifiedImageError

import O4_Imagery_Failures as IFAIL
import O4_UI_Utils as UI


@dataclass
class AsyncHttpConfig:
    timeout: float
    check_response: bool
    max_connect_retries: int
    max_baddata_retries: int
    sleep: Any


@dataclass
class AsyncHttpRequestState:
    request_context: dict[str, Any]
    tentative_request: int = 0
    tentative_image: int = 0
    status_code: Any = None
    reason: str = "request_failed"


@dataclass
class AsyncHttpRuntime:
    state: AsyncHttpRequestState
    http_session: Any
    url: str
    request_headers: Any
    config: AsyncHttpConfig


@dataclass
class AsyncHttpResponseData:
    status_code: Any
    status_text: str
    headers: Any
    content: bytes
    url: str


@dataclass
class AsyncHttpAttemptResult:
    done: bool = False
    success: bool = False
    data: Any = None
    reason: str = "request_failed"
    retry_bad_data: bool = False
    retry_delay: float | None = None
    status_code: Any = None


async def async_request_sleep(delay):
    await asyncio.sleep(delay)


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


async def _read_http_response(http_session, url, request_headers, config):
    kwargs = {"timeout": config.timeout}
    if request_headers:
        kwargs["headers"] = request_headers
    response_context = http_session.get(url, **kwargs)
    if hasattr(response_context, "__aenter__"):
        async with response_context as response:
            return await _response_data(response, url)
    return await _response_data(response_context, url)


async def _response_data(response, url):
    return AsyncHttpResponseData(
        status_code=_response_status_code(response),
        status_text=IFAIL.response_status_text(response),
        headers=response.headers,
        content=await _response_content(response),
        url=url,
    )


def _provider_no_data_status(data):
    headers = data.headers
    if "Content-Length" not in headers or int(headers["Content-Length"]) > 2521:
        return None
    if headers["Content-Length"] == "1033" and "virtualearth" in data.url:
        return 404
    if headers["Content-Length"] == "2521" and "arcgisonline" in data.url:
        return 404
    return None


async def _decode_image_response(data):
    try:
        small_image = await asyncio.to_thread(_open_image_from_bytes, data.content)
        return AsyncHttpAttemptResult(done=True, success=True, data=small_image)
    except (OSError, UnidentifiedImageError):
        UI.vprint(
            2,
            "Server said 'OK', but the received ",
            "image was corrupted.",
        )
        UI.vprint(3, data.url, data.headers)
        return AsyncHttpAttemptResult(reason="corrupted_image", retry_bad_data=True)


async def _classify_http_response(data, config):
    no_data_status = _provider_no_data_status(data)
    if no_data_status is not None:
        UI.vprint(3, data.url, data.headers)
        return AsyncHttpAttemptResult(
            done=True,
            reason="provider_no_data_image",
            status_code=no_data_status,
        )
    content_type = data.headers.get("Content-Type", "")
    if data.status_code == 200 and "image" in content_type:
        return await _decode_image_response(data)
    return _classify_non_image_response(data, config)


def _classify_non_image_response(data, config):
    if data.status_code == 404:
        UI.vprint(2, "Server said 'Not Found'")
        UI.vprint(3, data.url, data.headers)
        return AsyncHttpAttemptResult(done=True, reason="not_found")
    if data.status_code == 200:
        UI.vprint(2, "Server said 'OK' but sent us the wrong Content-Type.")
        UI.vprint(3, data.url, data.headers, data.content)
        return AsyncHttpAttemptResult(done=True, reason="wrong_content_type")
    if data.status_code == 403:
        UI.vprint(2, "Server said 'Forbidden' ! (IP banned?)")
        UI.vprint(3, data.url, data.headers, data.content)
        return AsyncHttpAttemptResult(done=True, reason="forbidden")
    return _classify_other_response(data, config)


def _classify_other_response(data, config):
    if isinstance(data.status_code, int) and 500 <= data.status_code < 600:
        UI.vprint(2, "Server said 'Internal Error'.", data.status_text)
        return AsyncHttpAttemptResult(
            done=not config.check_response,
            reason="server_error",
            retry_delay=2 if config.check_response else None,
        )
    UI.vprint(2, "Unmanaged Server answer:", data.status_text)
    UI.vprint(3, data.url, data.headers)
    return AsyncHttpAttemptResult(done=True, reason="unmanaged_status")


def _failure_payload(status_code):
    if status_code == 404:
        return "[404]"
    return str(status_code)


def _retry_limits_reached(state, config):
    return (
        state.tentative_request >= config.max_connect_retries
        or state.tentative_image >= config.max_baddata_retries
    )


async def _handle_connection_failure(state, error, config):
    state.status_code = "connection_failure"
    state.reason = "connection_failure"
    UI.vprint(2, "Server could not be connected, retrying in 2 secs")
    UI.vprint(3, error)
    if not config.check_response:
        return False
    await config.sleep(2)
    if UI.red_flag:
        return False
    state.tentative_request += 1
    return True


async def _next_attempt(runtime):
    try:
        data = await _read_http_response(
            runtime.http_session,
            runtime.url,
            runtime.request_headers,
            runtime.config,
        )
        runtime.state.status_code = data.status_code
        result = await _classify_http_response(data, runtime.config)
        _apply_attempt_result(runtime.state, result)
        return result
    except (aiohttp.ClientError, TimeoutError, OSError) as exc:
        can_continue = await _handle_connection_failure(
            runtime.state, exc, runtime.config
        )
        return AsyncHttpAttemptResult(done=not can_continue)


def _apply_attempt_result(state, result):
    state.reason = result.reason
    if result.status_code is not None:
        state.status_code = result.status_code
    if result.retry_bad_data:
        state.tentative_image += 1


async def async_http_request_to_image(url, request_headers, http_session, config):
    request_headers, request_context = IFAIL.split_request_headers(request_headers)
    UI.vprint(3, "HTTP request issued :", url, "\nRequest headers :", request_headers)
    state = AsyncHttpRequestState(request_context)
    runtime = AsyncHttpRuntime(state, http_session, url, request_headers, config)
    result = await _run_request_loop(runtime)
    if result.success:
        return (1, result.data, None)
    if result.data == "Stopped":
        return (0, "Stopped", None)
    failure = IFAIL.record_failure(
        url,
        state.status_code,
        state.tentative_request,
        state.tentative_image,
        state.reason,
        state.request_context,
    )
    return (0, _failure_payload(state.status_code), failure)


async def _run_request_loop(runtime):
    while True:
        result = await _next_attempt(runtime)
        if await _request_loop_done(runtime, result):
            return result


async def _request_loop_done(runtime, result):
    if result.success or result.done:
        return True
    if result.retry_delay is not None:
        await runtime.config.sleep(result.retry_delay)
    if UI.red_flag:
        result.data = "Stopped"
        return True
    return _retry_limits_reached(runtime.state, runtime.config)
