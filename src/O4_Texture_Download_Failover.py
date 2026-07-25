"""Retry decisions for provider failover during texture downloads."""

from __future__ import annotations

import O4_Provider_Failover as FAILOVER
import O4_UI_Utils as UI


def active_request(runtime, request, providers):
    # Preflight replacement prevents spending another HTTP attempt on a provider
    # that previous texture attempts have already blacklisted.
    if not runtime.failover_registry.is_blacklisted(request.active_attrs[3]):
        return request
    replacement_request = _replacement_request(runtime, request, providers)
    return replacement_request or request


def record_successful_download(runtime, request, result):
    # A concrete success proves the provider is usable again for this process.
    runtime.failover_registry.record_success(result.provider_code)
    runtime.state.progress["done"] += 1
    runtime.state.attempts.pop(request.active_attrs, None)
    return None


def record_failed_download(runtime, request, providers, failure_context):
    # Failure handling keeps two decisions separate: provider health determines
    # failover, while per-texture attempts still control final failure summaries.
    active_attrs = request.active_attrs
    provider_state = runtime.failover_registry.record_failure(active_attrs[3])
    attempt = _record_texture_attempt(runtime, active_attrs)
    replacement_request = _failover_request(runtime, request, provider_state, providers)
    if replacement_request is not None and not UI.red_flag:
        runtime.state.attempts.pop(active_attrs, None)
        return replacement_request
    if attempt < runtime.max_attempts and not UI.red_flag:
        return request
    runtime.state.final_failures.append(failure_context(active_attrs))
    runtime.state.attempts.pop(active_attrs, None)
    return None


def _record_texture_attempt(runtime, attrs):
    attempt = runtime.state.attempts[attrs] + 1
    runtime.state.attempts[attrs] = attempt
    return attempt


def _failover_request(runtime, request, provider_state, providers):
    # Only the provider code changes during failover; texture coordinates and
    # zoom level remain tied to the terrain file that requested the texture.
    if not provider_state.blacklisted:
        return None
    return _replacement_request(runtime, request, providers)


def _replacement_request(runtime, request, providers):
    compatible_providers = _extent_compatible_providers(runtime, request, providers)
    active_attrs = request.active_attrs
    replacement = runtime.failover_registry.select_replacement(
        active_attrs[3], compatible_providers
    )
    if replacement is None:
        return None
    FAILOVER.log_failover(active_attrs[3], replacement, request.requested_attrs)
    return request.with_active_attrs((*active_attrs[:3], replacement))


def _extent_compatible_providers(runtime, request, providers):
    requested_explicit = runtime.provider_extent_resolver(request.requested_attrs[3])
    return {
        code: provider
        for code, provider in providers.items()
        if runtime.provider_extent_resolver(code) == requested_explicit
    }
