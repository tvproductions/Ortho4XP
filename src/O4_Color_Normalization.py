from dataclasses import dataclass
from typing import Literal

import numpy
from PIL import Image


EdgeName = Literal["north", "south", "east", "west"]

EDGE_BAND_PIXELS = 32
MIN_EXPOSURE_SCALE = 0.85
MAX_EXPOSURE_SCALE = 1.18
MIN_CHANNEL_SCALE = 0.88
MAX_CHANNEL_SCALE = 1.14
DEFAULT_CORRECTION_STRENGTH = 0.65
_EPSILON = 1e-8
_LUMINANCE_WEIGHTS = numpy.array([0.2126, 0.7152, 0.0722], dtype=numpy.float64)

OPPOSITE_EDGE: dict[EdgeName, EdgeName] = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}


@dataclass(frozen=True)
class EdgeStats:
    mean_rgb: tuple[float, float, float]
    mean_luminance: float
    pixel_count: int


@dataclass(frozen=True)
class ColorCorrection:
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


def srgb_to_linear_array(values):
    srgb = numpy.asarray(values, dtype=numpy.float64) / 255.0
    return numpy.where(
        srgb <= 0.04045,
        srgb / 12.92,
        numpy.power((srgb + 0.055) / 1.055, 2.4),
    )


def linear_to_srgb_array(values):
    linear = numpy.clip(numpy.asarray(values, dtype=numpy.float64), 0.0, 1.0)
    srgb = numpy.where(
        linear <= 0.0031308,
        linear * 12.92,
        1.055 * numpy.power(linear, 1 / 2.4) - 0.055,
    )
    return numpy.clip(numpy.rint(srgb * 255), 0, 255).astype(numpy.uint8)


def extract_edge_pixels(image, edge: EdgeName, band_width=EDGE_BAND_PIXELS):
    if edge not in OPPOSITE_EDGE:
        raise ValueError(f"unsupported edge: {edge}")
    if band_width < 1:
        raise ValueError("band_width must be at least 1")

    rgb = image.convert("RGB")
    pixels = numpy.asarray(rgb, dtype=numpy.uint8)
    height, width = pixels.shape[:2]

    if edge in ("north", "south"):
        band = min(int(band_width), height)
        if edge == "north":
            return pixels[:band, :, :].copy()
        return pixels[-band:, :, :].copy()

    band = min(int(band_width), width)
    if edge == "west":
        return pixels[:, :band, :].copy()
    return pixels[:, -band:, :].copy()


def edge_stats(image, edge: EdgeName, band_width=EDGE_BAND_PIXELS) -> EdgeStats:
    pixels = extract_edge_pixels(image, edge, band_width)
    linear = srgb_to_linear_array(pixels).reshape((-1, 3))
    mean_rgb_array = linear.mean(axis=0)
    mean_luminance = float(mean_rgb_array.dot(_LUMINANCE_WEIGHTS))
    return EdgeStats(
        mean_rgb=(
            float(mean_rgb_array[0]),
            float(mean_rgb_array[1]),
            float(mean_rgb_array[2]),
        ),
        mean_luminance=mean_luminance,
        pixel_count=int(linear.shape[0]),
    )


def derive_color_correction(edge_pairs) -> ColorCorrection:
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


def normalize_image_with_neighbors(image, neighbor_images, band_width=EDGE_BAND_PIXELS):
    target = image.convert("RGB")
    edge_pairs = []
    for edge, neighbor_image in neighbor_images.items():
        if edge not in OPPOSITE_EDGE:
            continue
        try:
            neighbor = neighbor_image.convert("RGB")
        except (AttributeError, OSError, ValueError):
            continue
        if neighbor.size != target.size:
            continue
        edge_pairs.append(
            (
                edge_stats(target, edge, band_width),
                edge_stats(neighbor, OPPOSITE_EDGE[edge], band_width),
            )
        )
    if not edge_pairs:
        return target.copy()
    return apply_color_correction(target, derive_color_correction(edge_pairs))


def _weighted_means(stats_list):
    total_pixels = sum(stats.pixel_count for stats in stats_list)
    if total_pixels <= 0:
        return numpy.ones(3, dtype=numpy.float64), 1.0

    mean_rgb = (
        sum(
            numpy.array(stats.mean_rgb, dtype=numpy.float64) * stats.pixel_count
            for stats in stats_list
        )
        / total_pixels
    )
    mean_luminance = (
        sum(stats.mean_luminance * stats.pixel_count for stats in stats_list)
        / total_pixels
    )
    return mean_rgb, float(mean_luminance)


def _safe_ratio(numerator, denominator):
    if denominator <= _EPSILON:
        return 1.0
    return numerator / denominator


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))
