"""Metric orchestration for provider imagery scoring."""

from PIL import Image

import O4_Provider_Score_Artifacts as ART
import O4_Provider_Score_Edges as EDGE
from O4_Provider_Score_Models import ProviderScoreMetrics


def compute_provider_score_metrics(image: Image.Image) -> ProviderScoreMetrics:
    sample = ART.sample_rgb_array(image)
    luma = ART.luminance(sample)
    return ProviderScoreMetrics(
        noise=ART.noise_score(sample),
        jpeg_compression=ART.jpeg_compression_score(luma),
        clouds=ART.cloud_score(sample),
        color_drift=EDGE.color_drift_score(sample),
        seam_risk=EDGE.seam_risk_score(sample),
    )
