# TODO-036 Event Bus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a thread-safe event bus and emit coarse build lifecycle events from existing build boundaries without changing CLI or GUI behavior.

**Architecture:** `src/O4_Event_Bus.py` owns the singleton event infrastructure, typed event names, event dataclass, subscription registry, and test-reset hooks. `src/O4_Build_Core.py` stays the only build integration point for TODO-036, using small local publish helpers around existing all-in-one and batch build step loops.

**Tech Stack:** Python 3.13.x, stdlib `dataclasses`, `datetime`, `enum.StrEnum`, `threading`, `unittest`, `unittest.mock`, `concurrent.futures`. No new runtime or development dependencies.

## Global Constraints

- Python 3.13.x is required.
- Use `unittest` only; do not introduce `pytest` tests.
- No GUI progress changes.
- No CLI output changes.
- No mandatory logging subscriber.
- No cache implementation and no `CACHE_HIT` emission.
- No replacement of `O4_UI_Utils.vprint()`, `lvprint()`, or JSONL logging.
- No pipeline orchestrator abstraction; TODO-037 owns that.
- Keep current `BuildResult`, `BuildTileResult`, and `BuildBatchResult` contracts intact.
- Subscriber exceptions must not break tile builds.
- Use `apply_patch` for manual edits.

---

## File Structure

- **Create:** `src/O4_Event_Bus.py` - singleton event bus, typed event names, event payloads, subscribe/publish helpers.
- **Create:** `tests/test_event_bus.py` - event bus unit tests for API, unsubscribe, normalization, error isolation, and concurrency.
- **Create:** `tests/test_build_events.py` - build lifecycle event tests for all-in-one and batch build paths.
- **Modify:** `src/O4_Build_Core.py` - publish event helpers and event calls at existing build boundaries.
- **Modify:** `TODO.md` - mark TODO-036 done only after implementation and verification pass.

---

### Task 1: Event Bus API

**Files:**
- Create: `src/O4_Event_Bus.py`
- Create: `tests/test_event_bus.py`

**Interfaces:**
- Produces: `EventName`, `Event`, `EventBus`, `event_bus()`, `publish()`, `subscribe()`
- Consumes: `O4_UI_Utils.log_exception()` in later Task 2

- [ ] **Step 1: Write failing API tests**

Create `tests/test_event_bus.py`:

```python
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Event_Bus as EVENTS


class EventBusAPITests(unittest.TestCase):
    def setUp(self):
        EVENTS.event_bus().clear()

    def tearDown(self):
        EVENTS.event_bus().clear()

    def test_publish_returns_event_with_normalized_name_and_payload(self):
        event = EVENTS.publish("TILE_START", lat=12, lon=-123, mode="all")

        self.assertEqual(event.name, EVENTS.EventName.TILE_START)
        self.assertEqual(event.payload, {"lat": 12, "lon": -123, "mode": "all"})
        self.assertIsNotNone(event.timestamp.tzinfo)

    def test_subscribe_receives_events_in_order(self):
        received = []

        EVENTS.subscribe(EVENTS.EventName.TILE_START, lambda event: received.append(("a", event)))
        EVENTS.subscribe(EVENTS.EventName.TILE_START, lambda event: received.append(("b", event)))

        event = EVENTS.publish(EVENTS.EventName.TILE_START, lat=12)

        self.assertEqual([name for name, _event in received], ["a", "b"])
        self.assertTrue(all(seen is event for _name, seen in received))

    def test_unsubscribe_removes_exact_handler(self):
        received = []

        def first(event):
            received.append(("first", event.name))

        def second(event):
            received.append(("second", event.name))

        unsubscribe = EVENTS.subscribe(EVENTS.EventName.TILE_START, first)
        EVENTS.subscribe(EVENTS.EventName.TILE_START, second)

        unsubscribe()
        EVENTS.publish(EVENTS.EventName.TILE_START)

        self.assertEqual(received, [("second", EVENTS.EventName.TILE_START)])

    def test_clear_removes_all_subscribers(self):
        received = []
        EVENTS.subscribe(EVENTS.EventName.TILE_START, received.append)

        EVENTS.event_bus().clear()
        EVENTS.publish(EVENTS.EventName.TILE_START)

        self.assertEqual(received, [])

    def test_invalid_event_name_raises_value_error(self):
        with self.assertRaises(ValueError):
            EVENTS.publish("NOT_A_REAL_EVENT")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest tests.test_event_bus -v
```

