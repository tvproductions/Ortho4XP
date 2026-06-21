"""Image sampling helpers for provider scoring."""

from __future__ import annotations

import numpy
from PIL import Image

import O4_Resampling_Policy as RP


def sample_rgb_array(image: Image.Image) -> numpy.ndarray:
    rgb = image.convert("RGB")
    max_side = max(rgb.size)
    if max_side <= 512:
        return numpy.asarray(rgb, dtype=numpy.float64)
    scale = 512 / max_side
    size = (max(1, round(rgb.size[0] * scale)), max(1, round(rgb.size[1] * scale)))
    return numpy.asarray(RP.resize_image("bilinear", rgb, size), dtype=numpy.float64)


def luminance(sample: numpy.ndarray) -> numpy.ndarray:
    return (
        sample[:, :, 0] * 0.2126 + sample[:, :, 1] * 0.7152 + sample[:, :, 2] * 0.0722
    )


def mean_of_arrays(*arrays: numpy.ndarray) -> float:
    values = [float(numpy.mean(array)) for array in arrays if array.size]
    if not values:
        return 0.0
    return sum(values) / len(values)
