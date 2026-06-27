"""Cloud and haze proxy metrics for provider scoring."""

from __future__ import annotations

import numpy

from O4_Provider_Score_Channel_Data import channel_data
from O4_Provider_Score_Cloud_Data import cloud_masks, coverage_percent


def cloud_score(sample: numpy.ndarray) -> float:
    score, _details = cloud_score_details(sample)
    return score


def cloud_score_details(sample: numpy.ndarray) -> tuple[float, dict[str, float]]:
    if sample.size == 0 or sample.ndim != 3 or sample.shape[2] < 3:
        return 0.0, _cloud_details(0.0, 0.0, 0.0, 0.0)

    masks = cloud_masks(channel_data(sample))
    cloud_coverage = coverage_percent(masks.cloud)
    dense_coverage = coverage_percent(masks.dense)
    veil_coverage = coverage_percent(masks.veil)
    blue_sky_coverage = coverage_percent(masks.blue_sky)
    risk = min(100.0, max(0.0, (cloud_coverage - 5.0) * 2.1))
    return risk, _cloud_details(
        cloud_coverage,
        dense_coverage,
        veil_coverage,
        blue_sky_coverage,
    )


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
