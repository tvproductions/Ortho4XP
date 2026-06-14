from __future__ import annotations

"""XP12 Global Scenery source lookup and DSF read path.

The source boundary is deliberately narrow: primary overlay root first,
alternate overlay root second, then a temporary DSF copy.  The copy may already
be an uncompressed DSF or a 7z archive that must be extracted through the
configured external tool.

All temporary DSF and ``.7z`` paths are removed after each attempt.  Payload
validation is delegated to the DSF byte extractor so this module remains about
provider selection, copy/read behavior, and actionable source-path errors.
"""

import os
import shutil
from contextlib import suppress
from pathlib import Path

import O4_File_Names as FNAMES
from O4_Bathymetry_DSF_Bytes import extract_validated_rasters_from_dsf_bytes
from O4_Bathymetry_Models import BathymetryErrorContext


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
        with suppress(OSError):
            candidate.unlink()


def _external_tool_failure_detail(result):
    error_summary = getattr(result, "error_summary", None)
    if error_summary:
        return f": {error_summary}"
    returncode = getattr(result, "returncode", None)
    if returncode is not None:
        return f": returncode {returncode}"
    return ""
