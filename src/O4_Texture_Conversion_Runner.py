import queue
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field

import O4_Texture_Conversion_Scheduler as TCS
import O4_Texture_Encoder as TEX


# Queue runner invariants:
# - The scheduler facade owns public types and UI monkeypatching.
# - The runner owns executor lifetime and mutable queue state.
# - "quit" only stops intake; active futures are always drained.
# - Red-flag interruption prevents new work and reports an interrupted batch.
# - Progress is based on completed work plus active and queued jobs.
# - Worker exceptions become failed texture results, not thread crashes.
# - The queue can be live-fed while the DSF producer is still running.
# - Polling is short and injectable so tests can prove live progress behavior.
# - Future GPU backends can reuse the same bounded scheduling contract.
# - Result aggregation stays provider-aware for concise Step 3 summaries.
@dataclass
class TextureConversionQueueRunner:
    convert_queue: TCS.TextureConversionQueue
    max_workers: int
    convert_texture: TCS.ConvertTexture
    options: TCS.TextureConversionSchedulerOptions
    active: dict[Future, TCS.TextureConversionJob] = field(
        init=False,
        default_factory=dict,
    )
    completed: int = field(init=False, default=0)
    failures: list = field(init=False, default_factory=list)
    interrupted: bool = field(init=False, default=False)
    saw_quit: bool = field(init=False, default=False)

    def __post_init__(self):
        self.worker_count = max(1, int(self.max_workers))

    def run(self):
        with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
            while not self.saw_quit or self.active:
                self._stop_if_interrupted()
                self._schedule_available_jobs(executor)
                if self.active:
                    self._drain_completed_jobs()
                elif not self.saw_quit:
                    time.sleep(self.options.poll_interval)

        TCS.UI.progress_bar(self.options.progress_bar, 100)
        return TCS.TextureConversionBatchResult(
            self.completed,
            len(self.failures),
            self.interrupted or TCS.UI.red_flag,
            tuple(self.failures),
        )

    def _stop_if_interrupted(self):
        if TCS.UI.red_flag:
            self.interrupted = True
            self.saw_quit = True

    def _schedule_available_jobs(self, executor):
        while not self.saw_quit and len(self.active) < self.worker_count:
            job = self._next_job()
            if job is None:
                return
            self._submit_job(executor, job)

    def _next_queue_item(self):
        if self.active:
            return self.convert_queue.get_nowait()
        return self.convert_queue.get(timeout=self.options.poll_interval)

    def _next_job(self):
        try:
            item = self._next_queue_item()
        except queue.Empty:
            return None
        if item == "quit":
            self.saw_quit = True
            return None
        if TCS.UI.red_flag:
            self._stop_if_interrupted()
            return None
        return TCS.TextureConversionJob.from_queue_item(item)

    def _submit_job(self, executor, job):
        self.active[executor.submit(_run_job, job, self.convert_texture)] = job

    def _drain_completed_jobs(self):
        done, _pending = wait(
            self.active,
            timeout=self.options.poll_interval,
            return_when=FIRST_COMPLETED,
        )
        for future in done:
            self._record_completed_job(future)

    def _record_completed_job(self, future):
        self.active.pop(future)
        result = future.result()
        self.completed += 1
        if not result.ok:
            self.failures.append(result)
        _update_progress(
            self.options.progress_bar,
            self.completed,
            len(self.active) + _queued_job_count(self.convert_queue),
        )


def _run_job(job: TCS.TextureConversionJob, convert_texture: TCS.ConvertTexture):
    try:
        if job.source is not None:
            result = convert_texture(
                job.tile,
                job.til_x_left,
                job.til_y_top,
                job.zoomlevel,
                job.provider_code,
                texture_source=job.source,
            )
        else:
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
            job.display_name, job.provider_code, str(exc)
        )


def _update_progress(progress_bar, completed, remaining):
    total = completed + remaining
    if total <= 0:
        return
    TCS.UI.progress_bar(progress_bar, int(100 * completed / total))


def _queued_job_count(convert_queue):
    try:
        return max(0, convert_queue.qsize())
    except NotImplementedError:
        return 0
