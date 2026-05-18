# Bathymetry Input Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce a validated XP12 bathymetry input contract for water tiles before DSF encoding.

**Architecture:** Add a focused `O4_Bathymetry_Input.py` boundary that parses and validates XP12 Global Scenery DSF raster definitions/data. Integrate it into `O4_DSF_Utils.build_dsf()` after mesh water classification, so all-land tiles skip validation and water tiles fail before output DSF writing if bathymetry is missing or invalid.

**Tech Stack:** Python 3.13, standard-library `unittest`, NumPy, existing Ortho4XP `O4_*` modules, Ruff, ty, repo quality-check.

---

## File Map

- Create `src/O4_Bathymetry_Input.py`
  - Owns bathymetry provider boundary, DSF raster atom parsing, validation, and domain error types.
  - Has no GUI dependency and no tile-build side effects.
- Create `tests/test_bathymetry_input.py`
  - Owns in-memory DSF/raster fixtures and focused unit tests.
- Modify `src/O4_DSF_Utils.py`
  - Delegates existing Global Scenery raster extraction to `O4_Bathymetry_Input`.
  - Gates extraction on whether remapped mesh triangle types include water.
  - Converts bathymetry validation failures into user-facing hard build failures.
- Modify `TODO.md`
  - Mark TODO-014 done only after implementation, verification, GitHub Issue #9 evidence, and issue closeout.
- Modify `.codex/skills/quality-check/complexity-baseline.json` only if the full quality gate requires a baseline update for intentional new code size/complexity.

## Task 1: Add Failing Parser And Validation Tests

**Files:**
- Create: `tests/test_bathymetry_input.py`
- Later implementation target: `src/O4_Bathymetry_Input.py`

- [ ] **Step 1: Create failing tests for raster atom parsing and validation**

Create `tests/test_bathymetry_input.py` with this content:

```python
import struct
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Bathymetry_Input import (
    BathymetryInputError,
    RasterPayload,
    validate_raster_payload,
)


def atom(name: bytes, payload: bytes) -> bytes:
    return name[::-1] + struct.pack("<I", len(payload) + 8) + payload


def demn_payload(*names: str) -> bytes:
    return b"".join(name.encode("ascii") + b"\0" for name in names)


def demi(width: int, height: int, bytes_per_pixel: int = 2) -> bytes:
    flags = 1
    return struct.pack(
        "<BBHIIff",
        1,
        bytes_per_pixel,
        flags,
        width,
        height,
        1.0,
        0.0,
    )


def demd(width: int, height: int, bytes_per_pixel: int = 2, value: int = 7) -> bytes:
    if bytes_per_pixel == 1:
        return bytes([value]) * width * height
    if bytes_per_pixel == 2:
        return struct.pack("<" + "h" * width * height, *([value] * width * height))
    raise AssertionError("fixture only supports 1 or 2 byte pixels")


def dems_payload(
    *,
    elevation_size: tuple[int, int] = (2, 2),
    sea_level_size: tuple[int, int] = (2, 2),
    include_sea_level: bool = True,
    empty_sea_level: bool = False,
) -> bytes:
    elevation = atom("IMED".encode("ascii"), demi(*elevation_size)) + atom(
        "DMED".encode("ascii"), demd(*elevation_size)
    )
    if not include_sea_level:
        return elevation
    sea_data = b"" if empty_sea_level else demd(*sea_level_size)
    return (
        elevation
        + atom("IMED".encode("ascii"), demi(*sea_level_size))
        + atom("DMED".encode("ascii"), sea_data)
    )


class BathymetryInputTests(unittest.TestCase):
    def test_valid_payload_requires_elevation_and_sea_level(self):
        payload = validate_raster_payload(
            demn_payload("elevation", "sea_level"),
            dems_payload(),
            tile_label="+12-123",
            source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
        )

        self.assertIsInstance(payload, RasterPayload)
        self.assertEqual(payload.layer_names, ("elevation", "sea_level"))
        self.assertEqual(payload.elevation.width, 2)
        self.assertEqual(payload.elevation.height, 2)
        self.assertEqual(payload.bathymetry.width, 2)
        self.assertEqual(payload.bathymetry.height, 2)

    def test_missing_sea_level_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*sea_level.*XP12 Global Scenery",
        ):
            validate_raster_payload(
                demn_payload("elevation"),
                dems_payload(include_sea_level=False),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_empty_sea_level_payload_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*sea_level.*empty",
        ):
            validate_raster_payload(
                demn_payload("elevation", "sea_level"),
                dems_payload(empty_sea_level=True),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_mismatched_bathymetry_shape_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*sea_level.*2x3.*elevation.*2x2",
        ):
            validate_raster_payload(
                demn_payload("elevation", "sea_level"),
                dems_payload(sea_level_size=(2, 3)),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_malformed_dems_payload_is_rejected(self):
        with self.assertRaisesRegex(
            BathymetryInputError,
            r"\+12-123.*malformed.*DEMS",
        ):
            validate_raster_payload(
                demn_payload("elevation", "sea_level"),
                b"too-short",
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
uv run python -m unittest tests.test_bathymetry_input -q
```