Expected: import error because `O4_Event_Bus` does not exist.

- [ ] **Step 3: Implement minimal event bus API**

Create `src/O4_Event_Bus.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from typing import Any


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
    def __init__(self) -> None:
        self._lock = RLock()
        self._handlers: dict[EventName, list[EventHandler]] = {}

    def subscribe(self, name: EventName | str, handler: EventHandler) -> Unsubscribe:
        event_name = _event_name(name)
        with self._lock:
            self._handlers.setdefault(event_name, []).append(handler)

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._handlers.get(event_name)
                if not handlers:
                    return
                with contextlib.suppress(ValueError):
                    handlers.remove(handler)
                if not handlers:
                    self._handlers.pop(event_name, None)

        return unsubscribe

    def publish(self, name: EventName | str, **payload: Any) -> Event:
        event_name = _event_name(name)
        event = Event(
            name=event_name,
            timestamp=datetime.now(UTC),
            payload=dict(payload),
        )
        with self._lock:
            handlers = tuple(self._handlers.get(event_name, ()))
        for handler in handlers:
            handler(event)
        return event

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()


_BUS = EventBus()


def event_bus() -> EventBus:
    return _BUS


def publish(name: EventName | str, **payload: Any) -> Event:
    return event_bus().publish(name, **payload)


def subscribe(name: EventName | str, handler: EventHandler) -> Unsubscribe:
    return event_bus().subscribe(name, handler)


def _event_name(name: EventName | str) -> EventName:
    if isinstance(name, EventName):
        return name
    return EventName(str(name))
```

Also add `import contextlib` at the top of `src/O4_Event_Bus.py`:

```python
import contextlib
```

- [ ] **Step 4: Run API tests to verify pass**

Run:

```bash
uv run python -m unittest tests.test_event_bus -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Run focused lint/type checks**

Run:

```bash
uv run ruff check src\O4_Event_Bus.py tests\test_event_bus.py
uv run ty check src\O4_Event_Bus.py
```

Expected: both commands pass.

- [ ] **Step 6: Commit task**

Run:

```bash
git add src\O4_Event_Bus.py tests\test_event_bus.py
git commit -m "feat: add event bus API"
```

---

### Task 2: Event Bus Error Isolation and Thread Safety

**Files:**
- Modify: `src/O4_Event_Bus.py`
- Modify: `tests/test_event_bus.py`

**Interfaces:**
- Consumes: `EventBus.publish(name, **payload) -> Event`
- Produces: subscriber exception isolation and thread-safe publish semantics used by build events in later tasks

- [ ] **Step 1: Add failing subscriber error and concurrency tests**

Append to `tests/test_event_bus.py`:

```python
import concurrent.futures
import threading
from unittest import mock


