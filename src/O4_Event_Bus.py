from __future__ import annotations

import contextlib
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
