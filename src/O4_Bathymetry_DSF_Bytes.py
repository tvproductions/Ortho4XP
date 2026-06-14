from __future__ import annotations

"""Extract and validate raw bathymetry raster atoms from DSF bytes.

This module only understands the DSF envelope:

* reject corrupt headers before any raster-specific parsing;
* scan top-level atoms before the trailing checksum;
* extract ``DEMN`` from the ``DEFN`` super-atom;
* preserve the top-level ``DEMS`` payload unchanged;
* delegate raster-name, metadata, and payload validation to the raster parser.

Keeping byte extraction separate from source lookup lets tests validate tiny DSF
fixtures without depending on an X-Plane install or the 7z executable.
"""

import io
from dataclasses import dataclass

from O4_Bathymetry_DSF_Atoms import AtomReadContext, read_atom
from O4_Bathymetry_Models import BathymetryErrorContext, ValidatedRasterBytes
from O4_Bathymetry_Raster_Parser import validate_raster_payload


@dataclass
class _RawRasterAtoms:
    demn: bytes | None = None
    dems: bytes | None = None


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
    context = AtomReadContext(stream, atoms_end, errors, "DSF")
    while stream.tell() < atoms_end:
        _read_next_dsf_atom(context, atoms)
    return atoms


def _read_next_dsf_atom(context, atoms):
    atom_start = context.stream.tell()
    header, payload = read_atom(context)
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
    context = AtomReadContext(stream, len(payload), errors, "DEFN")
    while stream.tell() < len(payload):
        header, data = read_atom(context)
        if header == "DEMN":
            return data
    raise errors.error("missing DEMN raster definitions")
