"""Bounded whole-image color corrections derived from edge statistics."""

from dataclasses import dataclass

import numpy
from PIL import Image

from O4_Srgb_Color import linear_to_srgb_array, srgb_to_linear_array


MIN_EXPOSURE_SCALE = 0.85
MAX_EXPOSURE_SCALE = 1.18
MIN_CHANNEL_SCALE = 0.88
MAX_CHANNEL_SCALE = 1.14
DEFAULT_CORRECTION_STRENGTH = 0.65
_EPSILON = 1e-8


@dataclass(frozen=True)
class ColorCorrection:
    """Bounded whole-image exposure and chroma correction."""

    exposure_scale: float
    channel_scales: tuple[float, float, float]
    strength: float

    @classmethod
    def identity(cls) -> "ColorCorrection":
        return cls(
            exposure_scale=1.0,
            channel_scales=(1.0, 1.0, 1.0),
            strength=0.0,
        )

    def is_identity(self) -> bool:
        return self.strength <= 0.0 or (
            self.exposure_scale == 1.0 and self.channel_scales == (1.0, 1.0, 1.0)
        )


def derive_color_correction(edge_pairs) -> ColorCorrection:
    """Derive one conservative correction from target/neighbor edge pairs."""

    pairs = list(edge_pairs)
    if not pairs:
        return ColorCorrection.identity()

    target_rgb, target_luminance = _weighted_means(
        [target for target, _neighbor in pairs]
    )
    neighbor_rgb, neighbor_luminance = _weighted_means(
        [neighbor for _target, neighbor in pairs]
    )

    exposure_scale = _clamp(
        _safe_ratio(neighbor_luminance, target_luminance),
        MIN_EXPOSURE_SCALE,
        MAX_EXPOSURE_SCALE,
    )
    target_chroma = target_rgb / max(target_luminance, _EPSILON)
    neighbor_chroma = neighbor_rgb / max(neighbor_luminance, _EPSILON)
    channel_scales = numpy.clip(
        neighbor_chroma / numpy.maximum(target_chroma, _EPSILON),
        MIN_CHANNEL_SCALE,
        MAX_CHANNEL_SCALE,
    )

    return ColorCorrection(
        exposure_scale=float(exposure_scale),
        channel_scales=(
            float(channel_scales[0]),
            float(channel_scales[1]),
            float(channel_scales[2]),
        ),
        strength=DEFAULT_CORRECTION_STRENGTH,
    )


def apply_color_correction(image, correction: ColorCorrection):
    """Apply a bounded correction to the whole image in linear light."""

    rgb = image.convert("RGB")
    if correction.is_identity():
        return rgb.copy()

    linear = srgb_to_linear_array(numpy.asarray(rgb, dtype=numpy.uint8))
    scales = correction.exposure_scale * numpy.array(
        correction.channel_scales, dtype=numpy.float64
    )
    corrected = numpy.clip(linear * scales, 0.0, 1.0)
    strength = _clamp(correction.strength, 0.0, 1.0)
    blended = linear * (1 - strength) + corrected * strength
    return Image.fromarray(linear_to_srgb_array(blended), "RGB")


def _weighted_means(stats_list):
    stats_items = list(stats_list)
    total_pixels = sum(stats.pixel_count for stats in stats_items)
    if total_pixels <= 0:
        return numpy.ones(3, dtype=numpy.float64), 1.0

    return (
        _weighted_rgb_mean(stats_items, total_pixels),
        _weighted_luminance_mean(stats_items, total_pixels),
    )


def _weighted_rgb_mean(stats_items, total_pixels):
    total = numpy.zeros(3, dtype=numpy.float64)
    for stats in stats_items:
        total += numpy.array(stats.mean_rgb, dtype=numpy.float64) * stats.pixel_count
    return total / total_pixels


def _weighted_luminance_mean(stats_items, total_pixels):
    total = sum(stats.mean_luminance * stats.pixel_count for stats in stats_items)
    return float(total / total_pixels)


def _safe_ratio(numerator, denominator):
    if denominator <= _EPSILON:
        return 1.0
    return numerator / denominator


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))
