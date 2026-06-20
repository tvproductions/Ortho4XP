# TODO-036 Event Bus Design

Date: 2026-06-20
Backlog: TODO-036
GitHub Issue: #36

## 1. Purpose & Scope

Add a small event infrastructure layer that lets build surfaces publish
machine-readable lifecycle events without changing current CLI or GUI behavior.
This is an infrastructure-first implementation: subscribers may observe events,
but no user-facing workflow should depend on the event bus yet.

Scope covers:

- A thread-safe singleton event bus.
- Typed event names for the TODO-036 contract.
- Build-pipeline event emission from existing all-in-one and batch build
  boundaries.
- Deterministic `unittest` coverage for event bus behavior and emitted build
  event order.

This work deliberately avoids a new pipeline engine, GUI progress rewrite, cache
implementation, or required logging subscriber. Those belong to later backlog
items.

## 2. Event Model

Create `src/O4_Event_Bus.py` as the single event infrastructure module.

Key interface:

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable


class EventName(StrEnum):
    TILE_START = "TILE_START"
    TILE_PROGRESS = "TILE_PROGRESS"
    TILE_COMPLETE = "TILE_COMPLETE"
    TILE_ERROR = "TILE_ERROR"
    PIPELINE_STEP = "PIPELINE_STEP"
    CACHE_HIT = "CACHE_HIT"


@dataclass(frozen=True)
class Event:
    name: EventName
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)


EventHandler = Callable[[Event], None]
Unsubscribe = Callable[[], None]


class EventBus:
    def subscribe(self, name: EventName | str, handler: EventHandler) -> Unsubscribe
    def publish(self, name: EventName | str, **payload: Any) -> Event
    def clear(self) -> None


