"""Validate requested-to-resolved DDS mappings before terrain mutation.

Conversion workers operate concurrently, so their result collection is treated
as untrusted transaction input.  This module checks metadata shape, stable
texture location, provider identity, canonical naming, output existence, and
conflicting resolutions without reading or changing terrain files.
"""

from pathlib import Path

import O4_File_Names as FNAMES
from O4_Texture_Finalization_Models import TextureFinalizationError


def validated_mappings(tile, results):
    """Return canonical requested-to-resolved DDS names for valid results."""
    mappings = {}
    output_names = set()
    for result in results:
        requested_name, resolved_name = _validated_result(result)
        _record_mapping(mappings, requested_name, resolved_name)
        output_names.add(resolved_name)
    _require_outputs(tile, output_names)
    return mappings


def _validated_result(result):
    """Validate one conversion result and derive both canonical DDS names."""
    _require_successful_result(result)
    requested_attrs, resolved_attrs = _validated_result_metadata(result)
    _require_matching_texture_location(requested_attrs, resolved_attrs)
    _require_matching_provider(result, resolved_attrs)
    requested_name = FNAMES.dds_file_name_from_attributes(*requested_attrs)
    resolved_name = FNAMES.dds_file_name_from_attributes(*resolved_attrs)
    _require_display_name(result, resolved_name)
    return requested_name, resolved_name


def _require_successful_result(result):
    """Reject conversion failure and non-string display metadata."""
    if not result.ok:
        raise TextureFinalizationError(
            f"texture conversion failed: {result.display_name}"
        )
    if not isinstance(result.display_name, str) or not result.display_name:
        raise TextureFinalizationError(
            f"invalid texture display name: {result.display_name!r}"
        )


def _validated_result_metadata(result):
    """Require both sides of the requested/resolved identity contract."""
    requested_attrs = result.requested_attrs
    resolved_attrs = result.resolved_attrs
    if requested_attrs is None and resolved_attrs is None:
        raise TextureFinalizationError(
            f"missing texture resolution metadata: {result.display_name}"
        )
    if requested_attrs is None or resolved_attrs is None:
        raise TextureFinalizationError(
            f"incomplete texture resolution metadata: {result.display_name}"
        )
    return (
        _validated_texture_attrs("requested", requested_attrs, result.display_name),
        _validated_texture_attrs("resolved", resolved_attrs, result.display_name),
    )


def _require_matching_texture_location(requested_attrs, resolved_attrs):
    """Failover may change only provider identity, never tile coordinates."""
    if requested_attrs[:3] != resolved_attrs[:3]:
        raise TextureFinalizationError(
            "requested/resolved texture coordinates and zoom differ: "
            f"{requested_attrs[:3]}, {resolved_attrs[:3]}"
        )


def _require_matching_provider(result, resolved_attrs):
    """Keep the result provider field coherent with resolved attributes."""
    if resolved_attrs[3] != result.provider_code:
        raise TextureFinalizationError(
            f"resolved provider mismatch: {resolved_attrs[3]}, {result.provider_code}"
        )


def _require_display_name(result, resolved_name):
    """Require the worker's display name to be the canonical resolved DDS."""
    if result.display_name != resolved_name:
        raise TextureFinalizationError(
            "resolved DDS display name mismatch: "
            f"{result.display_name}, {resolved_name}"
        )


def _record_mapping(mappings, requested_name, resolved_name):
    """Reject order-dependent or conflicting resolutions for one request."""
    previous = mappings.setdefault(requested_name, resolved_name)
    if previous != resolved_name:
        raise TextureFinalizationError(
            f"conflicting resolutions for {requested_name}: {previous}, {resolved_name}"
        )


def _require_outputs(tile, output_names):
    """Require every successful resolved output to exist before rewrites."""
    texture_dir = Path(tile.build_dir) / "textures"
    missing = sorted(
        name for name in output_names if not (texture_dir / name).is_file()
    )
    if missing:
        raise TextureFinalizationError("missing DDS output: " + ", ".join(missing))


def _validated_texture_attrs(label, attrs, display_name):
    """Return a four-field texture identity after exact runtime validation."""
    if not isinstance(attrs, tuple) or len(attrs) != 4:
        raise TextureFinalizationError(
            f"invalid {label} texture attributes for {display_name}: {attrs!r}"
        )
    til_x_left, til_y_top, zoomlevel, provider_code = attrs
    coordinates = (til_x_left, til_y_top, zoomlevel)
    if not _coordinates_are_integers(coordinates):
        raise TextureFinalizationError(
            f"invalid {label} texture attributes for {display_name}: {attrs!r}"
        )
    if not isinstance(provider_code, str) or not provider_code:
        raise TextureFinalizationError(
            f"invalid {label} texture attributes for {display_name}: {attrs!r}"
        )
    return attrs


def _coordinates_are_integers(coordinates):
    """Exclude booleans and other integer-like values from texture identities."""
    return all(map(_is_exact_integer, coordinates))


def _is_exact_integer(value):
    """Accept integers without accepting their boolean subclass."""
    return type(value) is int
