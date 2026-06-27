"""Shared cloud-score helpers for provider scoring."""

from __future__ import annotations

from dataclasses import dataclass

import numpy

from O4_Provider_Score_Channel_Data import CloudChannels
from O4_Provider_Score_Sampling import local_luminance_std


@dataclass(frozen=True)
class CloudMasks:
    blue_sky: numpy.ndarray
    cloud: numpy.ndarray
    dense: numpy.ndarray
    veil: numpy.ndarray


def cloud_masks(channels: CloudChannels, block_size: int = 4) -> CloudMasks:
    dense_cloud = (channels.luminance >= 220) & (channels.saturation <= 28)
    local_std = local_luminance_std(channels.luminance, block_size)
    veil = (
        (channels.luminance >= 180) & (channels.saturation <= 38) & (local_std <= 8.0)
    )
    blue_sky = (
        (channels.blue > channels.red + 10)
        & (channels.blue > channels.green + 5)
        & (channels.luminance >= 145)
    )
    return CloudMasks(
        blue_sky=blue_sky,
        cloud=(dense_cloud | veil) & ~blue_sky,
        dense=dense_cloud & ~blue_sky,
        veil=veil & ~blue_sky,
    )


def coverage_percent(mask: numpy.ndarray) -> float:
    return float(numpy.mean(mask) * 100)
