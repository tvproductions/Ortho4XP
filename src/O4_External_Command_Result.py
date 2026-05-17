from dataclasses import dataclass


CommandOutcome = tuple[int, str, str]


@dataclass(frozen=True)
class ExternalCommandResult:
    tool_name: str
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    ok: bool
    error_summary: str


def make_result(
    tool_name: str,
    command: list[str],
    outcome: CommandOutcome,
) -> ExternalCommandResult:
    returncode, stdout, stderr = outcome
    return ExternalCommandResult(
        tool_name=tool_name,
        args=command,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        ok=returncode == 0,
        error_summary=_error_summary(returncode, stdout, stderr),
    )


def _error_summary(returncode: int, stdout: str, stderr: str) -> str:
    if returncode == 0:
        return ""
    detail = _first_nonempty_line(stderr) or _first_nonempty_line(stdout)
    if detail:
        return f"return code {returncode}: {detail[:240]}"
    return f"return code {returncode}"


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""
