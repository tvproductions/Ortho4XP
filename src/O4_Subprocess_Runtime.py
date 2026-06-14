import subprocess
from collections.abc import Callable

import O4_UI_Utils as UI

CommandOutcome = tuple[int, str, str]
StdoutHandler = Callable[[str], None]


def run_captured(command: list[str]) -> CommandOutcome:
    completed = subprocess.run(  # noqa: S603
        command,
        check=False,
        capture_output=True,
        text=True,
        env=UI.subprocess_env(),
    )
    return (completed.returncode, completed.stdout, completed.stderr)


def run_streamed(
    command: list[str], stdout_handler: StdoutHandler | None
) -> CommandOutcome:
    stdout_chunks: list[str] = []
    with subprocess.Popen(  # noqa: S603
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        env=UI.subprocess_env(),
    ) as process:
        if process.stdout is None:
            raise RuntimeError("streamed subprocess stdout pipe was not created")
        while True:
            line = process.stdout.readline()
            if not line:
                break
            decoded = _decode_output(line).rstrip("\r\n")
            stdout_chunks.append(decoded + "\n")
            if stdout_handler is not None:
                stdout_handler(decoded)
            else:
                print(decoded)
        stderr_bytes = process.stderr.read() if process.stderr is not None else b""
        returncode = process.wait()
    return (returncode, "".join(stdout_chunks), _decode_output(stderr_bytes))


def _decode_output(output: bytes) -> str:
    return output.decode("utf-8", errors="replace")