Expected: fail with `ModuleNotFoundError: No module named 'O4_Bathymetry_Input'`.

- [ ] **Step 3: Commit the failing tests**

Run:

```bash
git add tests/test_bathymetry_input.py
git commit -m "test: cover bathymetry input validation"
```

## Task 2: Implement Raster Payload Parser And Validator

**Files:**
- Create: `src/O4_Bathymetry_Input.py`
- Test: `tests/test_bathymetry_input.py`

- [ ] **Step 1: Add the bathymetry input module**

Create `src/O4_Bathymetry_Input.py` with this content:

```python
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
    _validate_raster_data(elevation, tile_label, source_path)
    _validate_raster_data(bathymetry, tile_label, source_path)
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
    try:
        names = tuple(
            part.decode("ascii") for part in demn.rstrip(b"\0").split(b"\0") if part
        )
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
    return header[::-1].decode("ascii"), payload


def _parse_demi(
    payload: bytes,
    tile_label: str,
    source_path: str,
) -> _RasterMetadata:
    if len(payload) < 18:
        raise _error(tile_label, source_path, "malformed DEMI raster metadata")
    _version, bytes_per_pixel, flags, width, height, _scale, _offset = struct.unpack(
        "<BBHIIff", payload[:18]
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
```

- [ ] **Step 2: Run the parser tests and verify they pass**

Run:

```bash
uv run python -m unittest tests.test_bathymetry_input -q
```

Expected: `OK`.

- [ ] **Step 3: Run Ruff on the new files**

Run:

```bash
uv run ruff check src/O4_Bathymetry_Input.py tests/test_bathymetry_input.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run ty on the new module**

Run:

```bash
uv run ty check src/O4_Bathymetry_Input.py
```

Expected: no errors for `src/O4_Bathymetry_Input.py`.

- [ ] **Step 5: Commit the parser and validator**

Run:

```bash
git add src/O4_Bathymetry_Input.py tests/test_bathymetry_input.py
git commit -m "Add XP12 bathymetry raster validator"
```

## Task 3: Add Global Scenery Provider Extraction Tests

**Files:**
- Modify: `tests/test_bathymetry_input.py`
- Modify: `src/O4_Bathymetry_Input.py`

- [ ] **Step 1: Add in-memory DSF fixture helpers and provider tests**

Append these helpers and tests to `tests/test_bathymetry_input.py`, before the `if __name__ == "__main__":` block:

```python
def dsf_file(*, demn: bytes, dems: bytes) -> bytes:
    body = atom("NFED".encode("ascii"), atom("NMED".encode("ascii"), demn))
    body += atom("SMED".encode("ascii"), dems)
    return b"XPLNEDSF" + struct.pack("<I", 1) + body + (b"0" * 16)


