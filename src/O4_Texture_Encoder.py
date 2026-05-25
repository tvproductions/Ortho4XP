import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from O4_External_Command_Result import ExternalCommandResult
import O4_Subprocess_Utils as SP
import O4_UI_Utils as UI


TextureCodec = Literal["bc1", "bc3"]
Sleep = Callable[[float], None]


@dataclass(frozen=True)
class TextureEncodeRequest:
    source_path: str
    output_path: str
    codec: TextureCodec
    display_name: str
    provider_code: str = ""
    til_x_left: int | None = None
    til_y_top: int | None = None
    zoomlevel: int | None = None
    max_attempts: int = 10


@dataclass(frozen=True)
class TextureEncodeResult:
    request: TextureEncodeRequest
    ok: bool
    attempts: int
    backend_name: str
    tool_name: str
    returncode: int
    error_summary: str


@dataclass(frozen=True)
class TextureConversionResult:
    ok: bool
    display_name: str
    provider_code: str = ""
    error_summary: str = ""
    encode_result: TextureEncodeResult | None = None

    @classmethod
    def success(
        cls, display_name: str, provider_code: str = ""
    ) -> "TextureConversionResult":
        return cls(ok=True, display_name=display_name, provider_code=provider_code)

    @classmethod
    def failure(
        cls,
        display_name: str,
        provider_code: str = "",
        error_summary: str = "",
    ) -> "TextureConversionResult":
        return cls(
            ok=False,
            display_name=display_name,
            provider_code=provider_code,
            error_summary=error_summary,
        )

    @classmethod
    def from_encode_result(
        cls, encode_result: TextureEncodeResult
    ) -> "TextureConversionResult":
        return cls(
            ok=encode_result.ok,
            display_name=encode_result.request.display_name,
            provider_code=encode_result.request.provider_code,
            error_summary=encode_result.error_summary,
            encode_result=encode_result,
        )


class TextureEncoderBackend:
    name = "abstract"

    def build_command(self, request: TextureEncodeRequest) -> list[str]:
        raise NotImplementedError

    def encode(self, request: TextureEncodeRequest) -> TextureEncodeResult:
        raise NotImplementedError


class NativeTextureEncoderBackend(TextureEncoderBackend):
    name = "native"

    def __init__(
        self,
        *,
        is_macos: bool | None = None,
        executable: str | None = None,
        run_external_command: Callable[..., ExternalCommandResult] | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        self.is_macos = sys.platform == "darwin" if is_macos is None else is_macos
        self.tool_name = (
            Path(executable).stem
            if executable is not None
            else "DDSTool"
            if self.is_macos
            else "nvcompress"
        )
        self.executable = executable or SP.resolve_tool(self.tool_name)
        self.run_external_command = run_external_command or SP.run_external_command
        self.sleep = sleep or time.sleep

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
        max_attempts = max(1, int(request.max_attempts))
        last_result = None

        for attempt in range(1, max_attempts + 1):
            last_result = self.run_external_command(command, tool_name=self.tool_name)
            if last_result.ok:
                break
            if attempt < max_attempts:
                UI.lvprint(
                    1,
                    "WARNING: texture encoding failed for",
                    request.display_name,
                    "- retrying.",
                    last_result.error_summary,
                )
                self.sleep(1)

        if last_result is None:
            raise RuntimeError("Texture encoding did not run")
        if not last_result.ok:
            UI.lvprint(
                1,
                "ERROR: texture encoding failed for",
                request.display_name,
                last_result.error_summary,
            )

        return TextureEncodeResult(
            request=request,
            ok=last_result.ok,
            attempts=attempt,
            backend_name=self.name,
            tool_name=last_result.tool_name,
            returncode=last_result.returncode,
            error_summary=last_result.error_summary,
        )


def encode_texture(
    request: TextureEncodeRequest, backend: TextureEncoderBackend | None = None
) -> TextureEncodeResult:
    encoder = backend or NativeTextureEncoderBackend()
    return encoder.encode(request)


def coerce_conversion_result(
    result: TextureConversionResult | TextureEncodeResult | object,
    display_name: str,
    provider_code: str = "",
) -> TextureConversionResult:
    if isinstance(result, TextureConversionResult):
        return result
    if isinstance(result, TextureEncodeResult):
        return TextureConversionResult.from_encode_result(result)
    if result is False:
        return TextureConversionResult.failure(
            display_name,
            provider_code,
            "conversion returned False",
        )
    return TextureConversionResult.success(display_name, provider_code)


def _validate_codec(codec: str) -> None:
    if codec not in ("bc1", "bc3"):
        raise ValueError(f"Unsupported texture codec: {codec}")


def _ddstool_codec_flag(codec: TextureCodec) -> str:
    if codec == "bc1":
        return "--png2dxt1"
    if codec == "bc3":
        return "--png2dxt5"
    raise ValueError(f"Unsupported texture codec: {codec}")
