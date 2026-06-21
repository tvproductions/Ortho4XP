"""Logging helpers for provider failover decisions."""

import O4_UI_Utils as UI


def log_blacklist(provider_code, consecutive_failures, threshold, blacklisted_until):
    UI.log_event(
        "Provider blacklisted",
        level="WARNING",
        context={
            "provider_code": provider_code,
            "consecutive_failures": consecutive_failures,
            "failure_threshold": threshold,
            "blacklisted_until": blacklisted_until,
        },
    )
    UI.vprint(
        1,
        "Provider",
        provider_code,
        "temporarily blacklisted after",
        consecutive_failures,
        "failed texture attempt(s).",
    )


def log_failover(failed_provider, replacement_provider, texture_attrs):
    til_x_left, til_y_top, zoomlevel, _provider_code = texture_attrs
    context = {
        "failed_provider": failed_provider,
        "replacement_provider": replacement_provider,
        "til_x_left": til_x_left,
        "til_y_top": til_y_top,
        "zoomlevel": zoomlevel,
    }
    UI.log_event("Provider failover selected", level="WARNING", context=context)
    UI.vprint(
        1,
        "Provider failover:",
        failed_provider,
        "->",
        replacement_provider,
        "for texture",
        (til_x_left, til_y_top, zoomlevel),
    )