class GlobalSceneryProviderTests(unittest.TestCase):
    def test_extract_validated_global_scenery_rasters(self):
        from O4_Bathymetry_Input import extract_validated_rasters_from_dsf_bytes

        demn = demn_payload("elevation", "sea_level")
        dems = dems_payload()
        result = extract_validated_rasters_from_dsf_bytes(
            dsf_file(demn=demn, dems=dems),
            tile_label="+12-123",
            source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
        )

        self.assertEqual(result.demn, demn)
        self.assertEqual(result.dems, dems)
        self.assertEqual(result.payload.bathymetry.name, "sea_level")

    def test_rejects_dsf_without_required_rasters(self):
        from O4_Bathymetry_Input import extract_validated_rasters_from_dsf_bytes

        with self.assertRaisesRegex(BathymetryInputError, r"missing sea_level"):
            extract_validated_rasters_from_dsf_bytes(
                dsf_file(demn=demn_payload("elevation"), dems=dems_payload(include_sea_level=False)),
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )

    def test_rejects_corrupted_dsf_header(self):
        from O4_Bathymetry_Input import extract_validated_rasters_from_dsf_bytes

        with self.assertRaisesRegex(BathymetryInputError, r"corrupted DSF"):
            extract_validated_rasters_from_dsf_bytes(
                b"not-a-dsf",
                tile_label="+12-123",
                source_path="XP12/Earth nav data/+10-130/+12-123.dsf",
            )
```

If Ruff reports a long line for the `dsf_file(...)` call in `test_rejects_dsf_without_required_rasters`, split the arguments exactly as Ruff requests.

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
uv run python -m unittest tests.test_bathymetry_input -q
```

Expected: fail because `extract_validated_rasters_from_dsf_bytes` is not defined.

- [ ] **Step 3: Implement DSF byte extraction and return type**

Update `src/O4_Bathymetry_Input.py`:

1. Add this dataclass after `RasterPayload`:

```python
@dataclass(frozen=True)
class ValidatedRasterBytes:
    demn: bytes
    dems: bytes
    payload: RasterPayload
```

2. Add these functions before `_parse_layer_names`:

```python
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
        header, payload = _read_atom(stream, atoms_end, tile_label, source_path)
        if header == "NFED":
            demn = _extract_demn_from_defn(payload, tile_label, source_path)
        elif header == "SMED":
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
        header, data = _read_atom(stream, total_len, tile_label, source_path)
        if header == "NMED":
            return data
    raise _error(tile_label, source_path, "missing DEMN raster definitions")
```

- [ ] **Step 4: Run tests and quality commands for the new provider code**

Run:

```bash
uv run python -m unittest tests.test_bathymetry_input -q
uv run ruff check src/O4_Bathymetry_Input.py tests/test_bathymetry_input.py
uv run ty check src/O4_Bathymetry_Input.py
```

Expected: all pass.

- [ ] **Step 5: Commit the provider byte extraction**

Run:

```bash
git add src/O4_Bathymetry_Input.py tests/test_bathymetry_input.py
git commit -m "Validate XP12 Global Scenery raster payloads"
```

## Task 4: Move DSF File Loading Into The Provider Boundary

**Files:**
- Modify: `src/O4_Bathymetry_Input.py`
- Modify: `tests/test_bathymetry_input.py`

- [ ] **Step 1: Add tests for source lookup and missing files**

Append this test class to `tests/test_bathymetry_input.py`, before the `if __name__ == "__main__":` block:

