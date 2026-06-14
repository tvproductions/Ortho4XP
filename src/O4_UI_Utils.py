import json
import os
import sys
import time
import traceback as traceback_module
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import O4_File_Names as FNAMES

verbosity: int = 1
red_flag: bool = False
is_working: bool = False
cleaning_level: int = 1
gui: Any | None = None
log: bool = True

LOG_FILENAME = "Ortho4XP.log.json"
BOTTOM_LINE = (
    "_____________________________________________________________"
    + "____________________________________"
)


################################################################################
def subprocess_env():
    """Return a subprocess environment with OBJC_DISABLE_INITIALIZE_FORK_SAFETY
    set on macOS to suppress CoreFoundation fork-safety warnings."""
    env = os.environ.copy()
    if "dar" in sys.platform:
        env["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
    return env


################################################################################
def progress_bar(nbr, percentage, message=None):
    if gui:
        gui.pgrbv[nbr].set(percentage)


################################################################################
def vprint(min_verbosity, *args):
    if verbosity >= min_verbosity:
        print(*args)


################################################################################
def log_path() -> str:
    return FNAMES.resource_path(LOG_FILENAME)


################################################################################
def log_event(message: str, *args, **options: Any) -> None:
    if not log:
        return
    with suppress(OSError):
        _write_event(_event_payload(message, args, options))


################################################################################
def _event_payload(message: str, args: tuple[Any, ...], options: dict[str, Any]):
    error = options.get("error")
    event_verbosity = options.get("min_verbosity", verbosity)
    if event_verbosity is None:
        event_verbosity = verbosity
    event = {
        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "level": str(options.get("level", "INFO")).upper(),
        "message": str(message),
        "args": [_json_value(arg) for arg in args],
        "context": _json_value(options.get("context") or {}),
        "verbosity": event_verbosity,
        "error_type": _event_error_type(error, options.get("error_type")),
        "error_summary": _event_error_summary(error, options.get("error_summary")),
    }
    traceback_text = options.get("traceback_text")
    if traceback_text:
        event["traceback"] = traceback_text
    return event


################################################################################
def _write_event(event) -> None:
    with open(log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n")


################################################################################
def _event_error_type(error, explicit):
    if explicit:
        return explicit
    return type(error).__name__ if error is not None else None


################################################################################
def _event_error_summary(error, explicit):
    if explicit:
        return explicit
    return str(error) if error is not None else None


################################################################################
def log_exception(
    message: object = "Unhandled exception",
    *args,
    context: dict[str, Any] | None = None,
) -> None:
    exc_type, exc, exc_traceback = sys.exc_info()
    if exc is None:
        if isinstance(message, BaseException):
            exc = message
            text = str(message)
        else:
            text = str(message)
    else:
        text = str(message)
    traceback_text = None
    if exc_type is not None and exc_traceback is not None:
        traceback_text = "".join(
            traceback_module.format_exception(exc_type, exc, exc_traceback)
        )
    log_event(
        text,
        *args,
        level="ERROR",
        context=context,
        error=exc,
        traceback_text=traceback_text,
    )


################################################################################
def logprint(*args):
    log_event(_message_from_args(args), *args)


################################################################################
def lvprint(min_verbosity, *args):
    if verbosity >= min_verbosity:
        print(*args)
    log_event(_message_from_args(args), *args, min_verbosity=min_verbosity)


################################################################################
def bug_report(*args):
    logprint("An internal error occured. Please file a bug with lat/lon and cfg")
    if args:
        logprint(*args)


################################################################################
def exit_message_and_bottom_line(*args):
    global is_working
    if not args:
        args = ("Process interrupted",)
    if args[0]:
        logprint(*args)
        print(*args)
    print(BOTTOM_LINE)
    is_working = False


################################################################################
def timings_and_bottom_line(tinit):
    global is_working
    message = "Completed in " + nicer_timer(time.time() - tinit) + "."
    logprint(message)
    print("\n" + message)
    print(BOTTOM_LINE)
    is_working = False


################################################################################
def _message_from_args(args) -> str:
    return " ".join(str(arg) for arg in args)


################################################################################
def _json_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return _json_sequence(value)
    if isinstance(value, dict):
        return _json_mapping(value)
    return str(value)


################################################################################
def _json_sequence(value):
    return [_json_value(item) for item in value]


################################################################################
def _json_mapping(value):
    return {str(key): _json_value(item) for key, item in value.items()}


################################################################################
def human_print(num, suffix=""):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
    return "{:.1f}{}{}".format(num, "Y", suffix)


################################################################################
def nicer_timer(elapsed):
    out_string = ""
    hours = elapsed // 3600
    if hours:
        elapsed -= 3600 * hours
        out_string += str(int(hours)) + "h"
    minutes = elapsed // 60
    if hours or minutes:
        elapsed -= 60 * minutes
        out_string += str(int(minutes)) + "m"
    elapsed = f"{elapsed:.2f}" if not out_string else int(elapsed)
    out_string += str(elapsed) + "sec"
    return out_string
