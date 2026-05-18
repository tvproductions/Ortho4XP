from __future__ import annotations

"""Validate XP12 DEMN and DEMS bathymetry raster payloads.

The parser pairs null-terminated DEMN layer names with strict DEMS ``DEMI`` /
``DEMD`` metadata-data pairs.  It requires the current TODO-014 semantic
contract: valid ``elevation`` and ``sea_level`` rasters with matching shapes.

It does not rebuild raster atoms.  Callers keep the original provider bytes for
DSF encoding after this module proves the payload is structurally and
semantically usable.

Validation stays local to the payload contract: atom order, raster dimensions,
bytes-per-pixel, payload length, required layer names, and shape compatibility.
Source paths and DSF envelope checks are handled by adjacent modules.
"""

from dataclasses import dataclass
import io
import struct

from O4_Bathymetry_DSF_Atoms import AtomReadContext, read_atom
from O4_Bathymetry_Models import (
    BathymetryErrorContext,
    BathymetryInputError,
    RasterInfo,
    RasterPayload,
)


@dataclass(frozen=True)
class _RasterMetadata:
    width: int
    height: int
    bytes_per_pixel: int
    flags: int


def validate_raster_payload(demn, dems, *, tile_label, source_path):
    errors = BathymetryErrorContext(tile_label, source_path)
    layer_names = _parse_layer_names(demn, errors)
    raster_pairs = _parse_dems(dems, errors)
    rasters = _build_rasters(layer_names, raster_pairs, errors)
    elevation, bathymetry = _validate_raster_semantics(rasters, errors)
    return RasterPayload(layer_names, rasters, elevation, bathymetry)


def _validate_raster_semantics(rasters, errors):
    for raster in rasters:
        _validate_raster_data(raster, errors)

    by_name = {raster.name: raster for raster in rasters}
    elevation = _required_raster(by_name, "elevation", errors)
    bathymetry = _required_raster(by_name, "sea_level", errors)
    _validate_matching_shape(elevation, bathymetry, errors)
    return elevation, bathymetry


def _validate_raster_data(raster, errors):
    expected_len = raster.width * raster.height * raster.bytes_per_pixel
    if not raster.data:
        raise errors.error(f"{raster.name} raster payload is empty")
    if len(raster.data) != expected_len:
        raise errors.error(
            f"{raster.name} raster payload has {len(raster.data)} bytes; "
            f"expected {expected_len}"
        )


def _required_raster(by_name, name, errors):
    if name in by_name:
        return by_name[name]
    if name == "sea_level":
        raise errors.error(
            "missing sea_level bathymetry raster required by XP12 Global Scenery"
        )
    raise errors.error(f"missing {name} raster")


def _validate_matching_shape(elevation, bathymetry, errors):
    if (bathymetry.width, bathymetry.height) != (elevation.width, elevation.height):
        raise errors.error(
            "sea_level raster shape "
            f"{bathymetry.width}x{bathymetry.height} does not match elevation "
            f"raster shape {elevation.width}x{elevation.height}"
        )


def _parse_layer_names(demn, errors):
    if not demn:
        raise errors.error("empty DEMN raster definition payload")
    if not demn.endswith(b"\0"):
        raise _malformed_demn_names(errors)
    return _decode_layer_names(demn[:-1].split(b"\0"), errors)


def _decode_layer_names(raw_names, errors):
    _reject_empty_layer_names(raw_names, errors)
    names = _decode_ascii_layer_names(raw_names, errors)
    if not names:
        raise errors.error("DEMN contains no raster layer names")
    return names


def _reject_empty_layer_names(raw_names, errors):
    for name in raw_names:
        if not name:
            raise _malformed_demn_names(errors)


def _decode_ascii_layer_names(raw_names, errors):
    try:
        return tuple(name.decode("ascii") for name in raw_names)
    except UnicodeDecodeError as exc:
        raise _malformed_demn_names(errors) from exc


def _malformed_demn_names(errors: BathymetryErrorContext) -> BathymetryInputError:
    return errors.error("malformed DEMN raster definition names")


def _parse_dems(dems, errors):
    if not dems:
        raise errors.error("empty DEMS raster data payload")
    stream = io.BytesIO(dems)
    pairs: list[tuple[_RasterMetadata, bytes]] = []
    context = AtomReadContext(stream, len(dems), errors)
    while stream.tell() < len(dems):
        pairs.append(_read_dems_pair(context))
    return tuple(pairs)


def _read_dems_pair(context):
    metadata_payload = _read_required_atom(context, "DEMI")
    metadata = _parse_demi(metadata_payload, context.errors)
    return metadata, _read_required_atom(context, "DEMD")


def _read_required_atom(context, expected_header):
    header, payload = read_atom(context)
    if header != expected_header:
        raise context.errors.error(
            f"malformed {context.atom_table_name} payload: expected "
            f"{expected_header} atom, found {header}"
        )
    return payload


def _parse_demi(payload, errors):
    metadata_size = struct.calcsize("<BBHIIff")
    if len(payload) != metadata_size:
        raise errors.error("malformed DEMI raster metadata")
    _version, bytes_per_pixel, flags, width, height, _scale, _offset = struct.unpack(
        "<BBHIIff", payload[:metadata_size]
    )
    _validate_demi_shape(width, height, bytes_per_pixel, errors)
    return _RasterMetadata(width, height, bytes_per_pixel, flags)


def _validate_demi_shape(width, height, bytes_per_pixel, errors):
    if bytes_per_pixel not in (1, 2, 4):
        raise errors.error(
            f"unsupported raster bytes-per-pixel value {bytes_per_pixel}"
        )
    if width <= 0 or height <= 0:
        raise errors.error(f"invalid raster dimensions {width}x{height}")


def _build_rasters(layer_names, raster_pairs, errors):
    if len(layer_names) != len(raster_pairs):
        raise errors.error(
            f"raster definition count {len(layer_names)} does not match "
            f"DEMS raster count {len(raster_pairs)}"
        )
    return tuple(
        RasterInfo(
            name=name,
            width=metadata.width,
            height=metadata.height,
            bytes_per_pixel=metadata.bytes_per_pixel,
            flags=metadata.flags,
            data=data,
        )
        for name, (metadata, data) in zip(layer_names, raster_pairs, strict=True)
    )