```python
import tempfile
from pathlib import Path
from unittest import mock


class BathymetrySourceLookupTests(unittest.TestCase):
    def test_missing_global_scenery_dsf_is_rejected(self):
        from O4_Bathymetry_Input import extract_validated_global_scenery_rasters

        with tempfile.TemporaryDirectory() as tmp:
            missing_primary = str(Path(tmp) / "primary")
            missing_alternate = str(Path(tmp) / "alternate")
            with self.assertRaisesRegex(
                BathymetryInputError,
                r"custom_overlay_src.*custom_overlay_src_alternate.*XP12 Global Scenery",
            ):
                extract_validated_global_scenery_rasters(
                    12,
                    -123,
                    primary_overlay_src=missing_primary,
                    alternate_overlay_src=missing_alternate,
                    tmp_dir=str(Path(tmp) / "tmp"),
                    unzip_executable="7z",
                    run_external_tool=lambda *args, **kwargs: None,
                )

    def test_reads_uncompressed_global_scenery_dsf(self):
        from O4_Bathymetry_Input import extract_validated_global_scenery_rasters

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            dsf_path = root / "Earth nav data" / "+10-130.dsf"
            dsf_path.parent.mkdir(parents=True)
            dsf_path.write_bytes(
                dsf_file(
                    demn=demn_payload("elevation", "sea_level"),
                    dems=dems_payload(),
                )
            )

            result = extract_validated_global_scenery_rasters(
                12,
                -123,
                primary_overlay_src=str(root),
                alternate_overlay_src="",
                tmp_dir=str(Path(tmp) / "tmp"),
                unzip_executable="7z",
                run_external_tool=mock.Mock(),
            )

        self.assertEqual(result.payload.bathymetry.name, "sea_level")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
uv run python -m unittest tests.test_bathymetry_input -q
```

Expected: fail because `extract_validated_global_scenery_rasters` is not defined.

- [ ] **Step 3: Implement source lookup for uncompressed DSFs**

Update `src/O4_Bathymetry_Input.py`:

1. Add imports near the top:

```python
import os
from pathlib import Path
import shutil

import O4_File_Names as FNAMES
```

2. Add this function before `extract_validated_rasters_from_dsf_bytes`:

```python
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
```

3. Remove the unused `os` import if Ruff reports it is unnecessary after edits. It is needed by `_read_uncompressed_or_7z_dsf`.

- [ ] **Step 4: Run focused validation**

Run:

```bash
uv run python -m unittest tests.test_bathymetry_input -q
uv run ruff check src/O4_Bathymetry_Input.py tests/test_bathymetry_input.py
uv run ty check src/O4_Bathymetry_Input.py
```

Expected: all pass.

- [ ] **Step 5: Commit source lookup**

Run:

```bash
git add src/O4_Bathymetry_Input.py tests/test_bathymetry_input.py
git commit -m "Add XP12 Global Scenery bathymetry provider"
```

## Task 5: Integrate The Bathymetry Boundary Into DSF Build

**Files:**
- Modify: `src/O4_DSF_Utils.py`
- Modify: `tests/test_bathymetry_input.py`
- Modify: `tests/test_config_models.py`

- [ ] **Step 1: Add tests for water gating helper**

Append this test class to `tests/test_bathymetry_input.py`, before the `if __name__ == "__main__":` block:

```python
class BathymetryWaterGateTests(unittest.TestCase):
    def test_all_land_tiles_do_not_require_bathymetry(self):
        from O4_DSF_Utils import mesh_requires_bathymetry

        self.assertFalse(mesh_requires_bathymetry([0, 0, 0]))

    def test_water_tiles_require_bathymetry(self):
        from O4_DSF_Utils import mesh_requires_bathymetry

        self.assertTrue(mesh_requires_bathymetry([0, 1, 0]))
        self.assertTrue(mesh_requires_bathymetry([0, 2, 0]))
```

- [ ] **Step 2: Add regression text checks**

Append these test methods to `ConfigModelTests` in `tests/test_config_models.py`:

```python
    def test_dsf_generation_uses_bathymetry_input_boundary(self):
        dsf_source = Path("src/O4_DSF_Utils.py").read_text()
        self.assertIn("extract_elevation_and_bathymetry_data", dsf_source)
        self.assertIn("mesh_requires_bathymetry", dsf_source)
        self.assertIn("O4_Bathymetry_Input", dsf_source)

    def test_masks_are_not_treated_as_bathymetry_source(self):
        bathy_source = Path("src/O4_Bathymetry_Input.py").read_text()
        self.assertNotIn("distance_masks_too", bathy_source)
        self.assertNotIn("ratio_bathy", bathy_source)
        self.assertNotIn("node_bathy", bathy_source)
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
uv run python -m unittest tests.test_bathymetry_input tests.test_config_models -q
```