class EventBusRobustnessTests(unittest.TestCase):
    def setUp(self):
        EVENTS.event_bus().clear()

    def tearDown(self):
        EVENTS.event_bus().clear()

    def test_handler_exception_is_logged_and_later_handlers_still_run(self):
        received = []

        def failing_handler(_event):
            raise RuntimeError("subscriber failed")

        def healthy_handler(event):
            received.append(event.name)

        EVENTS.subscribe(EVENTS.EventName.TILE_START, failing_handler)
        EVENTS.subscribe(EVENTS.EventName.TILE_START, healthy_handler)

        with mock.patch.object(EVENTS.UI, "log_exception") as log_exception:
            EVENTS.publish(EVENTS.EventName.TILE_START, lat=12)

        self.assertEqual(received, [EVENTS.EventName.TILE_START])
        log_exception.assert_called_once()
        args, kwargs = log_exception.call_args
        self.assertIsInstance(args[0], RuntimeError)
        self.assertEqual(kwargs["context"]["event_name"], "TILE_START")
        self.assertIn("failing_handler", kwargs["context"]["handler"])

    def test_base_exception_is_not_swallowed(self):
        def interrupting_handler(_event):
            raise KeyboardInterrupt()

        EVENTS.subscribe(EVENTS.EventName.TILE_START, interrupting_handler)

        with self.assertRaises(KeyboardInterrupt):
            EVENTS.publish(EVENTS.EventName.TILE_START)

    def test_handler_can_unsubscribe_itself_during_publish(self):
        received = []
        unsubscribe_holder = {}

        def self_removing_handler(event):
            received.append(event.name)
            unsubscribe_holder["unsubscribe"]()

        unsubscribe_holder["unsubscribe"] = EVENTS.subscribe(
            EVENTS.EventName.TILE_START,
            self_removing_handler,
        )

        EVENTS.publish(EVENTS.EventName.TILE_START)
        EVENTS.publish(EVENTS.EventName.TILE_START)

        self.assertEqual(received, [EVENTS.EventName.TILE_START])

    def test_concurrent_publish_delivers_expected_event_count(self):
        lock = threading.Lock()
        received = []

        def handler(event):
            with lock:
                received.append(event.payload["index"])

        EVENTS.subscribe(EVENTS.EventName.TILE_PROGRESS, handler)

        def publish_one(index):
            EVENTS.publish(EVENTS.EventName.TILE_PROGRESS, index=index)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(publish_one, range(100)))

        self.assertEqual(sorted(received), list(range(100)))
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest tests.test_event_bus -v
```

Expected: failure in `test_handler_exception_is_logged_and_later_handlers_still_run` because subscriber exceptions are not caught.

- [ ] **Step 3: Implement subscriber exception isolation**

Modify `src/O4_Event_Bus.py`:

```python
import O4_UI_Utils as UI
```

Replace the handler loop in `EventBus.publish()`:

```python
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                UI.log_exception(
                    exc,
                    context={
                        "event_name": event.name.value,
                        "handler": repr(handler),
                    },
                )
        return event
```

Leave `BaseException` subclasses uncaught by catching only `Exception`.

- [ ] **Step 4: Run event bus tests**

Run:

```bash
uv run python -m unittest tests.test_event_bus -v
```

Expected: 9 tests pass.

- [ ] **Step 5: Run focused lint/type checks**

Run:

```bash
uv run ruff check src\O4_Event_Bus.py tests\test_event_bus.py
uv run ty check src\O4_Event_Bus.py
```

Expected: both commands pass.

- [ ] **Step 6: Commit task**

Run:

```bash
git add src\O4_Event_Bus.py tests\test_event_bus.py
git commit -m "feat: harden event bus publishing"
```

---

### Task 3: All-in-One Build Event Emission

**Files:**
- Modify: `src/O4_Build_Core.py`
- Create: `tests/test_build_events.py`

**Interfaces:**
- Consumes: `O4_Event_Bus.publish(name, **payload)`
- Produces: all-in-one build lifecycle events with payload keys `lat`, `lon`, `mode`, `step`, `status`, `completed_steps`, `total_steps`, and `message`

- [ ] **Step 1: Write failing all-in-one event tests**

Create `tests/test_build_events.py`:

```python
import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Core as CORE
import O4_Event_Bus as EVENTS


def _tile():
    return SimpleNamespace(lat=12, lon=-123, build_dir="build")


def _event_summary(events):
    return [
        (
            event.name.value,
            event.payload.get("step"),
            event.payload.get("status"),
            event.payload.get("message"),
        )
        for event in events
    ]


