import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from O4_External_Command_Result import ExternalCommandResult
from O4_Texture_Models import (
    TextureCodec,
    TextureEncodeRequest,
    TextureEncodeResult,
    TextureEncoderBackend,
)
import O4_Subprocess_Utils as SP
import O4_UI_Utils as UI


# Native backend policy:
# - Keep platform tool selection isolated from the public encoder facade.
# - Keep retry timing injectable so unit tests never sleep.
# - Keep command construction explicit for future CUDA/Vulkan backends to mirror.
Sleep = Callable[[float], None]


@dataclass(frozen=True)
class TextureEncoderRuntime:
    run_external_command: Callable[..., ExternalCommandResult]
    sleep: Sleep


class NativeTextureEncoderBackend(TextureEncoderBackend):
    name = "native"

    def __init__(
        self,
        *,
        is_macos: bool | None = None,
        executable: str | None = None,
        runtime: TextureEncoderRuntime | None = None,
    ) -> None:
        runtime = runtime or _default_runtime()
        self.is_macos = sys.platform == "darwin" if is_macos is None else is_macos
        self.tool_name = (
            Path(executable).stem
            if executable is not None
            else "DDSTool"
            if self.is_macos
            else "nvcompress"
        )
        self.executable = executable or SP.resolve_tool(self.tool_name)
        self.run_external_command = runtime.run_external_command
        self.sleep = runtime.sleep

    def build_command(self, request: TextureEncodeRequest) -> list[str]:
        _validate_codec(request.codec)
        if self.is_macos:
            return [
                self.executable,
                _ddstool_codec_flag(request.codec),
                request.source_path,
                request.output_path,
            ]
        return [
            self.executable,
            f"-{request.codec}",
            "-fast",
            request.source_path,
            request.output_path,
        ]

    def encode(self, request: TextureEncodeRequest) -> TextureEncodeResult:
        command = self.build_command(request)
        attempts, last_result = self._run_encode_attempts(request, command)

        if not last_result.ok:
            UI.lvprint(
                1,
                "ERROR: texture encoding failed for",
                request.display_name,
                last_result.error_summary,
            )

        return TextureEncodeResult(
            request,
            last_result.ok,
            attempts,
            self.name,
            last_result.tool_name,
            last_result.returncode,
            last_result.error_summary,
        )

    def _run_encode_attempts(self, request, command):
        max_attempts = max(1, int(request.max_attempts))
        last_result = None

        for attempt in range(1, max_attempts + 1):
            last_result = self.run_external_command(command, tool_name=self.tool_name)
            if last_result.ok:
                return attempt, last_result
            self._retry_after_failure(request, last_result, attempt < max_attempts)

        if last_result is None:
            raise RuntimeError("Texture encoding did not run")
        return attempt, last_result

    def _retry_after_failure(self, request, result, should_retry):
        if not should_retry:
            return
        UI.lvprint(
            1,
            "WARNING: texture encoding failed for",
            request.display_name,
            "- retrying.",
            result.error_summary,
        )
        self.sleep(1)


def _default_runtime():
    return TextureEncoderRuntime(
        run_external_command=SP.run_external_command,
        sleep=time.sleep,
    )


def _validate_codec(codec: str) -> None:
    if codec not in ("bc1", "bc3"):
        raise ValueError(f"Unsupported texture codec: {codec}")


def _ddstool_codec_flag(codec: TextureCodec) -> str:
    if codec == "bc1":
        return "--png2dxt1"
    if codec == "bc3":
        return "--png2dxt5"
    raise ValueError(f"Unsupported texture codec: {codec}")
