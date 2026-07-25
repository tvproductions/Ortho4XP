from dataclasses import dataclass
from typing import Literal

# Texture model policy:
# - Data classes stay backend-neutral so CPU and GPU encoders share contracts.
# - Conversion results preserve legacy truthy behavior at the facade boundary.
# - Request metadata carries provider/tile context for summaries and diagnostics.
TextureCodec = Literal["bc1", "bc3"]


@dataclass(frozen=True)
class TextureCleanupPlan:
    always_paths: tuple[str, ...] = ()
    success_paths: tuple[str, ...] = ()


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
        return cls(True, display_name, provider_code)

    @classmethod
    def failure(
        cls,
        display_name: str,
        provider_code: str = "",
        error_summary: str = "",
    ) -> "TextureConversionResult":
        return cls(False, display_name, provider_code, error_summary)

    @classmethod
    def from_encode_result(
        cls, encode_result: TextureEncodeResult
    ) -> "TextureConversionResult":
        request = encode_result.request
        return cls(
            encode_result.ok,
            request.display_name,
            request.provider_code,
            encode_result.error_summary,
            encode_result,
        )


class TextureEncoderBackend:
    name = "abstract"

    def build_command(self, request: TextureEncodeRequest) -> list[str]:
        raise NotImplementedError

    def encode(self, request: TextureEncodeRequest) -> TextureEncodeResult:
        raise NotImplementedError
