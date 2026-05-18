from __future__ import annotations

from dataclasses import dataclass
import io
import struct


class BathymetryInputError(RuntimeError):
    """Raised when a water tile lacks valid XP12 bathymetry input."""


@dataclass(frozen=True)
class RasterInfo:
    name: str
    width: int
    height: int
    bytes_per_pixel: int
    flags: int
    data: bytes


@dataclass(frozen=True)
class RasterPayload:
    layer_names: tuple[str, ...]
    rasters: tuple[RasterInfo, ...]
    elevation: RasterInfo
    bathymetry: RasterInfo


def validate_raster_payload(
    demn: bytes,
    dems: bytes,
    *,
    tile_label: str,
    source_path: str,
) -> RasterPayload:
    layer_names = _parse_layer_names(demn, tile_label, source_path)
    raster_pairs = _parse_dems(dems, tile_label, source_path)
    if len(layer_names) != len(raster_pairs):
        raise _error(
            tile_label,
            source_path,
            f"raster definition count {len(layer_names)} does not match "
            f"DEMS raster count {len(raster_pairs)}",
        )

    rasters = tuple(
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
    by_name = {raster.name: raster for raster in rasters}
    if "elevation" not in by_name:
        raise _error(tile_label, source_path, "missing elevation raster")
    if "sea_level" not in by_name:
        raise _error(
            tile_label,
            source_path,
            "missing sea_level bathymetry raster required by XP12 Global Scenery",
        )

    elevation = by_name["elevation"]
    bathymetry = by_name["sea_level"]
    for raster in rasters:
        _validate_raster_data(raster, tile_label, source_path)
    if (bathymetry.width, bathymetry.height) != (elevation.width, elevation.height):
        raise _error(
            tile_label,
            source_path,
            "sea_level raster shape "
            f"{bathymetry.width}x{bathymetry.height} does not match elevation "
            f"raster shape {elevation.width}x{elevation.height}",
        )
    return RasterPayload(layer_names, rasters, elevation, bathymetry)


@dataclass(frozen=True)
class _RasterMetadata:
    width: int
    height: int
    bytes_per_pixel: int
    flags: int


def _parse_layer_names(demn: bytes, tile_label: str, source_path: str) -> tuple[str, ...]:
    if not demn:
        raise _error(tile_label, source_path, "empty DEMN raster definition payload")
    if not demn.endswith(b"\0"):
        raise _error(
            tile_label,
            source_path,
            "malformed DEMN raster definition names",
        )
    try:
        parts = demn[:-1].split(b"\0")
        if any(not part for part in parts):
            raise _error(
                tile_label,
                source_path,
                "malformed DEMN raster definition names",
            )
        names = tuple(part.decode("ascii") for part in parts)
    except UnicodeDecodeError as exc:
        raise _error(
            tile_label,
            source_path,
            "malformed DEMN raster definition names",
        ) from exc
    if not names:
        raise _error(tile_label, source_path, "DEMN contains no raster layer names")
    return names


def _parse_dems(
    dems: bytes,
    tile_label: str,
    source_path: str,
) -> tuple[tuple[_RasterMetadata, bytes], ...]:
    if not dems:
        raise _error(tile_label, source_path, "empty DEMS raster data payload")
    stream = io.BytesIO(dems)
    pairs: list[tuple[_RasterMetadata, bytes]] = []
    while stream.tell() < len(dems):
        header, payload = _read_atom(stream, len(dems), tile_label, source_path)
        if header != "DEMI":
            raise _error(
                tile_label,
                source_path,
                f"malformed DEMS payload: expected DEMI atom, found {header}",
            )
        metadata = _parse_demi(payload, tile_label, source_path)
        header, data = _read_atom(stream, len(dems), tile_label, source_path)
        if header != "DEMD":
            raise _error(
                tile_label,
                source_path,
                f"malformed DEMS payload: expected DEMD atom, found {header}",
            )
        pairs.append((metadata, data))
    return tuple(pairs)


def _read_atom(
    stream: io.BytesIO,
    total_len: int,
    tile_label: str,
    source_path: str,
) -> tuple[str, bytes]:
    atom_start = stream.tell()
    header = stream.read(4)
    size_bytes = stream.read(4)
    if len(header) != 4 or len(size_bytes) != 4:
        raise _error(tile_label, source_path, "malformed DEMS atom header")
    atom_size = struct.unpack("<I", size_bytes)[0]
    if atom_size < 8 or atom_start + atom_size > total_len:
        raise _error(tile_label, source_path, "malformed DEMS atom length")
    payload = stream.read(atom_size - 8)
    if len(payload) != atom_size - 8:
        raise _error(tile_label, source_path, "truncated DEMS atom payload")
    try:
        atom_header = header[::-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise _error(tile_label, source_path, "malformed DEMS atom header") from exc
    return atom_header, payload


def _parse_demi(
    payload: bytes,
    tile_label: str,
    source_path: str,
) -> _RasterMetadata:
    metadata_size = struct.calcsize("<BBHIIff")
    if len(payload) != metadata_size:
        raise _error(tile_label, source_path, "malformed DEMI raster metadata")
    _version, bytes_per_pixel, flags, width, height, _scale, _offset = struct.unpack(
        "<BBHIIff", payload[:metadata_size]
    )
    if bytes_per_pixel not in (1, 2, 4):
        raise _error(
            tile_label,
            source_path,
            f"unsupported raster bytes-per-pixel value {bytes_per_pixel}",
        )
    if width <= 0 or height <= 0:
        raise _error(
            tile_label,
            source_path,
            f"invalid raster dimensions {width}x{height}",
        )
    return _RasterMetadata(width, height, bytes_per_pixel, flags)


def _validate_raster_data(
    raster: RasterInfo,
    tile_label: str,
    source_path: str,
) -> None:
    expected_len = raster.width * raster.height * raster.bytes_per_pixel
    if not raster.data:
        raise _error(tile_label, source_path, f"{raster.name} raster payload is empty")
    if len(raster.data) != expected_len:
        raise _error(
            tile_label,
            source_path,
            f"{raster.name} raster payload has {len(raster.data)} bytes; "
            f"expected {expected_len}",
        )


def _error(tile_label: str, source_path: str, message: str) -> BathymetryInputError:
    return BathymetryInputError(
        f"Tile {tile_label} has invalid XP12 bathymetry input from {source_path}: "
        f"{message}. Point custom_overlay_src or custom_overlay_src_alternate at "
        "XP12 Global Scenery, or configure a future valid bathymetry provider."
    )
