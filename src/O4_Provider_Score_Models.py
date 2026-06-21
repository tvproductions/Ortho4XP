"""Data contracts for provider imagery scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TextureAttributes = tuple[int, int, int, str]


@dataclass(frozen=True)
class ProviderScoreMetrics:
    noise: float
    jpeg_compression: float
    clouds: float
    color_drift: float
    seam_risk: float

    def clamped(self) -> ProviderScoreMetrics:
        return ProviderScoreMetrics(
            noise=_clamp_metric(self.noise),
            jpeg_compression=_clamp_metric(self.jpeg_compression),
            clouds=_clamp_metric(self.clouds),
            color_drift=_clamp_metric(self.color_drift),
            seam_risk=_clamp_metric(self.seam_risk),
        )

    def to_context(self) -> dict[str, float]:
        return {
            "noise": round(self.noise, 2),
            "jpeg_compression": round(self.jpeg_compression, 2),
            "clouds": round(self.clouds, 2),
            "color_drift": round(self.color_drift, 2),
            "seam_risk": round(self.seam_risk, 2),
        }


@dataclass(frozen=True)
class ProviderScoreResult:
    provider_code: str
    texture_attributes: TextureAttributes
    metrics: ProviderScoreMetrics
    global_score: float
    quality_label: str

    @property
    def til_x_left(self) -> int:
        return self.texture_attributes[0]

    @property
    def til_y_top(self) -> int:
        return self.texture_attributes[1]

    @property
    def zoomlevel(self) -> int:
        return self.texture_attributes[2]

    def to_context(self) -> dict[str, Any]:
        return {
            "provider_code": self.provider_code,
            "tile_x": self.til_x_left,
            "tile_y": self.til_y_top,
            "zoomlevel": self.zoomlevel,
            "global_score": round(self.global_score, 2),
            "quality_label": self.quality_label,
            "metrics": self.metrics.to_context(),
        }


def _clamp_metric(value: float) -> float:
    return min(100.0, max(0.0, float(value)))
