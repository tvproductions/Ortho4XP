"""Edge color-drift metric for provider scoring."""

from __future__ import annotations

import itertools

import numpy

from O4_Provider_Score_Edge_Data import edge_arrays
from O4_Provider_Score_Sampling import luminance


def color_drift_score(sample: numpy.ndarray) -> float:
    luma = luminance(sample)
    edge_means = _edge_rgb_means(sample)
    if len(edge_means) < 2:
        return 0.0
    luma_risk = _edge_luminance_risk(edge_means, luma)
    color_risk = _maximum_edge_color_delta(edge_means) / 2.55
    return max(0.0, max(luma_risk, color_risk) - 15.0)


def _edge_rgb_means(sample: numpy.ndarray) -> list[numpy.ndarray]:
    band = max(1, min(sample.shape[0], sample.shape[1]) // 16)
    return [edge.reshape(-1, 3).mean(axis=0) for edge in edge_arrays(sample, band)]


def _edge_luminance_risk(edge_means: list[numpy.ndarray], luma: numpy.ndarray) -> float:
    edge_luma = [_rgb_luminance(mean) for mean in edge_means]
    luma_delta = max(edge_luma) - min(edge_luma)
    scene_luma = max(1.0, float(numpy.mean(luma)))
    return 100 * luma_delta / scene_luma


def _maximum_edge_color_delta(edge_means: list[numpy.ndarray]) -> float:
    return max(
        float(numpy.linalg.norm(left - right))
        for left, right in itertools.combinations(edge_means, 2)
    )


def _rgb_luminance(rgb: numpy.ndarray) -> float:
    return float(rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722)
