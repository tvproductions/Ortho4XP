import asyncio
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Provider_Failover as FAILOVER
import O4_Texture_Download_Failover as TDF
import O4_UI_Utils as UI

# Download requests retain two identities: the originally requested terrain
# texture and the provider currently selected by failover. Scheduler retries
# may change only the active identity; conversion and finalization still need
# the original identity to rewrite terrain references deterministically.
#
from O4_Texture_Source import TextureBuildResult


@dataclass
class DownloadTextureOptions:
    max_download_slots: int
    max_texture_download_retries: int
    workers: int | None = None
    producer_done_event: Any = None


@dataclass
class DownloadTextureState:
    progress_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    progress: dict[str, int] = field(default_factory=lambda: {"done": 0, "pending": 0})
    attempts: Any = field(default_factory=lambda: defaultdict(int))
    final_failures: list[dict[str, Any]] = field(default_factory=list)
    interrupted: bool = False


@dataclass(frozen=True)
class TextureDownloadRequest:
    requested_attrs: tuple
    active_attrs: tuple

    def __post_init__(self):
        object.__setattr__(self, "requested_attrs", tuple(self.requested_attrs))
        object.__setattr__(self, "active_attrs", tuple(self.active_attrs))

    @classmethod
    def initial(cls, attrs):
        attrs = tuple(attrs)
        return cls(attrs, attrs)

    def with_active_attrs(self, attrs):
        return TextureDownloadRequest(self.requested_attrs, tuple(attrs))


@dataclass
class DownloadTextureRuntime:
    tile: Any
    download_queue: Any
    convert_queue: Any
    semaphore: asyncio.Semaphore
    state: DownloadTextureState
    max_attempts: int
    failover_registry: Any = FAILOVER.default_registry
    provider_extent_resolver: Any = IMG.provider_uses_explicit_extent


def _worker_count(options):
    return max(1, options.workers or options.max_download_slots)


def _producer_done_event(options):
    if options.producer_done_event is not None:
        return options.producer_done_event
    producer_done_event = threading.Event()
    producer_done_event.set()
    return producer_done_event


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


def _update_progress(runtime):
    progress = runtime.state.progress
    denom = progress["done"] + progress["pending"] + runtime.download_queue.qsize()
    UI.progress_bar(2, int(100 * progress["done"] / denom) if denom else 100)


async def _mark_download_started(runtime):
    async with runtime.state.progress_lock:
        runtime.state.progress["pending"] += 1
        _update_progress(runtime)


async def _record_download_result(runtime, request, result):
    async with runtime.state.progress_lock:
        runtime.state.progress["pending"] -= 1
        if result.ok:
            retry_request = TDF.record_successful_download(runtime, request, result)
        else:
            retry_request = TDF.record_failed_download(
                runtime, request, IMG.providers_dict, _texture_failure_context
            )
        _update_progress(runtime)
    return retry_request


async def _build_texture(runtime, attrs):
    try:
        return await IMG.async_build_texture_source(runtime.tile, *attrs)
    except Exception as err:
        UI.vprint(2, f"Download failed: {err}")
        return TextureBuildResult.failure(tuple(attrs), str(err))


async def _download_task(runtime, request):
    if UI.red_flag:
        runtime.state.interrupted = True
        return 0
    async with runtime.semaphore:
        await _mark_download_started(runtime)
        result = await _build_texture(runtime, request.active_attrs)
        retry_request = await _record_download_result(runtime, request, result)
        await _queue_download_result(runtime, request, result, retry_request)
        if UI.red_flag:
            runtime.state.interrupted = True
        return 1 if result.ok else 0


async def _queue_download_result(runtime, request, result, retry_request):
    if result.ok and result.source is not None:
        source = result.source.with_requested_attrs(request.requested_attrs)
        runtime.convert_queue.put((runtime.tile, source))
    elif retry_request is not None:
        runtime.download_queue.put(retry_request)
        async with runtime.state.progress_lock:
            _update_progress(runtime)


async def _run_ready_tasks(runtime, tasks):
    while not runtime.download_queue.empty() and not UI.red_flag:
        queue_item = runtime.download_queue.get()
        if isinstance(queue_item, str) and queue_item == "quit":
            continue
        request = _download_request(queue_item)
        active_request = TDF.active_request(runtime, request, IMG.providers_dict)
        tasks.add(asyncio.create_task(_download_task(runtime, active_request)))
    return tasks


def _download_request(queue_item):
    """Preserve an existing request identity or initialize one from legacy input."""
    if isinstance(queue_item, TextureDownloadRequest):
        return queue_item
    return TextureDownloadRequest.initial(queue_item)


async def _collect_completed_tasks(tasks):
    if not tasks:
        return tasks
    done, pending_tasks = await asyncio.wait(tasks, timeout=0.05)
    for task in done:
        task.result()
    return pending_tasks


async def _wait_for_downloads(runtime, producer_done_event):
    tasks = set()
    while True:
        tasks = await _run_ready_tasks(runtime, tasks)
        tasks = await _collect_completed_tasks(tasks)
        if await _download_loop_done(runtime, producer_done_event, tasks):
            break
    if tasks:
        await asyncio.gather(*tasks)


async def _download_loop_done(runtime, producer_done_event, tasks):
    if _downloads_complete(runtime, producer_done_event, tasks) or UI.red_flag:
        return True
    await _wait_for_more_work(runtime, tasks)
    return False


def _downloads_complete(runtime, producer_done_event, tasks):
    return producer_done_event.is_set() and runtime.download_queue.empty() and not tasks


async def _wait_for_more_work(runtime, tasks):
    if not tasks and runtime.download_queue.empty():
        await asyncio.sleep(0.05)


def _sorted_counts(counts):
    return ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))


def _print_summary(tile, final_failures):
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    summary = IMG.imagery_download_summary(tile_coords, final_failures)
    if not summary:
        return
    provider_counts = _sorted_counts(summary["by_provider"])
    status_counts = _sorted_counts(summary["by_status"])
    request_counts = _sorted_counts(summary["by_request_type"])
    UI.vprint(
        1,
        "Imagery download summary:",
        f"{summary['total_textures']} incomplete or failed texture(s)",
        f"for tile {tile_coords}.",
        f"Providers: {provider_counts}.",
        f"Statuses: {status_counts}.",
        f"Request types: {request_counts}.",
    )


async def async_download_textures(tile, download_queue, convert_queue, options):
    worker_count = _worker_count(options)
    UI.vprint(1, f"-> Opening download queue with {worker_count} worker(s).")
    runtime = DownloadTextureRuntime(
        tile=tile,
        download_queue=download_queue,
        convert_queue=convert_queue,
        semaphore=asyncio.Semaphore(worker_count),
        state=DownloadTextureState(),
        max_attempts=max(1, int(options.max_texture_download_retries)),
    )
    await _wait_for_downloads(runtime, _producer_done_event(options))
    UI.progress_bar(2, 100)
    if runtime.state.interrupted or UI.red_flag:
        UI.vprint(1, "Download process interrupted.")
        return 0
    _print_summary(tile, runtime.state.final_failures)
    if runtime.state.progress["done"]:
        UI.vprint(1, " *Download of textures completed.")
    return 1
