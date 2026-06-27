"""Cloud and haze proxy metrics for provider scoring."""

from __future__ import annotations

import numpy


def cloud_score(sample: numpy.ndarray) -> float:
    score, _details = cloud_score_details(sample)
    return score


def cloud_score_details(sample: numpy.ndarray) -> tuple[float, dict[str, float]]:
    if sample.size == 0 or sample.ndim != 3 or sample.shape[2] < 3:
        return 0.0, _cloud_details(0.0, 0.0, 0.0, 0.0)

    rgb = sample[:, :, :3].astype(numpy.float64)
    red = rgb[:, :, 0]
    green = rgb[:, :, 1]
    blue = rgb[:, :, 2]
    max_channel = numpy.max(rgb, axis=2)
    min_channel = numpy.min(rgb, axis=2)
    luminance = (red + green + blue) / 3.0
    saturation = max_channel - min_channel

    dense_cloud = (luminance >= 220) & (saturation <= 28)
    local_std = _local_luminance_std(luminance, block_size=4)
    veil = (luminance >= 180) & (saturation <= 38) & (local_std <= 8.0)
    blue_sky = (blue > red + 10) & (blue > green + 5) & (luminance >= 145)
    cloud_mask = (dense_cloud | veil) & ~blue_sky

    cloud_coverage = float(numpy.mean(cloud_mask) * 100)
    dense_coverage = float(numpy.mean(dense_cloud & ~blue_sky) * 100)
    veil_coverage = float(numpy.mean(veil & ~blue_sky) * 100)
    blue_sky_coverage = float(numpy.mean(blue_sky) * 100)
    risk = min(100.0, max(0.0, (cloud_coverage - 5.0) * 2.1))
    return risk, _cloud_details(
        cloud_coverage,
        dense_coverage,
        veil_coverage,
        blue_sky_coverage,
    )


def _local_luminance_std(luminance: numpy.ndarray, block_size: int) -> numpy.ndarray:
    height, width = luminance.shape
    std_map = numpy.zeros((height, width), dtype=numpy.float64)
    for y_start in range(0, height, block_size):
        y_end = min(height, y_start + block_size)
        for x_start in range(0, width, block_size):
            x_end = min(width, x_start + block_size)
            block = luminance[y_start:y_end, x_start:x_end]
            std_map[y_start:y_end, x_start:x_end] = float(numpy.std(block))
    return std_map


def _cloud_details(
    cloud_coverage: float,
    dense_coverage: float,
    veil_coverage: float,
    blue_sky_coverage: float,
) -> dict[str, float]:
    return {
        "cloud_coverage_pct": round(cloud_coverage, 2),
        "dense_cloud_pct": round(dense_coverage, 2),
        "veil_pct": round(veil_coverage, 2),
        "blue_sky_excluded_pct": round(blue_sky_coverage, 2),
    }
