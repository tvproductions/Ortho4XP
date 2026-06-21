"""Data contracts for provider failover state."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderHealthState:
    provider_code: str
    consecutive_failures: int = 0
    blacklisted_until: float | None = None
    blacklisted: bool = False


@dataclass(frozen=True)
class ProviderFailoverPolicy:
    failure_threshold: int = 3
    timeout_seconds: float = 300
    clock: Callable[[], float] = time.monotonic

    def normalized(self) -> ProviderFailoverPolicy:
        return ProviderFailoverPolicy(
            failure_threshold=max(1, int(self.failure_threshold)),
            timeout_seconds=max(0.0, float(self.timeout_seconds)),
            clock=self.clock,
        )
