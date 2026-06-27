"""Shared score invocation helpers for provider scoring tests."""

from __future__ import annotations

from PIL import Image

import O4_Provider_Scoring as SCORE

DEFAULT_PROVIDER_CODE = "BI"
DEFAULT_TEXTURE_ATTRIBUTES = (32, 48, 16, "BI")


def score_image(
    image: Image.Image,
    scoring_context: SCORE.ProviderScoreContext | None = None,
) -> SCORE.ProviderScoreResult:
    return SCORE.score_provider_image(
        DEFAULT_PROVIDER_CODE,
        DEFAULT_TEXTURE_ATTRIBUTES,
        image,
        scoring_context=scoring_context,
    )
