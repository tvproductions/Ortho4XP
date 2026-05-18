from __future__ import annotations

from dataclasses import dataclass
import io
import os
from pathlib import Path
import shutil
import struct

import O4_File_Names as FNAMES


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


@dataclass(frozen=True)
class ValidatedRasterBytes:
    demn: bytes
    dems: bytes
    payload: RasterPayload


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


def extract_validated_global_scenery_rasters(
    lat: int,
    lon: int,
    *,
    primary_overlay_src: str,
    alternate_overlay_src: str,
    tmp_dir: str,
    unzip_executable: str,
    run_external_tool,
) -> ValidatedRasterBytes:
    tile_label = FNAMES.short_latlon(lat, lon)
    source_path = _find_global_scenery_dsf(
        lat,
        lon,
        primary_overlay_src,
        alternate_overlay_src,
        tile_label,
    )
    tmp_path = Path(tmp_dir) / f"{tile_label}.dsf"
    try:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_path, tmp_path)
        dsf_bytes = _read_uncompressed_or_7z_dsf(
            tmp_path,
            tile_label,
            str(source_path),
            unzip_executable,
            run_external_tool,
        )
    except OSError as exc:
        raise _error(
            tile_label,
            str(source_path),
            f"could not copy/read XP12 Global Scenery DSF: {exc}",
        ) from exc
    finally:
        for suffix in ("", ".7z"):
            candidate = Path(str(tmp_path) + suffix)
            try:
                candidate.unlink()
            except OSError:
                pass

    return extract_validated_rasters_from_dsf_bytes(
        dsf_bytes,
        tile_label=tile_label,
        source_path=str(source_path),
    )


def _find_global_scenery_dsf(
    lat: int,
    lon: int,
    primary_overlay_src: str,
    alternate_overlay_src: str,
    tile_label: str,
) -> Path:
    relative = Path("Earth nav data") / f"{FNAMES.long_latlon(lat, lon)}.dsf"
    for root in (primary_overlay_src, alternate_overlay_src):
        if not root:
            continue
        candidate = Path(root) / relative
        if candidate.exists():
            return candidate
    raise _error(
        tile_label,
        f"{primary_overlay_src!r} or {alternate_overlay_src!r}",
        "missing XP12 Global Scenery DSF; check custom_overlay_src and "
        "custom_overlay_src_alternate",
    )


def _read_uncompressed_or_7z_dsf(
    tmp_path: Path,
    tile_label: str,
    source_path: str,
    unzip_executable: str,
    run_external_tool,
) -> bytes:
    with tmp_path.open("rb") as f:
        signature = f.read(2)
    if signature != b"7z":
        return tmp_path.read_bytes()

    archive_path = Path(str(tmp_path) + ".7z")
    os.replace(tmp_path, archive_path)
    result = run_external_tool(
        "7z",
        ["e", f"-o{tmp_path.parent}", str(archive_path)],
        executable=unzip_executable,
    )
    if result is not None and not getattr(result, "ok", False):
        raise _error(tile_label, source_path, "could not unpack compressed DSF")
    if not tmp_path.exists():
        raise _error(tile_label, source_path, "7z extraction did not produce DSF file")
    return tmp_path.read_bytes()


def extract_validated_rasters_from_dsf_bytes(
    dsf_bytes: bytes,
    *,
    tile_label: str,
    source_path: str,
) -> ValidatedRasterBytes:
    demn, dems = _extract_raw_raster_atoms(dsf_bytes, tile_label, source_path)
    payload = validate_raster_payload(
        demn,
        dems,
        tile_label=tile_label,
        source_path=source_path,
    )
    return ValidatedRasterBytes(demn=demn, dems=dems, payload=payload)


def _extract_raw_raster_atoms(
    dsf_bytes: bytes,
    tile_label: str,
    source_path: str,
) -> tuple[bytes, bytes]:
    if len(dsf_bytes) < 28 or dsf_bytes[:8] != b"XPLNEDSF":
        raise _error(tile_label, source_path, "corrupted DSF header")
    stream = io.BytesIO(dsf_bytes)
    stream.seek(12)
    atoms_end = len(dsf_bytes) - 16
    if atoms_end < 12:
        raise _error(tile_label, source_path, "corrupted DSF atom table")

    demn: bytes | None = None
    dems: bytes | None = None
    while stream.tell() < atoms_end:
        atom_start = stream.tell()
        header, payload = _read_atom(
            stream,
            atoms_end,
            tile_label,
            source_path,
            atom_table_name="DSF",
        )
        if header == "DEFN":
            demn = _extract_demn_from_defn(payload, tile_label, source_path)
        elif header == "DEMS":
            dems = payload
        if stream.tell() <= atom_start:
            raise _error(tile_label, source_path, "malformed DSF atom table")

    if demn is None:
        raise _error(tile_label, source_path, "missing DEMN raster definitions")
    if dems is None:
        raise _error(tile_label, source_path, "missing DEMS raster data")
    return demn, dems


def _extract_demn_from_defn(
    payload: bytes,
    tile_label: str,
    source_path: str,
) -> bytes:
    stream = io.BytesIO(payload)
    total_len = len(payload)
    while stream.tell() < total_len:
        header, data = _read_atom(
            stream,
            total_len,
            tile_label,
            source_path,
            atom_table_name="DEFN",
        )
        if header == "DEMN":
            return data
    raise _error(tile_label, source_path, "missing DEMN raster definitions")


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
    *,
    atom_table_name: str = "DEMS",
) -> tuple[str, bytes]:
    atom_start = stream.tell()
    header = stream.read(4)
    size_bytes = stream.read(4)
    if len(header) != 4 or len(size_bytes) != 4:
        raise _error(tile_label, source_path, f"malformed {atom_table_name} atom header")
    atom_size = struct.unpack("<I", size_bytes)[0]
    if atom_size < 8 or atom_start + atom_size > total_len:
        raise _error(tile_label, source_path, f"malformed {atom_table_name} atom length")
    payload = stream.read(atom_size - 8)
    if len(payload) != atom_size - 8:
        raise _error(tile_label, source_path, f"truncated {atom_table_name} atom payload")
    try:
        atom_header = header[::-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise _error(
            tile_label,
            source_path,
            f"malformed {atom_table_name} atom header",
        ) from exc
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
