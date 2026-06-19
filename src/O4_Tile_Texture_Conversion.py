from collections import defaultdict

import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Texture_Conversion_Scheduler as TCS
import O4_UI_Utils as UI


def report_texture_conversion_result(tile, result):
    if result.interrupted:
        UI.vprint(1, "DDS conversion process interrupted.")
        return
    if result.failed:
        provider_counts = _texture_conversion_provider_counts(result.failures)
        UI.vprint(
            1,
            "DDS conversion summary:",
            f"{result.failed} failed texture(s)",
            f"for tile {FNAMES.short_latlon(tile.lat, tile.lon)}.",
            f"Providers: {provider_counts}.",
        )
        return
    if result.completed >= 1:
        UI.vprint(1, " *DDS conversion of textures completed.")


def run_texture_conversion_scheduler(convert_queue, result_holder, max_convert_slots):
    try:
        result_holder["result"] = TCS.run_texture_conversion_queue(
            convert_queue,
            max_convert_slots,
            convert_texture=_convert_texture_job,
        )
    except Exception as exc:
        result_holder["exception"] = exc


def handle_texture_conversion_scheduler_result(tile, result_holder):
    if "exception" in result_holder:
        exc = result_holder["exception"]
        UI.vprint(
            1,
            "DDS conversion scheduler failed:",
            f"{type(exc).__name__}: {exc}",
        )
        UI.vprint(3, exc)
        UI.red_flag = True
        return
    result = result_holder.get("result")
    if result is None:
        UI.vprint(1, "DDS conversion scheduler failed:", "missing conversion result.")
        UI.red_flag = True
        return
    report_texture_conversion_result(tile, result)


def _texture_conversion_provider_counts(failures):
    counts = defaultdict(int)
    for failure in failures:
        counts[failure.provider_code or "unknown"] += 1
    return ", ".join(
        f"{provider}={count}" for provider, count in sorted(counts.items())
    )


def _convert_texture_job(*args, texture_source=None):
    if texture_source is not None:
        return IMG.convert_texture_source(texture_source)
    return IMG.convert_texture(*args)
