"""Build-facing adapter helpers for the generic pipeline runner."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import O4_Pipeline as PIPELINE

StepCompleteCallback = Callable[[PIPELINE.StepState, int, int], None]


@dataclass(frozen=True)
class BuildPipelineSpec[T]:
    mode: str
    steps: Iterable[tuple[str, T]]
    run_step: Callable[[T], PIPELINE.StepOutcome]
    on_step_complete: StepCompleteCallback


def run_named_steps[T](
    tile,
    spec: BuildPipelineSpec[T],
) -> PIPELINE.PipelineResult:
    pipeline = PIPELINE.Pipeline(
        spec.mode,
        event_payload=tile_event_payload(tile, mode=spec.mode),
        on_step_complete=spec.on_step_complete,
    )
    for name, step_value in spec.steps:
        pipeline.add_step(name, lambda step_value=step_value: spec.run_step(step_value))
    return pipeline.run()


def tile_event_payload(tile, *, mode: str) -> dict[str, object]:
    return {"lat": tile.lat, "lon": tile.lon, "mode": mode}