Expected: fail because `mesh_requires_bathymetry` does not exist and `O4_DSF_Utils.py` does not import the boundary yet.

- [ ] **Step 4: Update DSF imports**

In `src/O4_DSF_Utils.py`, add this import with the other `O4_*` imports:

```python
import O4_Bathymetry_Input as BATHY_INPUT
```

- [ ] **Step 5: Replace old inline extraction with boundary delegation**

Replace the body of `extract_elevation_and_bathymetry_data(lat, lon)` in `src/O4_DSF_Utils.py` with:

```python
def extract_elevation_and_bathymetry_data(lat, lon):
    UI.vprint(1, "     Extracting XP12 rasters from X-Plane Global Scenery")
    result = BATHY_INPUT.extract_validated_global_scenery_rasters(
        lat,
        lon,
        primary_overlay_src=OVL.custom_overlay_src,
        alternate_overlay_src=OVL.custom_overlay_src_alternate,
        tmp_dir=FNAMES.Tmp_dir,
        unzip_executable=OVL.unzip_cmd,
        run_external_tool=SP.run_external_tool,
    )
    return (result.demn, result.dems)
```

- [ ] **Step 6: Add bathymetry gate helper**

Add this helper near `extract_elevation_and_bathymetry_data()` in `src/O4_DSF_Utils.py`:

```python
def mesh_requires_bathymetry(tri_types):
    return any(tri_type in (1, 2) for tri_type in tri_types)
```

- [ ] **Step 7: Move raster extraction before DSF file writing and gate it**

In `build_dsf()`, after the `node_bathy = BATHY.compute_depth_ratio_bounds_from_masks(...)` block and before `UI.vprint(1, "-> Computing point pools and texture requirements")`, insert:

```python
    if mesh_requires_bathymetry(tri_types):
        try:
            (bDEMN, bDEMS) = extract_elevation_and_bathymetry_data(tile.lat, tile.lon)
        except BATHY_INPUT.BathymetryInputError as exc:
            UI.exit_message_and_bottom_line("\nERROR:", exc)
            return 0
    else:
        UI.vprint(1, "-> No water triangles detected; skipping XP12 bathymetry input")
        bDEMN = b""
        bDEMS = b""
```

Then remove the later block near DSF writing:

```python
    # Transfer DEM and bathymetry raster from Global Scenery tiles
    (bDEMN, bDEMS) = extract_elevation_and_bathymetry_data(tile.lat, tile.lon)
```

Do not leave a second extraction call after output file backup/rename. Bathymetry failure must happen before `os.replace(dsf_file_name, dsf_file_name + ".bak")`.

- [ ] **Step 8: Remove now-unused imports**

In `src/O4_DSF_Utils.py`, remove imports that only supported the old inline extractor if Ruff reports them unused:

```python
import io
import shutil
```

Keep `struct`, `os`, `array`, `hashlib`, `numpy`, and `Image` if still used.

- [ ] **Step 9: Run focused tests and static checks**

Run:

```bash
uv run python -m unittest tests.test_bathymetry_input tests.test_config_models -q
uv run ruff check src/O4_Bathymetry_Input.py src/O4_DSF_Utils.py tests/test_bathymetry_input.py tests/test_config_models.py
uv run ty check src/O4_Bathymetry_Input.py src/O4_DSF_Utils.py
```

Expected: all pass. If ty reports existing errors in `src/O4_DSF_Utils.py` unrelated to the touched code, record them and run ty on `src/O4_Bathymetry_Input.py` plus any smaller changed files. Do not ignore new ty errors introduced by this task.

- [ ] **Step 10: Commit DSF integration**

Run:

```bash
git add src/O4_DSF_Utils.py tests/test_bathymetry_input.py tests/test_config_models.py
git commit -m "Require bathymetry input for XP12 water tiles"
```

## Task 6: Close TODO-014 Tracking And Verify

**Files:**
- Modify: `TODO.md`
- Possibly modify: `.codex/skills/quality-check/complexity-baseline.json`

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
uv run python -m unittest tests.test_bathymetry_input tests.test_config_models -q
```

Expected: `OK`.

- [ ] **Step 2: Run broader unit tests**

Run:

```bash
uv run python -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 3: Run Ruff**

