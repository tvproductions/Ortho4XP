import os
from collections.abc import Callable, Sequence
from pathlib import Path

import O4_Subprocess_Runtime as RUNTIME
import O4_UI_Utils as UI
from O4_External_Command_Result import ExternalCommandResult, make_result
from O4_External_Tool_Paths import resolve_tool

CommandArg = str | os.PathLike[str]
StdoutHandler = Callable[[str], None]


def run_external_tool(
    tool_name: str,
    args: Sequence[CommandArg] = (),
    *,
    executable: CommandArg | None = None,
    stream_stdout: bool = False,
    stdout_handler: StdoutHandler | None = None,
) -> ExternalCommandResult:
    """Run an external Ortho4XP tool with shared env, capture, and logging."""
    command = [
        str(Path(executable) if isinstance(executable, os.PathLike) else executable)
        if executable is not None
        else resolve_tool(tool_name),
        *[str(arg) for arg in args],
    ]
    _log_command_start(tool_name, command)
    try:
        if stream_stdout:
            result = _run_streamed(tool_name, command, stdout_handler)
        else:
            result = _run_captured(tool_name, command)
    except OSError as exc:
        result = make_result(tool_name, command, (127, "", str(exc)))
    _log_command_complete(result)
    if not result.ok:
        UI.lvprint(1, "External command failed:", result.error_summary)
    return result


def run_external_command(
    command: Sequence[CommandArg],
    *,
    tool_name: str | None = None,
    stream_stdout: bool = False,
    stdout_handler: StdoutHandler | None = None,
) -> ExternalCommandResult:
    executable = command[0]
    inferred_tool_name = tool_name or Path(str(executable)).stem
    return run_external_tool(
        inferred_tool_name,
        command[1:],
        executable=executable,
        stream_stdout=stream_stdout,
        stdout_handler=stdout_handler,
    )


def _run_captured(tool_name: str, command: list[str]) -> ExternalCommandResult:
    return make_result(tool_name, command, RUNTIME.run_captured(command))


def _run_streamed(
    tool_name: str, command: list[str], stdout_handler: StdoutHandler | None
) -> ExternalCommandResult:
    return make_result(
        tool_name, command, RUNTIME.run_streamed(command, stdout_handler)
    )


def _format_command(command: Sequence[str]) -> str:
    return " ".join(command)


def _log_command_start(tool_name: str, command: list[str]) -> None:
    UI.log_event(
        "External command start",
        level="INFO",
        context=_command_context(tool_name, command, command_text=True),
    )


def _log_command_complete(result: ExternalCommandResult) -> None:
    UI.log_event(
        "External command complete",
        level="INFO" if result.ok else "ERROR",
        context=_result_context(result),
        error_type=None if result.ok else "ExternalCommandError",
        error_summary=result.error_summary or None,
    )


def _command_context(
    tool_name: str, command: list[str], *, command_text: bool = False
) -> dict[str, object]:
    context: dict[str, object] = {"tool_name": tool_name, "command": command}
    if command_text:
        context["command_text"] = _format_command(command)
    return context


def _result_context(result: ExternalCommandResult) -> dict[str, object]:
    context = _command_context(result.tool_name, result.args)
    context["returncode"] = result.returncode
    context["ok"] = result.ok
    return context
