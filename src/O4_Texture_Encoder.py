from O4_Native_Texture_Encoder import NativeTextureEncoderBackend, TextureEncoderRuntime
from O4_Texture_Models import (
    TextureCodec,
    TextureConversionResult,
    TextureEncodeRequest,
    TextureEncodeResult,
    TextureEncoderBackend,
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