Run:

```bash
uv run ruff check Ortho4XP.py src tests
```

Expected: `All checks passed!`

- [ ] **Step 4: Run ty on changed Python files**

Run:

```bash
uv run ty check src/O4_Bathymetry_Input.py src/O4_DSF_Utils.py tests/test_bathymetry_input.py tests/test_config_models.py
```

Expected: no new type errors. If ty cannot check test files cleanly because the repo baseline excludes tests, run the command on changed `src` files and record the limitation in the evidence.

- [ ] **Step 5: Run full quality check**

Run:

```bash
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected: full quality gate passes. If it fails only because intentional new module size/complexity is not in the baseline, inspect the report, update `.codex/skills/quality-check/complexity-baseline.json` using the project-local baseline workflow, and rerun the full quality check.

- [ ] **Step 6: Update TODO-014**

In `TODO.md`, change TODO-014 to:

```markdown
### TODO-014: Require Valid Bathymetry Inputs for Physical Water Meshes

Status: Done

GitHub Issue: #9 (closed)

Make XP12 3D bathymetry requirements explicit before deeper mesh rewrites.

Completed by adding a source-agnostic bathymetry input boundary, validating XP12
Global Scenery raster definitions and data for water tiles, skipping
bathymetry validation for all-land tiles, rejecting missing or malformed
`sea_level` raster data with actionable errors, and preserving mask-derived
depth ratios as blend/control data rather than bathymetry sources.
```

Keep the existing acceptance criteria and labels below that block unless implementation details require a precise wording update.

- [ ] **Step 7: Comment on GitHub Issue #9 with evidence**

Run:

```bash
gh issue comment 9 --repo tvproductions/Ortho4XP --body "Implemented TODO-014 bathymetry input validation. Evidence: focused bathymetry/config tests passed; full unittest discovery passed; Ruff passed; ty passed on changed Python files; full quality-check passed. The implementation validates XP12 Global Scenery DEMN/DEMS raster payloads for water tiles, requires sea_level bathymetry, skips all-land tiles, and preserves mask-derived depth ratios as controls only."
```

Expected: GitHub CLI reports the comment URL.

- [ ] **Step 8: Close GitHub Issue #9**

Run:

```bash
gh issue close 9 --repo tvproductions/Ortho4XP --reason completed --comment "Closing after TODO-014 implementation and full repository verification passed."
```

Expected: issue closes as completed.

- [ ] **Step 9: Commit closeout changes**

Run:

```bash
git add TODO.md .codex/skills/quality-check/complexity-baseline.json
git commit -m "Close TODO-014 bathymetry validation"
```

If the complexity baseline was not modified, run:

```bash
git add TODO.md
git commit -m "Close TODO-014 bathymetry validation"
```

- [ ] **Step 10: Final state check**

Run:

```bash
git diff --stat
git status --short --branch
git log --oneline -5
```

Expected: no unstaged/uncommitted changes, branch ahead of origin by the new implementation commits.

## Self-Review Notes

- Spec coverage:
  - Source-agnostic boundary: Tasks 2-4.
  - XP12 Global Scenery only provider: Tasks 3-4.
  - Water-only validation gate: Task 5.
  - All-land skip: Task 5 tests.
  - Mask-derived data not accepted as bathymetry: Task 5 regression test.
  - Deterministic tests without X-Plane install: Tasks 1, 3, 4, and 5 use in-memory fixtures/temp dirs.
  - ROADMAP note: already committed with the approved spec in `5ba16de`.
  - TODO/GitHub closeout: Task 6.
- Placeholder scan: no placeholder implementation steps remain; all code-bearing steps include concrete code.
- Type consistency: core names are `BathymetryInputError`, `RasterInfo`, `RasterPayload`, `ValidatedRasterBytes`, `validate_raster_payload`, `extract_validated_rasters_from_dsf_bytes`, `extract_validated_global_scenery_rasters`, and `mesh_requires_bathymetry`.
