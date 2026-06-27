"""Shared RGB channel extraction for provider scoring."""

from __future__ import annotations

from dataclasses import dataclass

import numpy


@dataclass(frozen=True)
class CloudChannels:
    blue: numpy.ndarray
    green: numpy.ndarray
    luminance: numpy.ndarray
    red: numpy.ndarray
    saturation: numpy.ndarray


def channel_data(sample: numpy.ndarray) -> CloudChannels:
    rgb = sample[:, :, :3].astype(numpy.float64)
    red = rgb[:, :, 0]
    green = rgb[:, :, 1]
    blue = rgb[:, :, 2]
    saturation = numpy.max(rgb, axis=2) - numpy.min(rgb, axis=2)
    luminance = (red + green + blue) / 3.0
    return CloudChannels(
        blue=blue,
        green=green,
        luminance=luminance,
        red=red,
        saturation=saturation,
    )
