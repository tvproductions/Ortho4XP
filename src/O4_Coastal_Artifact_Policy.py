"""XP12 coastal-mask decisions shared by DSF and texture generation.

The policy deliberately owns no provider downloads or image processing.  It
turns validated resource facts into one immutable terrain disposition early
enough for DSF coordinate selection and later cleanup to agree.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
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
            _is_explicit_extent(layer.get("extent_code", "global")) for layer in layers
        )
    return _is_explicit_extent(providers.get(provider_code, {}).get("extent", "global"))


def _is_explicit_extent(extent_code: object) -> bool:
    normalized = str(extent_code or "global").removeprefix("!")
    return normalized != "global"


def decide_coastal_mask(
    *,
    tri_type: int,
    imprint_masks_to_dds: bool,
    mask_file_name: str | None,
    explicit_provider_extent: bool,
) -> CoastalMaskDecision:
    """Select one XP12 coastal disposition from validated planning facts."""
    native_decision = _native_water_decision(
        tri_type,
        mask_file_name,
        explicit_provider_extent,
    )
    if native_decision is not None:
        return native_decision
    return _masked_water_decision(imprint_masks_to_dds, mask_file_name)


def _native_water_decision(
    tri_type: int,
    mask_file_name: str | None,
    explicit_provider_extent: bool,
) -> CoastalMaskDecision | None:
    if tri_type not in (1, 2):
        return CoastalMaskDecision(CoastalMaskDisposition.UNMASKED_LAND)
    if explicit_provider_extent:
        return CoastalMaskDecision(
            CoastalMaskDisposition.NATIVE_WATER,
            reason="explicit provider extent",
        )
    if not mask_file_name:
        return CoastalMaskDecision(
            CoastalMaskDisposition.NATIVE_WATER,
            reason="coastal mask unavailable",
        )
    return None


def _masked_water_decision(
    imprint_masks_to_dds: bool,
    mask_file_name: str | None,
) -> CoastalMaskDecision:
    if mask_file_name is None:
        raise ValueError("masked coastal water requires a file name")
    if imprint_masks_to_dds:
        return CoastalMaskDecision.imprinted_alpha(mask_file_name)
    return CoastalMaskDecision.external_border(mask_file_name)


def water_texture_coordinates(
    decision: CoastalMaskDecision,
    texture_st: tuple[float, float],
    water_ratios: tuple[float, float],
) -> tuple[float, float, float, float]:
    """Return the four post-normal coordinates for custom XP12 water."""
    s, t = texture_st
    if decision.disposition == CoastalMaskDisposition.EXTERNAL_BORDER:
        return s, t, s, t
    if decision.disposition == CoastalMaskDisposition.IMPRINTED_ALPHA:
        ratio_fetch, ratio_bathy = water_ratios
        return ratio_fetch, ratio_bathy, s, t
    raise ValueError(f"{decision.disposition} has no custom water coordinates")


def require_external_border_mask(
    build_dir: str,
    decision: CoastalMaskDecision | None,
) -> None:
    """Reject a stale external-border decision before opening its terrain file."""
    if decision is None:
        return
    if decision.disposition != CoastalMaskDisposition.EXTERNAL_BORDER:
        return
    mask_path = Path(build_dir) / "textures" / str(decision.mask_file_name)
    if not mask_path.is_file():
        raise FileNotFoundError(f"Missing BORDER_TEX mask: {mask_path}")
