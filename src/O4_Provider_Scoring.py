"""Provider imagery quality scoring for downloaded texture images."""

from __future__ import annotations

from PIL import Image

import O4_UI_Utils as UI
from O4_Provider_Score_Metrics import compute_provider_score_metrics
from O4_Provider_Score_Models import (
    ProviderScoreMetrics,
    ProviderScoreResult,
    TextureAttributes,
)
from O4_Texture_Source import TextureSource


def score_provider_image(
    provider_code: str,
    texture_attributes: TextureAttributes,
    image: Image.Image,
) -> ProviderScoreResult:
    metrics = compute_provider_score_metrics(image)
    return provider_score_from_metrics(provider_code, texture_attributes, metrics)


def provider_score_from_metrics(
    provider_code: str,
    texture_attributes: TextureAttributes,
    metrics: ProviderScoreMetrics,
) -> ProviderScoreResult:
    clamped = metrics.clamped()
    artifact_risk = (
        clamped.noise
        + clamped.jpeg_compression
        + clamped.clouds
        + clamped.color_drift
        + clamped.seam_risk
    ) / 5
    global_score = round(100 - artifact_risk, 2)
    return ProviderScoreResult(
        provider_code=provider_code,
        texture_attributes=texture_attributes,
        metrics=clamped,
        global_score=global_score,
        quality_label=_quality_label(global_score),
    )


def log_provider_score(result: ProviderScoreResult) -> None:
    UI.log_event("Provider imagery score", level="INFO", context=result.to_context())


def score_and_log_provider_image(
    provider_code: str,
    texture_attributes: TextureAttributes,
    image: Image.Image,
) -> ProviderScoreResult:
    result = score_provider_image(provider_code, texture_attributes, image)
    log_provider_score(result)
    return result


def scored_value[T](
    value: T, texture_attributes: TextureAttributes, image: Image.Image
) -> T:
    score_and_log_provider_image(texture_attributes[3], texture_attributes, image)
    return value


def texture_source(
    tile: object,
    texture_attributes: TextureAttributes,
    image: Image.Image,
    cache: tuple[str | None, bool],
) -> TextureSource:
    score_and_log_provider_image(texture_attributes[3], texture_attributes, image)
    cache_path, wrote_cache = cache
    return TextureSource(tile, texture_attributes, image, cache_path, wrote_cache)


def _quality_label(global_score: float) -> str:
    if global_score >= 90:
        return "excellent"
    if global_score >= 75:
        return "good"
    if global_score >= 60:
        return "fair"
    return "poor"
