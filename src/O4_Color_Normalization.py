"""sRGB edge-statistics color normalization for completed Ortho4XP textures.

The functions in this module intentionally operate on finished 4096px
orthophotos rather than provider download tiles.  Edge bands are sampled from
the target image and any already-cached cardinal neighbors, converted from sRGB
into linear light, reduced to mean RGB and luminance statistics, and then used
to derive one bounded global correction for the target image.

This is not pixel blending.  Neighbor imagery never replaces target pixels; it
only supplies the exposure and chroma reference for a conservative adjustment.
The correction is clamped and blended back with the original linear-light image
so bad neighbors or extreme provider differences cannot dominate the texture.
"""

from dataclasses import dataclass
from typing import Literal

import numpy

from O4_Color_Correction import (
    DEFAULT_CORRECTION_STRENGTH as DEFAULT_CORRECTION_STRENGTH,
)
from O4_Color_Correction import (
    MAX_CHANNEL_SCALE as MAX_CHANNEL_SCALE,
)
from O4_Color_Correction import (
    MAX_EXPOSURE_SCALE as MAX_EXPOSURE_SCALE,
)
from O4_Color_Correction import (
    MIN_CHANNEL_SCALE as MIN_CHANNEL_SCALE,
)
from O4_Color_Correction import (
    MIN_EXPOSURE_SCALE as MIN_EXPOSURE_SCALE,
)
from O4_Color_Correction import (
    ColorCorrection as ColorCorrection,
)
from O4_Color_Correction import (
    apply_color_correction,
    derive_color_correction,
)
from O4_Srgb_Color import (
    linear_to_srgb_array as linear_to_srgb_array,
)
from O4_Srgb_Color import (
    srgb_to_linear_array as srgb_to_linear_array,
)

EdgeName = Literal["north", "south", "east", "west"]

EDGE_BAND_PIXELS = 32
_LUMINANCE_WEIGHTS = numpy.array([0.2126, 0.7152, 0.0722], dtype=numpy.float64)

OPPOSITE_EDGE: dict[EdgeName, EdgeName] = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}
_EDGE_ARRAY_SLICES = {
    "north": lambda band: (slice(0, band), slice(None), slice(None)),
    "south": lambda band: (slice(-band, None), slice(None), slice(None)),
    "west": lambda band: (slice(None), slice(0, band), slice(None)),
    "east": lambda band: (slice(None), slice(-band, None), slice(None)),
}


@dataclass(frozen=True)
class EdgeStats:
    """Linear-light statistics for one sampled edge band."""

    mean_rgb: tuple[float, float, float]
    mean_luminance: float
    pixel_count: int


def extract_edge_pixels(image, edge: EdgeName, band_width=EDGE_BAND_PIXELS):
    """Return a copied RGB pixel band for one cardinal edge."""

    if edge not in OPPOSITE_EDGE:
        raise ValueError(f"unsupported edge: {edge}")
    if band_width < 1:
        raise ValueError("band_width must be at least 1")

    rgb = image.convert("RGB")
    pixels = numpy.asarray(rgb, dtype=numpy.uint8)
    height, width = pixels.shape[:2]
    axis_size = height if edge in ("north", "south") else width
    band = min(int(band_width), axis_size)
    return pixels[_EDGE_ARRAY_SLICES[edge](band)].copy()


def edge_stats(image, edge: EdgeName, band_width=EDGE_BAND_PIXELS) -> EdgeStats:
    """Compute linear-light mean RGB and luminance for one image edge."""

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


def normalize_image_with_neighbors(image, neighbor_images, band_width=EDGE_BAND_PIXELS):
    """Normalize one image using same-sized cardinal neighbor images."""

    target = image.convert("RGB")
    edge_pairs = [
        pair
        for edge, neighbor_image in neighbor_images.items()
        if (pair := _edge_stats_pair(target, edge, neighbor_image, band_width))
        is not None
    ]
    if not edge_pairs:
        return target.copy()
    return apply_color_correction(target, derive_color_correction(edge_pairs))


def _edge_stats_pair(target, edge, neighbor_image, band_width):
    if edge not in OPPOSITE_EDGE:
        return None
    try:
        neighbor = neighbor_image.convert("RGB")
    except (AttributeError, OSError, ValueError):
        return None
    if neighbor.size != target.size:
        return None
    return (
        edge_stats(target, edge, band_width),
        edge_stats(neighbor, OPPOSITE_EDGE[edge], band_width),
    )