def event_bus() -> EventBus
def publish(name: EventName | str, **payload: Any) -> Event
def subscribe(name: EventName | str, handler: EventHandler) -> Unsubscribe
```

`EventName` is a `StrEnum` because Python 3.13 is required and string-compatible
values make logs, tests, and future JSON serialization straightforward.

## 3. Thread Safety

`EventBus` owns a dictionary mapping `EventName` to an ordered tuple or list of
handlers. It protects registry reads and writes with `threading.RLock`.

Publishing follows this sequence:

1. Normalize `name` to `EventName`.
2. Build an `Event` with `datetime.now(UTC)`.
3. Lock the registry and copy the current handlers for that event name.
4. Release the lock.
5. Invoke handlers in subscription order.
6. Return the `Event` object to the publisher.

Handlers run outside the lock so a handler can subscribe or unsubscribe without
deadlocking the bus. A handler added during a publish call does not receive the
already-in-flight event. A handler removed during a publish call may still
receive that in-flight event if it was in the snapshot.

## 4. Subscriber Error Handling

Subscriber exceptions must not break tile builds. `EventBus.publish()` catches
`Exception` from each handler, logs the failure through
`O4_UI_Utils.log_exception()`, and continues invoking remaining handlers.

The logged message should identify the event name and handler representation:

```python
UI.log_exception(
    exc,
    context={
        "event_name": event.name.value,
        "handler": repr(handler),
    },
)
```

The event bus should not swallow `BaseException` subclasses such as
`KeyboardInterrupt` or `SystemExit`.

## 5. Build Integration

Modify `src/O4_Build_Core.py` only at existing build boundaries.

### 5.1 All-in-one build

`build_tile_all(tile)` publishes:

| Event | Timing | Payload |
| --- | --- | --- |
| `TILE_START` | Immediately after context creation | `lat`, `lon`, `mode="all"` |
| `PIPELINE_STEP` | Before each step | `lat`, `lon`, `step`, `status="start"`, `mode="all"` |
| `PIPELINE_STEP` | After each step returns without interruption | `lat`, `lon`, `step`, `status="complete"`, `mode="all"` |
| `TILE_PROGRESS` | After each completed step | `lat`, `lon`, `completed_steps`, `total_steps`, `mode="all"` |
| `TILE_ERROR` | If `ctx.red_flag` interrupts a step or retry | `lat`, `lon`, `step`, `message="interrupted"`, `mode="all"` |
| `TILE_COMPLETE` | After retry handling and incomplete texture reporting | `lat`, `lon`, `step="all"`, `mode="all"` |

The retry path is instrumented as `step="retry"` for error reporting only. It
does not become a normal pipeline step because retry is conditional recovery
inside the current all-in-one behavior.

### 5.2 Batch build

`build_batch(plan, on_tile_complete=None)` and `_build_tile_plan(tile_plan, ctx)`
publish the same event names using `mode="batch"`.

Selected steps come from `tile_plan.steps`; progress counts only selected steps.
For a falsey build step result, `_build_tile_plan()` publishes:

```python
TILE_ERROR(
    lat=tile_plan.lat,
    lon=tile_plan.lon,
    step=step,
    message=f"{step} failed",
    mode="batch",
)
```

The existing `on_tile_complete` callback remains unchanged and continues to
receive only `BuildTileResult` objects.

### 5.3 Cache events

`CACHE_HIT` is defined now but not emitted by TODO-036. Smart cache behavior is
TODO-038, and emitting cache events before the cache exists would create
misleading behavior.

## 6. Helper Functions

Keep `O4_Build_Core.py` integration readable by adding local helper functions
instead of scattering event payload assembly:

```python
def _tile_event_payload(tile, *, mode: str) -> dict[str, object]
def _publish_tile_start(tile, *, mode: str) -> None
def _publish_tile_complete(tile, *, mode: str, step: str = "all") -> None
def _publish_tile_error(tile, *, mode: str, step: str, message: str) -> None
def _publish_step(tile, *, mode: str, step: str, status: str) -> None
def _publish_progress(
    tile,
    *,
    mode: str,
    completed_steps: int,
    total_steps: int,
) -> None
```

These helpers call `O4_Event_Bus.publish()` and do not return values. They keep
the current `BuildResult` and `BuildTileResult` contracts intact.

## 7. Testing Strategy

Use `unittest` only.

### 7.1 `tests/test_event_bus.py`

Cover event infrastructure behavior:

- `subscribe()` receives events in subscription order.
- The returned unsubscribe callable removes exactly that handler.
- Publishing with a string event name normalizes to `EventName`.
- Invalid event names raise `ValueError`.
- A handler can unsubscribe itself during publish without deadlock.
- A handler that raises `Exception` is logged and does not prevent later
  handlers from running.
- Concurrent publish calls from multiple threads deliver the expected number of
  events to a thread-safe test collector.
- `clear()` removes all subscribers for test isolation.

### 7.2 `tests/test_build_events.py`

Cover build integration:

- `build_tile_all()` emits `TILE_START`, paired `PIPELINE_STEP` start/complete
  events for `vector`, `mesh`, `masks`, and `tile`, four `TILE_PROGRESS`
  events, and `TILE_COMPLETE`.
- Interrupted all-in-one builds emit `TILE_ERROR` and do not emit
  `TILE_COMPLETE`.
- Batch builds emit events only for selected steps and preserve existing
  `on_tile_complete` callback behavior.
- Falsey batch step results emit `TILE_ERROR` with the same failure message
  returned in `BuildTileResult`.

Tests should subscribe to the singleton bus, collect event objects, and call
`clear()` in `tearDown()` to avoid cross-test leakage.

## 8. Non-Goals

1. No GUI progress changes.
2. No CLI output changes.
3. No mandatory logging subscriber.
4. No cache implementation or `CACHE_HIT` emission.
5. No replacement of `O4_UI_Utils.vprint()`, `lvprint()`, or JSONL logging.
6. No pipeline orchestrator abstraction; TODO-037 owns that.

## 9. Verification

Focused verification:

```bash
uv run python -m unittest tests.test_event_bus tests.test_build_events -q
uv run ruff check src\O4_Event_Bus.py src\O4_Build_Core.py tests\test_event_bus.py tests\test_build_events.py
uv run ty check src\O4_Event_Bus.py src\O4_Build_Core.py
```

Repository verification before completion:

```bash
uv run python -m unittest discover -s tests
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

## 10. References

- Backlog item: `TODO.md`, TODO-036.
- Build boundary: `src/O4_Build_Core.py`.
- Build state facade: `src/O4_Build_Context.py`.
- Existing structured logging: `src/O4_UI_Utils.py`.
- Current build tests: `tests/test_build_core.py` and
  `tests/test_build_context.py`.
