"""Resolve and cache XP12 coastal-mask artifacts used during DSF assembly."""

import O4_Coastal_Artifact_Policy as CAP
import O4_File_Names as FNAMES
import O4_Mask_Utils as MASK
import O4_UI_Utils as UI


def provider_uses_explicit_extent(provider_code):
    """Report whether provider geometry replaces inferred coastal masking."""
    import O4_Imagery_Utils as IMG

    return CAP.provider_uses_explicit_extent(
        provider_code,
        IMG.providers_dict,
        IMG.local_combined_providers_dict,
    )


def load_inferred_coastal_mask(tile, texture_attributes, explicit_extent):
    """Load an inferred mask unless explicit provider geometry owns the edge."""
    if explicit_extent:
        return False
    try:
        return MASK.needs_mask(tile, *texture_attributes)
    except OSError as exc:
        UI.vprint(3, exc)
        return False


def coastal_artifact(tile, texture_attributes, tri_type, artifacts):
    """Return one cached coastal decision together with its inferred mask."""
    terrain_attributes = (texture_attributes, tri_type)
    if terrain_attributes in artifacts:
        return artifacts[terrain_attributes], None
    explicit_extent = provider_uses_explicit_extent(texture_attributes[3])
    mask_im = load_inferred_coastal_mask(
        tile,
        texture_attributes,
        explicit_extent,
    )
    decision = CAP.decide_coastal_mask(
        tri_type=tri_type,
        imprint_masks_to_dds=tile.imprint_masks_to_dds,
        mask_file_name=FNAMES.mask_file(*texture_attributes) if mask_im else None,
        explicit_provider_extent=explicit_extent,
    )
    artifacts[terrain_attributes] = decision
    if decision.creates_custom_terrain:
        UI.vprint(2, "      Use of an alpha mask.")
    return decision, mask_im
