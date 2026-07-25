from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CoastalMaskDisposition(StrEnum):
    NATIVE_WATER = "native_water"
    EXTERNAL_BORDER = "external_border"
    IMPRINTED_ALPHA = "imprinted_alpha"
    UNMASKED_LAND = "unmasked_land"


@dataclass(frozen=True)
class CoastalMaskDecision:
    disposition: CoastalMaskDisposition
    mask_file_name: str | None = None
    reason: str = ""

    @classmethod
    def external_border(cls, mask_file_name: str):
        return cls(CoastalMaskDisposition.EXTERNAL_BORDER, mask_file_name)

    @classmethod
    def imprinted_alpha(cls, mask_file_name: str):
        return cls(CoastalMaskDisposition.IMPRINTED_ALPHA, mask_file_name)

    @property
    def creates_custom_terrain(self) -> bool:
        return self.disposition in {
            CoastalMaskDisposition.EXTERNAL_BORDER,
            CoastalMaskDisposition.IMPRINTED_ALPHA,
        }

    @property
    def is_overlay(self) -> bool:
        return self.disposition == CoastalMaskDisposition.EXTERNAL_BORDER

    @property
    def cleanup_after_conversion(self) -> bool:
        return self.disposition == CoastalMaskDisposition.IMPRINTED_ALPHA


def provider_uses_explicit_extent(
    provider_code: str,
    providers: dict[str, dict[str, Any]],
    combined_providers: dict[str, list[dict[str, Any]]],
) -> bool:
    layers = combined_providers.get(provider_code)
    if layers is not None:
        return any(
            _is_explicit_extent(layer.get("extent_code", "global"))
            for layer in layers
        )
    return _is_explicit_extent(
        providers.get(provider_code, {}).get("extent", "global")
    )


def _is_explicit_extent(extent_code: object) -> bool:
    normalized = str(extent_code or "global").removeprefix("!")
    return normalized != "global"


def decide_coastal_mask(
    *,
    tri_type: int,
    imprint_masks_to_dds: bool,
    mask_file_name: str | None,
    mask_available: bool,
    explicit_provider_extent: bool,
) -> CoastalMaskDecision:
    if tri_type not in (1, 2):
        return CoastalMaskDecision(CoastalMaskDisposition.UNMASKED_LAND)
    if explicit_provider_extent:
        return CoastalMaskDecision(
            CoastalMaskDisposition.NATIVE_WATER,
            reason="explicit provider extent",
        )
    if not mask_available:
        return CoastalMaskDecision(
            CoastalMaskDisposition.NATIVE_WATER,
            reason="coastal mask unavailable",
        )
    if not mask_file_name:
        raise ValueError("available coastal mask requires a file name")
    if imprint_masks_to_dds:
        return CoastalMaskDecision.imprinted_alpha(mask_file_name)
    return CoastalMaskDecision.external_border(mask_file_name)


def water_texture_coordinates(
    decision: CoastalMaskDecision,
    s: float,
    t: float,
    ratio_fetch: float,
    ratio_bathy: float,
) -> tuple[float, float, float, float]:
    if decision.disposition == CoastalMaskDisposition.EXTERNAL_BORDER:
        return s, t, s, t
    if decision.disposition == CoastalMaskDisposition.IMPRINTED_ALPHA:
        return ratio_fetch, ratio_bathy, s, t
    raise ValueError(f"{decision.disposition} has no custom water coordinates")
