"""Small named-step pipeline runner for build orchestration.

The module keeps pipeline mechanics separate from tile-build policy:
`Pipeline` knows how to run named callables, track status/timing, publish
`PIPELINE_STEP` events, and stop on failure. Callers keep ownership of domain
events, result objects, and recovery behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter
from typing import Any

import O4_Event_Bus as EVENTS
import O4_UI_Utils as UI


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass(frozen=True)
class StepOutcome:
    ok: bool = True
    message: str = ""


@dataclass
class StepState:
    name: str
    status: StepStatus = StepStatus.PENDING
    duration_seconds: float | None = None
    message: str = ""


@dataclass(frozen=True)
class PipelineResult:
    ok: bool
    steps: tuple[StepState, ...]
    failed_step: str | None = None
    message: str = ""


StepAction = Callable[[], StepOutcome | bool | None]
StepCompleteCallback = Callable[[StepState, int, int], None]


@dataclass(frozen=True)
class _Step:
    state: StepState
    action: StepAction


class Pipeline:
    """Run ordered named steps with status, timing, and event publication."""

    def __init__(
        self,
        name: str,
        *,
        event_payload: Mapping[str, Any] | None = None,
        on_step_complete: StepCompleteCallback | None = None,
    ) -> None:
        self.name = name
        self._event_payload = dict(event_payload or {})
        self._on_step_complete = on_step_complete
        self._steps: list[_Step] = []

    def add_step(self, name: str, action: StepAction) -> None:
        self._steps.append(_Step(StepState(name), action))

    def run(self) -> PipelineResult:
        total_steps = len(self._steps)
        for completed_steps, step in enumerate(self._steps, start=1):
            result = self._run_step_and_report(step, completed_steps, total_steps)
            if result is not None:
                return result
        return PipelineResult(True, self._states())

    def _run_step_and_report(
        self, step: _Step, completed_steps: int, total_steps: int
    ) -> PipelineResult | None:
        outcome = self._run_step(step)
        if not outcome.ok:
            return PipelineResult(
                False,
                self._states(),
                failed_step=step.state.name,
                message=outcome.message,
            )
        if self._on_step_complete is not None:
            self._on_step_complete(step.state, completed_steps, total_steps)
        return None

    def _run_step(self, step: _Step) -> StepOutcome:
        step.state.status = StepStatus.RUNNING
        step.state.message = ""
        self._publish_step(step.state)
        start = perf_counter()
        outcome = self._call_step(step)
        step.state.duration_seconds = perf_counter() - start
        self._finish_step(step.state, outcome)
        self._publish_step(step.state)
        return outcome

    def _call_step(self, step: _Step) -> StepOutcome:
        try:
            return _step_outcome(step.action())
        except Exception as exc:
            UI.log_exception(
                exc,
                context={"pipeline": self.name, "step": step.state.name},
            )
            return StepOutcome(False, str(exc))

    def _finish_step(self, state: StepState, outcome: StepOutcome) -> None:
        if outcome.ok:
            state.status = StepStatus.COMPLETE
        else:
            state.status = StepStatus.ERROR
            state.message = outcome.message

    def _publish_step(self, state: StepState) -> None:
        payload = {
            **self._event_payload,
            "pipeline": self.name,
            "step": state.name,
            "status": state.status.value,
        }
        if state.message:
            payload["message"] = state.message
        if state.duration_seconds is not None:
            payload["duration_seconds"] = state.duration_seconds
        EVENTS.publish(EVENTS.EventName.PIPELINE_STEP, **payload)

    def _states(self) -> tuple[StepState, ...]:
        return tuple(step.state for step in self._steps)


def _step_outcome(value: StepOutcome | bool | None) -> StepOutcome:
    if isinstance(value, StepOutcome):
        return value
    if value is False:
        return StepOutcome(False, "failed")
    return StepOutcome(True)
