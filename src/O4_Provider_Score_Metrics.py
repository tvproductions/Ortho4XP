"""Metric orchestration for provider imagery scoring."""

from PIL import Image

import O4_Provider_Score_Artifacts as ART
import O4_Provider_Score_Edges as EDGE
from O4_Provider_Score_Models import ProviderScoreContext, ProviderScoreMetrics


def compute_provider_score_metrics(
    image: Image.Image,
    scoring_context: ProviderScoreContext | None = None,
) -> ProviderScoreMetrics:
    sample = ART.sample_rgb_array(image)
    luma = ART.luminance(sample)
    cloud_risk, cloud_details = ART.cloud_score_details(sample)
    seam_risk, seam_details = EDGE.seam_risk_score_details(sample, scoring_context)
    return ProviderScoreMetrics(
        noise=ART.noise_score(sample),
        jpeg_compression=ART.jpeg_compression_score(luma),
        clouds=cloud_risk,
        color_drift=EDGE.color_drift_score(sample),
        seam_risk=seam_risk,
        details={
            "clouds": cloud_details,
            "seam_risk": seam_details,
        },
    )