class BuildAllEventTests(unittest.TestCase):
    def setUp(self):
        EVENTS.event_bus().clear()
        self.events = []
        for name in EVENTS.EventName:
            EVENTS.subscribe(name, self.events.append)

    def tearDown(self):
        EVENTS.event_bus().clear()

    def test_build_tile_all_emits_lifecycle_events(self):
        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=1),
            mock.patch.object(CORE.MASK, "build_masks", return_value=1),
            mock.patch.object(CORE.TILE, "build_tile", return_value=1),
            mock.patch.object(CORE.UI, "lvprint"),
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
        ):
            result = CORE.build_tile_all(_tile())

        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        self.assertEqual(
            _event_summary(self.events),
            [
                ("TILE_START", None, None, None),
                ("PIPELINE_STEP", "vector", "running", None),
                ("PIPELINE_STEP", "vector", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("PIPELINE_STEP", "mesh", "running", None),
                ("PIPELINE_STEP", "mesh", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("PIPELINE_STEP", "masks", "running", None),
                ("PIPELINE_STEP", "masks", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("PIPELINE_STEP", "tile", "running", None),
                ("PIPELINE_STEP", "tile", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("TILE_COMPLETE", "all", None, None),
            ],
        )
        self.assertTrue(
            all(event.payload["lat"] == 12 for event in self.events)
        )
        self.assertTrue(
            all(event.payload["lon"] == -123 for event in self.events)
        )
        self.assertTrue(
            all(event.payload["mode"] == "all" for event in self.events)
        )
        progress_payloads = [
            event.payload
            for event in self.events
            if event.name == EVENTS.EventName.TILE_PROGRESS
        ]
        self.assertEqual(
            [(p["completed_steps"], p["total_steps"]) for p in progress_payloads],
            [(1, 4), (2, 4), (3, 4), (4, 4)],
        )

    def test_interrupted_all_in_one_emits_tile_error_not_complete(self):
        def interrupting_mesh(_tile, ctx=None):
            ctx.red_flag = True
            return 0

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", side_effect=interrupting_mesh),
            mock.patch.object(CORE.MASK, "build_masks", return_value=1),
            mock.patch.object(CORE.TILE, "build_tile", return_value=1),
            mock.patch.object(CORE.UI, "lvprint"),
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
        ):
            result = CORE.build_tile_all(_tile())

        self.assertEqual(result, CORE.BuildResult(False, "mesh", "interrupted"))
        self.assertIn(
            ("TILE_ERROR", "mesh", None, "interrupted"),
            _event_summary(self.events),
        )
        self.assertNotIn("TILE_COMPLETE", [event.name.value for event in self.events])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest tests.test_build_events -v
```

Expected: failures because `O4_Build_Core` does not publish events yet.

- [ ] **Step 3: Add event helpers to build core**

Modify `src/O4_Build_Core.py` imports:

```python
import O4_Event_Bus as EVENTS
```

Add helper functions near `_build_steps()`:

```python
def _tile_event_payload(tile, *, mode: str) -> dict[str, object]:
    return {"lat": tile.lat, "lon": tile.lon, "mode": mode}


def _publish_tile_start(tile, *, mode: str) -> None:
    EVENTS.publish(EVENTS.EventName.TILE_START, **_tile_event_payload(tile, mode=mode))


def _publish_tile_complete(tile, *, mode: str, step: str = "all") -> None:
    EVENTS.publish(
        EVENTS.EventName.TILE_COMPLETE,
        **_tile_event_payload(tile, mode=mode),
        step=step,
    )


def _publish_tile_error(tile, *, mode: str, step: str, message: str) -> None:
    EVENTS.publish(
        EVENTS.EventName.TILE_ERROR,
        **_tile_event_payload(tile, mode=mode),
        step=step,
        message=message,
    )


def _publish_step(tile, *, mode: str, step: str, status: str) -> None:
    EVENTS.publish(
        EVENTS.EventName.PIPELINE_STEP,
        **_tile_event_payload(tile, mode=mode),
        step=step,
        status=status,
    )


def _publish_progress(
    tile,
    *,
    mode: str,
    completed_steps: int,
    total_steps: int,
) -> None:
    EVENTS.publish(
        EVENTS.EventName.TILE_PROGRESS,
        **_tile_event_payload(tile, mode=mode),
        completed_steps=completed_steps,
        total_steps=total_steps,
    )
```

- [ ] **Step 4: Publish events in all-in-one build**

Modify `build_tile_all()`:

```python
def build_tile_all(tile) -> BuildResult:
    """Run the current all-in-one tile sequence and return its structured result."""
    ctx = BC.BuildContext()
    _publish_tile_start(tile, mode="all")
    interrupted = _run_build_steps(tile, ctx)
    if interrupted:
        _publish_tile_error(tile, mode="all", step=interrupted.step, message=interrupted.message)
        return interrupted

    interrupted = _retry_incomplete_textures_if_needed(tile, ctx)
    if interrupted:
        _publish_tile_error(tile, mode="all", step=interrupted.step, message=interrupted.message)
        return interrupted

    ctx.is_working = False
    _report_remaining_incomplete_textures()
    _publish_tile_complete(tile, mode="all")
    return BuildResult(ok=True, step="all")
```

Modify `_run_build_steps()`:

```python
def _run_build_steps(tile, ctx) -> BuildResult | None:
    steps = _build_steps()
    total_steps = len(steps)
    for completed_steps, (step, build_step) in enumerate(steps, start=1):
        _publish_step(tile, mode="all", step=step, status="running")
        build_step(tile, ctx=ctx)
        if ctx.red_flag:
            return _interrupted(step)
        _publish_step(tile, mode="all", step=step, status="complete")
        _publish_progress(
            tile,
            mode="all",
            completed_steps=completed_steps,
            total_steps=total_steps,
        )
    return None
```

- [ ] **Step 5: Run focused build event tests**

Run:

```bash
uv run python -m unittest tests.test_build_events -v
```

Expected: 2 tests pass.

- [ ] **Step 6: Run existing build core tests**

Run:

```bash
uv run python -m unittest tests.test_build_core tests.test_build_context tests.test_build_core_interrupts -v
```

Expected: all existing build tests pass.

- [ ] **Step 7: Run focused lint/type checks**

Run:

```bash
uv run ruff check src\O4_Build_Core.py tests\test_build_events.py
uv run ty check src\O4_Build_Core.py
```

Expected: both commands pass.

- [ ] **Step 8: Commit task**

Run:

```bash
git add src\O4_Build_Core.py tests\test_build_events.py
git commit -m "feat: emit all-in-one build events"
```

---

### Task 4: Batch Build Event Emission

**Files:**
- Modify: `src/O4_Build_Core.py`
- Modify: `tests/test_build_events.py`

**Interfaces:**
- Consumes: helper functions from Task 3
- Produces: `mode="batch"` event emissions from `_build_tile_plan()`

- [ ] **Step 1: Add failing batch event tests**

Append to `tests/test_build_events.py`:

```python
def _tile_plan(
    lat=12,
    lon=-123,
    *,
    steps=("vector", "mesh"),
    override_tile_config=False,
):
    import O4_Build_Models as MODELS

    return MODELS.BuildTilePlan(
        lat=lat,
        lon=lon,
        provider="BI",
        zoom_level=16,
        output_dir="Tiles",
        custom_build_dir="Tiles/",
        steps=steps,
        override_tile_config=override_tile_config,
    )


class BuildBatchEventTests(unittest.TestCase):
    def setUp(self):
        EVENTS.event_bus().clear()
        self.events = []
        for name in EVENTS.EventName:
            EVENTS.subscribe(name, self.events.append)

    def tearDown(self):
        EVENTS.event_bus().clear()

    def _patch_tile_class(self):
        return mock.patch.object(
            CORE.CFG,
            "Tile",
            side_effect=lambda lat, lon, custom: SimpleNamespace(
                lat=lat,
                lon=lon,
                custom_build_dir=custom,
                build_dir=f"build-{lat}-{lon}",
                dem=None,
                default_website="",
                default_zl=0,
                make_dirs=mock.Mock(),
                read_from_config=mock.Mock(return_value=1),
            ),
        )

    def test_batch_build_emits_selected_step_events_and_completion_callback(self):
        import O4_Build_Models as MODELS

        completed = []
        with (
            self._patch_tile_class(),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=1),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
        ):
            result = CORE.build_batch(
                MODELS.BuildPlan((_tile_plan(steps=("vector", "mesh")),)),
                on_tile_complete=completed.append,
            )

        self.assertTrue(result.ok)
        self.assertEqual(completed, list(result.tiles))
        self.assertEqual(
            _event_summary(self.events),
            [
                ("TILE_START", None, None, None),
                ("PIPELINE_STEP", "vector", "running", None),
                ("PIPELINE_STEP", "vector", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("PIPELINE_STEP", "mesh", "running", None),
                ("PIPELINE_STEP", "mesh", "complete", None),
                ("TILE_PROGRESS", None, None, None),
                ("TILE_COMPLETE", "all", None, None),
            ],
        )
        self.assertTrue(all(event.payload["mode"] == "batch" for event in self.events))

    def test_falsey_batch_step_emits_tile_error(self):
        import O4_Build_Models as MODELS

        with (
            self._patch_tile_class(),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=0),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
        ):
            result = CORE.build_batch(MODELS.BuildPlan((_tile_plan(steps=("mesh",)),)))

        self.assertFalse(result.ok)
        self.assertEqual(result.tiles[0].message, "mesh failed")
        self.assertIn(
            ("TILE_ERROR", "mesh", None, "mesh failed"),
            _event_summary(self.events),
        )
        self.assertNotIn("TILE_COMPLETE", [event.name.value for event in self.events])
```

- [ ] **Step 2: Run batch event tests to verify failure**

Run:

```bash
uv run python -m unittest tests.test_build_events -v
```

Expected: batch tests fail because `_build_tile_plan()` does not publish events yet.

- [ ] **Step 3: Publish events in batch build**

Modify `_build_tile_plan()` in `src/O4_Build_Core.py`:

```python
def _build_tile_plan(
    tile_plan: MODELS.BuildTilePlan, ctx: BC.BuildContext
) -> MODELS.BuildTileResult:
    tile = CFG.Tile(tile_plan.lat, tile_plan.lon, tile_plan.custom_build_dir)
    _publish_tile_start(tile, mode="batch")
    tile.default_website = tile_plan.provider
    tile.default_zl = tile_plan.zoom_level
    tile.custom_build_dir = tile_plan.custom_build_dir
    tile.dem = None
    if tile_plan.override_tile_config:
        tile.read_from_config(use_global=True)
    else:
        tile.read_from_config()
    if _steps_need_tile_directory(tile_plan.steps):
        tile.make_dirs()
    total_steps = len(tile_plan.steps)
    completed_steps = 0
    for step in MODELS.ALL_STEPS:
        if step not in tile_plan.steps:
            continue
        _publish_step(tile, mode="batch", step=step, status="running")
        ok = _run_batch_step(step, tile, ctx)
        if ctx.red_flag:
            UI.exit_message_and_bottom_line("")
            _publish_tile_error(
                tile,
                mode="batch",
                step=step,
                message="interrupted",
            )
            return MODELS.BuildTileResult(
                tile_plan.lat,
                tile_plan.lon,
                False,
                step,
                "interrupted",
            )
        if not ok:
            message = f"{step} failed"
            _publish_tile_error(tile, mode="batch", step=step, message=message)
            return MODELS.BuildTileResult(
                tile_plan.lat,
                tile_plan.lon,
                False,
                step,
                message,
            )
        completed_steps += 1
        _publish_step(tile, mode="batch", step=step, status="complete")
        _publish_progress(
            tile,
            mode="batch",
            completed_steps=completed_steps,
            total_steps=total_steps,
        )
    _publish_tile_complete(tile, mode="batch")
    return MODELS.BuildTileResult(tile_plan.lat, tile_plan.lon, True, "all")
```

- [ ] **Step 4: Run build event tests**

Run:

```bash
uv run python -m unittest tests.test_build_events -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Run existing build tests**

Run:

```bash
uv run python -m unittest tests.test_build_core tests.test_build_context tests.test_build_core_interrupts -v
```

Expected: all existing build tests pass.

- [ ] **Step 6: Run focused lint/type checks**

Run:

```bash
uv run ruff check src\O4_Event_Bus.py src\O4_Build_Core.py tests\test_event_bus.py tests\test_build_events.py
uv run ty check src\O4_Event_Bus.py src\O4_Build_Core.py
```

Expected: both commands pass.

- [ ] **Step 7: Commit task**

Run:

```bash
git add src\O4_Build_Core.py tests\test_build_events.py
git commit -m "feat: emit batch build events"
```

---

### Task 5: Verification, Backlog Evidence, and Issue Closeout

**Files:**
- Modify: `TODO.md`

**Interfaces:**
- Consumes: completed Tasks 1-4
- Produces: verified TODO-036 completion evidence and closed GHI #36

- [ ] **Step 1: Run focused verification**

Run:

```bash
uv run python -m unittest tests.test_event_bus tests.test_build_events -q
uv run ruff check src\O4_Event_Bus.py src\O4_Build_Core.py tests\test_event_bus.py tests\test_build_events.py
uv run ty check src\O4_Event_Bus.py src\O4_Build_Core.py
```

Expected:

- Event bus and build event tests pass.
- Ruff reports no findings for changed files.
- `ty` reports no type errors for changed Python files.

- [ ] **Step 2: Run build-regression tests**

Run:

```bash
uv run python -m unittest tests.test_build_core tests.test_build_context tests.test_build_core_interrupts -q
```

Expected: all selected build regression tests pass.

- [ ] **Step 3: Run full repository verification**

Run:

```bash
uv run python -m unittest discover -s tests
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected:

- Full `unittest` discovery passes.
- Full quality check passes, including Ruff, Ruff format, ty, whitespace, complexity, and native checks.

- [ ] **Step 4: Update TODO.md completion evidence**

Modify the TODO-036 block in `TODO.md` from:

```markdown
Status: Pending
GitHub Issue: #36

Add event-driven architecture for module communication. Reference:
ORTHO4XP_V3 `O4_EventBus`.
```

to:

```markdown
Status: Done
GitHub Issue: #36

Completion note: implemented an infrastructure-first event bus with typed event
names, thread-safe publish/subscribe, subscriber exception isolation, and
coarse build lifecycle emissions from the existing all-in-one and batch build
boundaries. `CACHE_HIT` is defined but intentionally not emitted until
TODO-038 implements smart cache behavior.

Verification note: focused event/build event tests, build regression tests,
full `unittest` discovery, changed-file Ruff, changed-file `ty`, and the full
repository quality gate passed.

Add event-driven architecture for module communication. Reference:
ORTHO4XP_V3 `O4_EventBus`.
```

- [ ] **Step 5: Commit closeout changes**

Run:

```bash
git add TODO.md
git commit -m "docs: complete TODO-036 backlog evidence"
```

- [ ] **Step 6: Comment on GitHub issue #36**

Run:

```bash
gh issue comment 36 --repo tvproductions/Ortho4XP --body "Implemented TODO-036 as infrastructure-first event bus work.\n\nEvidence:\n- Added typed EventName values for TILE_START, TILE_PROGRESS, TILE_COMPLETE, TILE_ERROR, PIPELINE_STEP, and CACHE_HIT.\n- Added thread-safe singleton EventBus publish/subscribe with unsubscribe and test reset support.\n- Subscriber exceptions are logged and do not break build execution.\n- Existing all-in-one and batch build boundaries emit coarse lifecycle and pipeline-step events without GUI or CLI behavior changes.\n- CACHE_HIT is defined but intentionally not emitted until TODO-038 implements smart cache behavior.\n\nVerification:\n- uv run python -m unittest tests.test_event_bus tests.test_build_events -q\n- uv run python -m unittest tests.test_build_core tests.test_build_context tests.test_build_core_interrupts -q\n- uv run python -m unittest discover -s tests\n- uv run ruff check src\\O4_Event_Bus.py src\\O4_Build_Core.py tests\\test_event_bus.py tests\\test_build_events.py\n- uv run ty check src\\O4_Event_Bus.py src\\O4_Build_Core.py\n- uv run python .codex/skills/quality-check/scripts/quality_check.py"
```

Expected: GitHub issue receives the evidence comment.

- [ ] **Step 7: Close GitHub issue #36**

Run:

```bash
gh issue close 36 --repo tvproductions/Ortho4XP --comment "Acceptance criteria are complete and verification passed."
```

Expected: issue #36 is closed.

- [ ] **Step 8: Final status check**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected:

- Working tree is clean.
- Branch contains the TODO-036 implementation commits and backlog evidence commit.

---

## Self-Review

1. **Spec coverage:** Task 1 covers the typed event model and singleton helpers. Task 2 covers thread safety and subscriber error isolation. Task 3 covers all-in-one build events. Task 4 covers batch build events. Task 5 covers verification, backlog evidence, and GitHub issue tracking.
2. **Placeholder scan:** The plan has no placeholder implementation steps. `TODO-036`, `TODO-037`, and `TODO-038` appear only as backlog identifiers.
3. **Type consistency:** Event names, helper names, payload keys, and return contracts match the approved spec.
4. **Scope check:** The plan does not add GUI changes, CLI output changes, cache behavior, required subscribers, or a pipeline orchestrator.
