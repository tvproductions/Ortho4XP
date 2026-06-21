"""Edge seam-risk metric for provider scoring."""

from __future__ import annotations

import numpy

from O4_Provider_Score_Sampling import luminance


def seam_risk_score(sample: numpy.ndarray) -> float:
    luma = luminance(sample)
    band = max(1, min(luma.shape) // 16)
    edge_means = _luminance_edge_means(luma, band)
    edge_delta = max(edge_means) - min(edge_means)
    interior_mean = _interior_luminance_mean(luma, band)
    interior_delta = max(abs(mean - interior_mean) for mean in edge_means)
    return max(0.0, max(edge_delta, interior_delta) - 12.0)


def _luminance_edge_means(luma: numpy.ndarray, band: int) -> list[float]:
    return [
        float(numpy.mean(luma[:, :band])),
        float(numpy.mean(luma[:, -band:])),
        float(numpy.mean(luma[:band, :])),
        float(numpy.mean(luma[-band:, :])),
    ]


def _interior_luminance_mean(luma: numpy.ndarray, band: int) -> float:
    interior = luma[band:-band, band:-band]
    if interior.size == 0:
        return float(numpy.mean(luma))
    return float(numpy.mean(interior))
