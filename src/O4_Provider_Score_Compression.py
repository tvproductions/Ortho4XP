"""Noise and block-artifact metrics for provider scoring."""

from __future__ import annotations

import numpy

from O4_Provider_Score_Sampling import luminance, mean_of_arrays


def noise_score(sample: numpy.ndarray) -> float:
    luma = luminance(sample)
    horizontal = numpy.abs(numpy.diff(luma, axis=1))
    vertical = numpy.abs(numpy.diff(luma, axis=0))
    mean_delta = mean_of_arrays(horizontal, vertical)
    return max(0.0, (mean_delta - 4.0) * 1.8)


def jpeg_compression_score(luma: numpy.ndarray) -> float:
    height, width = luma.shape
    if height < 16 or width < 16:
        return 0.0
    vertical_boundary = numpy.abs(luma[:, 8::8] - luma[:, 7:-1:8])
    horizontal_boundary = numpy.abs(luma[8::8, :] - luma[7:-1:8, :])
    vertical_inside = numpy.abs(luma[:, 1::8] - luma[:, :-1:8])
    horizontal_inside = numpy.abs(luma[1::8, :] - luma[:-1:8, :])
    boundary = mean_of_arrays(vertical_boundary, horizontal_boundary)
    inside = mean_of_arrays(vertical_inside, horizontal_inside)
    return max(0.0, (boundary - inside - 2.0) * 1.8)
