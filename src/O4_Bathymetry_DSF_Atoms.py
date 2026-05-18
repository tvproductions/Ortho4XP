from __future__ import annotations

"""Shared DSF atom reader for bathymetry input parsing.

DSF atom ids are stored reversed on disk and atom lengths include the eight-byte
header.  The reader centralizes those details so source, DSF envelope, and DEMS
payload parsers all report malformed headers, lengths, and payloads with the
same tile/source context.
"""

from dataclasses import dataclass
import io
import struct

from O4_Bathymetry_Models import BathymetryErrorContext


@dataclass(frozen=True)
class AtomReadContext:
    stream: io.BytesIO
    total_len: int
    errors: BathymetryErrorContext
    atom_table_name: str = "DEMS"


def read_atom(context):
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
