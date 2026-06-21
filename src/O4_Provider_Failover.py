"""Thread-safe provider failover state for imagery downloads."""

from __future__ import annotations

import threading
from typing import Any

import O4_Provider_Failover_Logging as LOG
from O4_Provider_Failover_Models import (
    ProviderFailoverPolicy,
    ProviderHealthState,
)


class ProviderFailoverRegistry:
    # This object is shared by async download tasks and may be reused by future
    # batch surfaces, so all mutable provider health state stays behind one lock.
    def __init__(
        self,
        policy: ProviderFailoverPolicy | None = None,
        **overrides: Any,
    ):
        policy = _policy_from_options(policy, overrides)
        self.failure_threshold = policy.failure_threshold
        self.timeout_seconds = policy.timeout_seconds
        self._clock = policy.clock
        self._lock = threading.RLock()
        self._failures: dict[str, int] = {}
        self._blacklisted_until: dict[str, float] = {}

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
            self._blacklisted_until.clear()

    def record_success(self, provider_code: str) -> None:
        with self._lock:
            self._failures.pop(provider_code, None)
            self._blacklisted_until.pop(provider_code, None)

    def record_failure(self, provider_code: str) -> ProviderHealthState:
        with self._lock:
            # Expiry is lazy: callers do not need a background cleanup task, and
            # a provider becomes eligible again the next time it is inspected.
            self._expire_if_needed(provider_code)
            consecutive_failures = self._failures.get(provider_code, 0) + 1
            self._failures[provider_code] = consecutive_failures
            blacklisted_until = self._blacklisted_until.get(provider_code)
            if consecutive_failures >= self.failure_threshold:
                blacklisted_until = self._clock() + self.timeout_seconds
                self._blacklisted_until[provider_code] = blacklisted_until
                LOG.log_blacklist(
                    provider_code,
                    consecutive_failures,
                    self.failure_threshold,
                    blacklisted_until,
                )
            return ProviderHealthState(
                provider_code=provider_code,
                consecutive_failures=consecutive_failures,
                blacklisted_until=blacklisted_until,
                blacklisted=blacklisted_until is not None,
            )

    def is_blacklisted(self, provider_code: str) -> bool:
        with self._lock:
            self._expire_if_needed(provider_code)
            return provider_code in self._blacklisted_until

    def state_for(self, provider_code: str) -> ProviderHealthState:
        with self._lock:
            self._expire_if_needed(provider_code)
            blacklisted_until = self._blacklisted_until.get(provider_code)
            return ProviderHealthState(
                provider_code=provider_code,
                consecutive_failures=self._failures.get(provider_code, 0),
                blacklisted_until=blacklisted_until,
                blacklisted=blacklisted_until is not None,
            )

    def select_replacement(
        self,
        failed_provider: str,
        providers: dict[str, dict[str, Any]],
    ) -> str | None:
        with self._lock:
            # The loaded provider inventory is the source of truth. Hidden
            # providers are allowed, but GUI-visible providers win ties.
            candidates = [
                provider_code
                for provider_code, provider in providers.items()
                if provider_code != failed_provider
                and provider.get("code", provider_code) == provider_code
                and not self._is_blacklisted_locked(provider_code)
            ]
            if not candidates:
                return None
            return sorted(
                candidates, key=lambda code: _provider_priority(code, providers)
            )[0]

    def _is_blacklisted_locked(self, provider_code: str) -> bool:
        self._expire_if_needed(provider_code)
        return provider_code in self._blacklisted_until

    def _expire_if_needed(self, provider_code: str) -> None:
        blacklisted_until = self._blacklisted_until.get(provider_code)
        if blacklisted_until is None or self._clock() < blacklisted_until:
            return
        self._blacklisted_until.pop(provider_code, None)
        self._failures.pop(provider_code, None)


def _provider_priority(provider_code, providers):
    provider = providers[provider_code]
    gui_rank = 0 if provider.get("in_GUI", True) else 1
    return gui_rank, provider_code


def _policy_from_options(policy, overrides):
    # Tests pass a fake clock directly; production uses the default monotonic
    # policy. Keeping the compatibility shim here avoids a wide call-site API.
    policy = policy or ProviderFailoverPolicy()
    return ProviderFailoverPolicy(
        failure_threshold=overrides.get("failure_threshold", policy.failure_threshold),
        timeout_seconds=overrides.get("timeout_seconds", policy.timeout_seconds),
        clock=overrides.get("clock", policy.clock),
    ).normalized()


def log_failover(failed_provider, replacement_provider, texture_attrs):
    LOG.log_failover(failed_provider, replacement_provider, texture_attrs)


default_registry = ProviderFailoverRegistry()
