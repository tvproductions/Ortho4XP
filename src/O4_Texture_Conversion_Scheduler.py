import queue
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Callable

import O4_File_Names as FNAMES
import O4_Texture_Encoder as TEX
import O4_UI_Utils as UI


ConvertTexture = Callable[[object, int, int, int, str], object]


@dataclass(frozen=True)
class TextureConversionJob:
    tile: object
    til_x_left: int
    til_y_top: int
    zoomlevel: int
    provider_code: str

    @classmethod
    def from_queue_item(cls, item):
        tile, til_x_left, til_y_top, zoomlevel, provider_code = item
        return cls(tile, til_x_left, til_y_top, zoomlevel, provider_code)

    @property
    def display_name(self):
        return FNAMES.dds_file_name_from_attributes(
            self.til_x_left,
            self.til_y_top,
            self.zoomlevel,
            self.provider_code,
        )


@dataclass(frozen=True)
class TextureConversionBatchResult:
    completed: int
    failed: int
    interrupted: bool
    failures: tuple


def run_texture_conversion_queue(
    convert_queue,
    max_workers,
    *,
    convert_texture: ConvertTexture,
    progress_bar=3,
    poll_interval=0.05,
):
    worker_count = max(1, int(max_workers))
    active: dict[Future, TextureConversionJob] = {}
    completed = 0
    failures = []
    saw_quit = False
    interrupted = False

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        while not saw_quit or active:
            if UI.red_flag:
                interrupted = True
                saw_quit = True

            while not saw_quit and len(active) < worker_count:
                try:
                    item = _next_queue_item(
                        convert_queue,
                        has_active_futures=bool(active),
                        poll_interval=poll_interval,
                    )
                except queue.Empty:
                    break

                if item == "quit":
                    saw_quit = True
                    break
                if UI.red_flag:
                    interrupted = True
                    saw_quit = True
                    break

                job = TextureConversionJob.from_queue_item(item)
                active[executor.submit(_run_job, job, convert_texture)] = job

            if not active:
                if saw_quit:
                    break
                time.sleep(poll_interval)
                continue

            done, _pending = wait(
                active,
                timeout=poll_interval,
                return_when=FIRST_COMPLETED,
            )
            for future in done:
                job = active.pop(future)
                result = future.result()
                completed += 1
                if not result.ok:
                    failures.append(result)
                _update_progress(
                    progress_bar,
                    completed,
                    len(active) + _queued_job_count(convert_queue),
                )

    UI.progress_bar(progress_bar, 100)
    return TextureConversionBatchResult(
        completed=completed,
        failed=len(failures),
        interrupted=interrupted or UI.red_flag,
        failures=tuple(failures),
    )


def _next_queue_item(convert_queue, *, has_active_futures, poll_interval):
    if has_active_futures:
        return convert_queue.get_nowait()
    return convert_queue.get(timeout=poll_interval)


def _run_job(job: TextureConversionJob, convert_texture: ConvertTexture):
    try:
        result = convert_texture(
            job.tile,
            job.til_x_left,
            job.til_y_top,
            job.zoomlevel,
            job.provider_code,
        )
        return TEX.coerce_conversion_result(
            result,
            job.display_name,
            job.provider_code,
        )
    except Exception as exc:
        return TEX.TextureConversionResult.failure(
            job.display_name,
            job.provider_code,
            str(exc),
        )


def _update_progress(progress_bar, completed, remaining):
    total = completed + remaining
    if total <= 0:
        return
    UI.progress_bar(progress_bar, int(100 * completed / total))


def _queued_job_count(convert_queue):
    try:
        return max(0, convert_queue.qsize())
    except NotImplementedError:
        return 0
