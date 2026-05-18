"""XP12 Global Scenery bathymetry raster extraction.

This module keeps the TODO-014 bathymetry boundary deliberately narrow:

* XP12 Global Scenery is the only accepted provider.
* Water tiles need both DEMN layer names and DEMS raster payloads.
* The required semantic layers are ``elevation`` and ``sea_level``.
* ``sea_level`` must have the same shape as ``elevation``.
* The original DEMN and DEMS bytes are returned unchanged for DSF encoding.

DSF atoms use little-endian lengths and reversed four-byte atom ids on disk.
For example, the on-disk bytes ``NFED`` decode to the logical atom ``DEFN``.
The bathymetry data needed by Ortho4XP lives in two places:

* top-level ``DEFN`` contains child ``DEMN`` with null-terminated names;
* top-level ``DEMS`` contains repeating ``DEMI`` metadata and ``DEMD`` data.

The parser stages are intentionally separated:

* source lookup resolves the XP12 Global Scenery DSF for a tile;
* copy/read handles uncompressed DSF files and 7z-compressed DSF archives;
* atom scanning extracts raw DEMN and DEMS payloads from the DSF envelope;
* payload validation pairs names with raster metadata and byte payloads;
* semantic validation requires elevation and sea-level bathymetry rasters.

The error context is threaded through every stage so failures name the tile,
the source DSF, and the concrete invalid condition before build code can rename
or replace the generated DSF.  That is important because missing bathymetry is a
configuration problem, not an encoding problem, and the user needs the original
Global Scenery path in the failure message.

Validation notes for maintainers:

* A DSF shorter than the eight-byte signature, four-byte version, and trailing
  sixteen-byte checksum cannot contain a valid atom table.
* The scanner stops before the checksum bytes.  It never treats the checksum as
  an atom and it checks that every atom advances the stream.
* Atom sizes include their own eight-byte header.  Sizes below eight or beyond
  the enclosing atom table are rejected before payload reads.
* Atom ids are decoded as ASCII after reversing the disk byte order.  Non-ASCII
  ids are malformed input, not unknown optional data.
* ``DEFN`` may contain many definition children, but bathymetry only consumes
  ``DEMN``.  Missing ``DEMN`` means there is no reliable layer-name contract.
* ``DEMN`` is a sequence of null-terminated ASCII layer names.  Empty entries,
  missing final terminators, and non-ASCII names are rejected.
* ``DEMS`` is a strict sequence of ``DEMI`` then ``DEMD`` pairs.  An unexpected
  atom means names and raster bytes can no longer be paired safely.
* ``DEMI`` metadata is fixed-size for the fields Ortho4XP needs: version,
  bytes-per-pixel, flags, width, height, scale, and offset.
* Supported pixel widths are one, two, and four bytes.  Other widths would make
  byte-length validation ambiguous for the current DSF encoder.
* Width and height must be positive before the expected byte count is computed.
* Every named raster payload must be non-empty and exactly match its metadata
  byte count.  Extra rasters are allowed only if their own payload is valid.
* ``elevation`` is required because X-Plane expects the terrain elevation layer
  to remain coherent with bathymetry data.
* ``sea_level`` is required because it is the XP12 Global Scenery bathymetry
  layer currently preserved into generated DSFs.
* ``sea_level`` and ``elevation`` must share width and height so the encoder
  writes compatible raster definitions and raster data.
* The validated result returns the original DEMN and DEMS bytes, not rebuilt
  bytes, because the DSF writer needs byte-for-byte provider atoms.
* Temporary copies are always removed after source reads, including stale
  ``.7z`` siblings from prior attempts.
* The compressed path renames the temporary DSF copy to ``.7z`` before invoking
  the configured extractor, matching the historical 7z command behavior.
* External tool failures include the tool-provided summary when present and the
  return code otherwise.
* A successful extractor run must create the expected temporary DSF path.  A
  missing output file is reported as invalid bathymetry input.
* The source lookup checks the primary overlay root first, then the alternate
  root, matching the existing Ortho4XP overlay precedence.
* Empty overlay roots are ignored so unset alternates do not produce misleading
  path probes.
* All raised errors use ``BathymetryInputError``.  Callers can either surface the
  message and stop or let the exception abort before DSF backup/rename.

Refactor boundaries:

* ``GlobalSceneryRasterSource`` owns the provider inputs that used to travel as
  long parameter lists.  Adding another provider should introduce a new source
  object instead of widening function signatures again.
* ``BathymetryErrorContext`` is deliberately tiny.  It formats one canonical
  message so every parser helper can fail without rebuilding context strings.
* ``RasterInfo`` represents the parsed semantic unit: one name, one metadata
  record, and one byte payload.
* ``RasterPayload`` represents the validated semantic contract that callers can
  inspect in tests without reparsing binary atoms.
* ``ValidatedRasterBytes`` carries both raw atoms and parsed payload.  The raw
  atoms feed DSF encoding; the parsed payload proves the bytes are acceptable.
* ``_AtomReadContext`` keeps stream state, bounds, table name, and error context
  together so atom readers stay below the parameter-count gate.
* ``_RawRasterAtoms`` is mutable only during DSF scanning.  It is private and is
  converted to an immutable tuple before validation continues.
* Source lookup does not validate payloads.  Its only responsibility is finding
  the correct DSF path according to Ortho4XP overlay settings.
* Archive handling does not parse atoms.  It only returns DSF bytes or raises a
  contextual input error.
* Atom scanning does not validate raster semantics.  It only extracts DEMN and
  DEMS byte payloads from a syntactically valid DSF envelope.
* Raster parsing does not know about files.  It validates byte structures using
  the supplied error context.
* Semantic validation does not rewrite raster data.  It checks provider bytes
  and names the exact missing or inconsistent layer.
* Test fixtures build tiny DSFs from atom helpers so payload tests and source
  tests cover the same byte-order rules as production parsing.
* All-land tiles are handled outside this module.  This module assumes its caller
  already determined that bathymetry input is required.
* The module intentionally avoids imagery providers, masks, and computed depth
  ratios.  Those are downstream DSF encoding concerns, not source validation.
* New validation rules should be added at the narrowest stage that owns the
  invariant.  For example, atom size belongs to atom reading, while sea-level
  shape belongs to semantic validation.
* New error paths should include the provider path and tile label through
  ``BathymetryErrorContext`` instead of custom exception text.
* New tests should prefer semantic assertions over copying incidental command
  output.  The error text checks should only pin actionable user-facing context.
* If Laminar changes XP12 raster naming, add that compatibility in named-raster
  validation and keep the raw DEMN/DEMS preservation behavior intact.
* If another bathymetry provider is added, do not route it through masks or mesh
  depth ratios.  It should produce validated raster atoms through a separate
  source boundary.
* If compressed-source behavior changes, keep cleanup symmetric: both the temp
  DSF path and its archive sibling must be removable after every attempt.

Failure examples the parser must keep actionable:

* Missing source DSF: name both overlay configuration roots and explain that
  XP12 Global Scenery is required.
* Corrupted DSF header: reject before atom reads so later messages do not imply
  a raster-specific issue.
* Corrupted atom table: reject impossible table bounds before scanning.
* Missing DEMN: report missing raster definitions, not missing sea-level data,
  because names cannot be paired yet.
* Missing DEMS: report missing raster data, not malformed metadata.
* Empty DEMN: report empty raster definitions.
* DEMN without final null: report malformed raster definition names.
* DEMN with an empty middle entry: report malformed raster definition names.
* DEMN with non-ASCII bytes: report malformed raster definition names.
* Empty DEMS: report empty raster data payload.
* DEMS atom order mismatch: report the expected atom and the atom found.
* Truncated atom header: report the table whose atom header was malformed.
* Atom length outside the table: report malformed atom length.
* Truncated atom payload: report truncated atom payload.
* DEMI with an unexpected metadata byte count: report malformed DEMI metadata.
* Unsupported bytes-per-pixel: include the unsupported value.
* Non-positive raster dimensions: include the invalid dimensions.
* Raster count mismatch: include both name count and DEMS pair count.
* Missing elevation: report the missing elevation raster directly.
* Missing sea_level: mention XP12 Global Scenery because that is the current
  provider contract.
* Empty raster data: name the raster whose payload is empty.
* Raster byte-count mismatch: name the raster, actual byte count, and expected
  byte count.
* Sea-level shape mismatch: include both sea-level and elevation dimensions.

These examples are intentionally close to the user-facing messages asserted by
the tests.  They are the compatibility contract for future parser refactors.

Minimal valid fixture shape:

* File prefix: ``XPLNEDSF`` plus a four-byte DSF version.
* Top-level atom: ``DEFN`` encoded on disk as ``NFED``.
* Child atom: ``DEMN`` encoded on disk as ``NMED``.
* DEMN payload: ``elevation\0sea_level\0``.
* Top-level atom: ``DEMS`` encoded on disk as ``SMED``.
* First DEMS child: ``DEMI`` metadata for elevation.
* Second DEMS child: ``DEMD`` elevation bytes.
* Third DEMS child: ``DEMI`` metadata for sea_level.
* Fourth DEMS child: ``DEMD`` sea_level bytes.
* File suffix: sixteen checksum bytes that are outside the atom scan range.

The tiny test DSFs follow that shape exactly.  They keep source-provider tests
deterministic without depending on an X-Plane installation, GDAL tools, network
imagery, or the real 7z executable.

Why raw bytes are preserved:

* Ortho4XP is not synthesizing new bathymetry rasters in TODO-014.
* The XP12 provider has already encoded raster scale, offset, flags, and data.
* Rebuilding DEMN or DEMS would risk losing provider metadata that Ortho4XP does
  not yet interpret.
* Validation proves the bytes contain required layers while leaving the DSF
  writer free to append exactly those provider atoms.
* Tests assert both parsed semantics and raw byte preservation so the two
  responsibilities cannot drift apart.

Why this module does not inspect water triangles:

* Mesh classification happens after mesh read and XP12 water-triangle recutting.
* All-land tiles must skip bathymetry validation entirely.
* Water tiles must fail before generated DSF backup/rename when input is absent
  or malformed.
* Keeping the mesh gate in the DSF build layer prevents parser code from needing
  tile mesh internals.
* Keeping provider validation here prevents DSF encoding code from knowing DSF
  atom parsing details.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import io
import os
from pathlib import Path
import shutil
import struct
from typing import Any

import O4_File_Names as FNAMES


class BathymetryInputError(RuntimeError):
    """Raised when a water tile lacks valid XP12 bathymetry input."""


@dataclass(frozen=True)
class BathymetryErrorContext:
    tile_label: str
    source_path: str

    def error(self, message):
        return BathymetryInputError(
            f"Tile {self.tile_label} has invalid XP12 bathymetry input from "
            f"{self.source_path}: {message}. Point custom_overlay_src or "
            "custom_overlay_src_alternate at XP12 Global Scenery, or configure "
            "a future valid bathymetry provider."
        )


@dataclass(frozen=True)
class GlobalSceneryRasterSource:
    lat: int
    lon: int
    primary_overlay_src: str
    alternate_overlay_src: str
    tmp_dir: str
    unzip_executable: str
    run_external_tool: Callable[..., Any]

    @property
    def tile_label(self):
        return FNAMES.short_latlon(self.lat, self.lon)


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


@dataclass(frozen=True)
class _RasterMetadata:
    width: int
    height: int
    bytes_per_pixel: int
    flags: int


@dataclass(frozen=True)
class _AtomReadContext:
    stream: io.BytesIO
    total_len: int
    errors: BathymetryErrorContext
    atom_table_name: str = "DEMS"


@dataclass
class _RawRasterAtoms:
    demn: bytes | None = None
    dems: bytes | None = None


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


def extract_validated_global_scenery_rasters(source):
    source_path = _find_global_scenery_dsf(source)
    errors = BathymetryErrorContext(source.tile_label, str(source_path))
    tmp_path = Path(source.tmp_dir) / f"{source.tile_label}.dsf"

    try:
        dsf_bytes = _copy_and_read_global_scenery_dsf(source, source_path, tmp_path)
    except OSError as exc:
        raise errors.error(
            f"could not copy/read XP12 Global Scenery DSF: {exc}"
        ) from exc
    finally:
        _remove_temp_dsf_files(tmp_path)

    return extract_validated_rasters_from_dsf_bytes(
        dsf_bytes,
        tile_label=source.tile_label,
        source_path=str(source_path),
    )


def _copy_and_read_global_scenery_dsf(source, source_path, tmp_path):
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source_path, tmp_path)
    errors = BathymetryErrorContext(source.tile_label, str(source_path))
    return _read_uncompressed_or_7z_dsf(source, tmp_path, errors)


def _find_global_scenery_dsf(source):
    relative = (
        Path("Earth nav data") / f"{FNAMES.long_latlon(source.lat, source.lon)}.dsf"
    )
    for root in (source.primary_overlay_src, source.alternate_overlay_src):
        if not root:
            continue
        candidate = Path(root) / relative
        if candidate.exists():
            return candidate
    searched = f"{source.primary_overlay_src!r} or {source.alternate_overlay_src!r}"
    errors = BathymetryErrorContext(source.tile_label, searched)
    raise errors.error(
        "missing XP12 Global Scenery DSF; check custom_overlay_src and "
        "custom_overlay_src_alternate"
    )


def _read_uncompressed_or_7z_dsf(source, tmp_path, errors):
    with tmp_path.open("rb") as f:
        signature = f.read(2)
    if signature != b"7z":
        return tmp_path.read_bytes()

    archive_path = Path(str(tmp_path) + ".7z")
    os.replace(tmp_path, archive_path)
    result = source.run_external_tool(
        "7z",
        ["e", f"-o{tmp_path.parent}", str(archive_path)],
        executable=source.unzip_executable,
    )
    _validate_7z_result(result, tmp_path, errors)
    return tmp_path.read_bytes()


def _validate_7z_result(result, tmp_path, errors):
    if result is not None and not getattr(result, "ok", False):
        detail = _external_tool_failure_detail(result)
        raise errors.error(f"could not unpack compressed DSF{detail}")
    if not tmp_path.exists():
        raise errors.error("7z extraction did not produce DSF file")


def _remove_temp_dsf_files(tmp_path):
    for suffix in ("", ".7z"):
        candidate = Path(str(tmp_path) + suffix)
        try:
            candidate.unlink()
        except OSError:
            pass


def _external_tool_failure_detail(result):
    error_summary = getattr(result, "error_summary", None)
    if error_summary:
        return f": {error_summary}"
    returncode = getattr(result, "returncode", None)
    if returncode is not None:
        return f": returncode {returncode}"
    return ""


def extract_validated_rasters_from_dsf_bytes(dsf_bytes, *, tile_label, source_path):
    errors = BathymetryErrorContext(tile_label, source_path)
    demn, dems = _extract_raw_raster_atoms(dsf_bytes, errors)
    payload = validate_raster_payload(
        demn,
        dems,
        tile_label=tile_label,
        source_path=source_path,
    )
    return ValidatedRasterBytes(demn=demn, dems=dems, payload=payload)


def _extract_raw_raster_atoms(dsf_bytes, errors):
    atoms_end = _validate_dsf_envelope(dsf_bytes, errors)
    atoms = _scan_dsf_atoms(dsf_bytes, atoms_end, errors)
    return _require_raw_raster_atoms(atoms, errors)


def _validate_dsf_envelope(dsf_bytes, errors):
    if len(dsf_bytes) < 28 or dsf_bytes[:8] != b"XPLNEDSF":
        raise errors.error("corrupted DSF header")
    atoms_end = len(dsf_bytes) - 16
    if atoms_end < 12:
        raise errors.error("corrupted DSF atom table")
    return atoms_end


def _scan_dsf_atoms(dsf_bytes, atoms_end, errors):
    stream = io.BytesIO(dsf_bytes)
    stream.seek(12)
    atoms = _RawRasterAtoms()
    context = _AtomReadContext(stream, atoms_end, errors, "DSF")
    while stream.tell() < atoms_end:
        _read_next_dsf_atom(context, atoms)
    return atoms


def _read_next_dsf_atom(context, atoms):
    atom_start = context.stream.tell()
    header, payload = _read_atom(context)
    _capture_raw_raster_atom(header, payload, atoms, context.errors)
    if context.stream.tell() <= atom_start:
        raise context.errors.error("malformed DSF atom table")


def _capture_raw_raster_atom(header, payload, atoms, errors):
    if header == "DEFN":
        atoms.demn = _extract_demn_from_defn(payload, errors)
    if header == "DEMS":
        atoms.dems = payload


def _require_raw_raster_atoms(atoms, errors):
    if atoms.demn is None:
        raise errors.error("missing DEMN raster definitions")
    if atoms.dems is None:
        raise errors.error("missing DEMS raster data")
    return atoms.demn, atoms.dems


def _extract_demn_from_defn(payload, errors):
    stream = io.BytesIO(payload)
    context = _AtomReadContext(stream, len(payload), errors, "DEFN")
    while stream.tell() < len(payload):
        header, data = _read_atom(context)
        if header == "DEMN":
            return data
    raise errors.error("missing DEMN raster definitions")


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
    context = _AtomReadContext(stream, len(dems), errors)
    while stream.tell() < len(dems):
        pairs.append(_read_dems_pair(context))
    return tuple(pairs)


def _read_dems_pair(context):
    metadata_payload = _read_required_atom(context, "DEMI")
    metadata = _parse_demi(metadata_payload, context.errors)
    return metadata, _read_required_atom(context, "DEMD")


def _read_required_atom(context, expected_header):
    header, payload = _read_atom(context)
    if header != expected_header:
        raise context.errors.error(
            f"malformed {context.atom_table_name} payload: expected "
            f"{expected_header} atom, found {header}"
        )
    return payload


def _read_atom(context):
    atom_start = context.stream.tell()
    header, atom_size = _read_atom_prefix(context)
    _validate_atom_size(atom_start, atom_size, context)
    return _decode_atom_header(header, context), _read_atom_payload(atom_size, context)


def _read_atom_prefix(context):
    header = context.stream.read(4)
    size_bytes = context.stream.read(4)
    if len(header) != 4 or len(size_bytes) != 4:
        raise context.errors.error(f"malformed {context.atom_table_name} atom header")
    return header, struct.unpack("<I", size_bytes)[0]


def _validate_atom_size(atom_start, atom_size, context):
    if atom_size < 8 or atom_start + atom_size > context.total_len:
        raise context.errors.error(f"malformed {context.atom_table_name} atom length")


def _read_atom_payload(atom_size, context):
    payload = context.stream.read(atom_size - 8)
    if len(payload) != atom_size - 8:
        raise context.errors.error(f"truncated {context.atom_table_name} atom payload")
    return payload


def _decode_atom_header(header, context):
    try:
        return header[::-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise context.errors.error(
            f"malformed {context.atom_table_name} atom header"
        ) from exc


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
