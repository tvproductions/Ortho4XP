"""Retry decisions for provider failover during texture downloads."""

from __future__ import annotations

import O4_Provider_Failover as FAILOVER
import O4_UI_Utils as UI


def active_attrs(runtime, attrs, providers):
    # Preflight replacement prevents spending another HTTP attempt on a provider
    # that previous texture attempts have already blacklisted.
    if not runtime.failover_registry.is_blacklisted(attrs[3]):
        return attrs
    replacement_attrs = _replacement_attrs(runtime, attrs, providers)
    return replacement_attrs or attrs


def record_successful_download(runtime, attrs, result):
    # A concrete success proves the provider is usable again for this process.
    runtime.failover_registry.record_success(result.provider_code)
    runtime.state.progress["done"] += 1
    runtime.state.attempts.pop(attrs, None)
    return None


def record_failed_download(runtime, attrs, providers, failure_context):
    # Failure handling keeps two decisions separate: provider health determines
    # failover, while per-texture attempts still control final failure summaries.
    provider_state = runtime.failover_registry.record_failure(attrs[3])
    attempt = _record_texture_attempt(runtime, attrs)
    replacement_attrs = _failover_attrs(runtime, attrs, provider_state, providers)
    if replacement_attrs is not None and not UI.red_flag:
        runtime.state.attempts.pop(attrs, None)
        return replacement_attrs
    if attempt < runtime.max_attempts and not UI.red_flag:
        return attrs
    runtime.state.final_failures.append(failure_context(attrs))
    runtime.state.attempts.pop(attrs, None)
    return None


def _record_texture_attempt(runtime, attrs):
    attempt = runtime.state.attempts[attrs] + 1
    runtime.state.attempts[attrs] = attempt
    return attempt


def _failover_attrs(runtime, attrs, provider_state, providers):
    # Only the provider code changes during failover; texture coordinates and
    # zoom level remain tied to the terrain file that requested the texture.
    if not provider_state.blacklisted:
        return None
    return _replacement_attrs(runtime, attrs, providers)


def _replacement_attrs(runtime, attrs, providers):
    replacement = runtime.failover_registry.select_replacement(attrs[3], providers)
    if replacement is None:
        return None
    FAILOVER.log_failover(attrs[3], replacement, attrs)
    return (*attrs[:3], replacement)
