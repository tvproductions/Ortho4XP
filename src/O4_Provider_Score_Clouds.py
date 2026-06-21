"""Cloud proxy metric for provider scoring."""

from __future__ import annotations

import numpy


def cloud_score(sample: numpy.ndarray) -> float:
    max_channel = numpy.max(sample, axis=2)
    min_channel = numpy.min(sample, axis=2)
    saturation = max_channel - min_channel
    bright_low_saturation = (max_channel >= 220) & (saturation <= 35)
    return float(numpy.mean(bright_low_saturation) * 100)
