"""Non-destructive DSFTool bridge for native XP12 DSF header text.

The bridge runs after Ortho4XP has finished writing its binary ortho DSF temp
file.  It converts the default Global Scenery DSF and generated ortho DSF to
DSFTool text, copies only parser-approved header lines into a staged text file,
and replaces the generated temp DSF only after DSFTool successfully repacks the
staged text.  Missing tools, missing default scenery, unsupported header text,
and conversion failures all leave the generated ortho DSF unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil

from O4_DSF_Header_Models import DsfHeaderBridgeRequest, DsfHeaderBridgeResult
from O4_DSF_Header_Text import (
    extract_supported_header_lines,
    splice_supported_header_lines,
)
import O4_File_Names as FNAMES


class _BridgeSkip(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class _BridgePaths:
    default_text: Path
    generated_text: Path
    spliced_text: Path
    staged_binary: Path

    def cleanup_paths(self) -> list[Path]:
        return [
            self.default_text,
            self.generated_text,
            self.spliced_text,
            self.staged_binary,
        ]


@dataclass
class _BridgeContext:
    request: DsfHeaderBridgeRequest
    default_dsf_path: Path
    tile_label: str
    paths: _BridgePaths
    cleanup_paths: list[Path]


def splice_native_dsf_headers_for_tile(tile, generated_dsf_path):
    import O4_Overlay_Utils as OVL
    import O4_Subprocess_Utils as SP
    import O4_UI_Utils as UI

    request = DsfHeaderBridgeRequest(
        lat=tile.lat,
        lon=tile.lon,
        generated_dsf_path=Path(generated_dsf_path),
        primary_overlay_src=OVL.custom_overlay_src,
        alternate_overlay_src=OVL.custom_overlay_src_alternate,
        tmp_dir=Path(FNAMES.Tmp_dir),
        dsftool_executable=OVL.dsftool_cmd,
        unzip_executable=OVL.unzip_cmd,
        run_external_tool=SP.run_external_tool,
    )
    result = splice_native_dsf_headers(request)
    _log_bridge_result(result, UI)
    return result


def splice_native_dsf_headers(request: DsfHeaderBridgeRequest) -> DsfHeaderBridgeResult:
    default_dsf_path = _find_default_dsf(request)
    if default_dsf_path is None:
        return DsfHeaderBridgeResult(False, "missing default DSF")
    try:
        context = _bridge_context(request, default_dsf_path)
        return _splice_native_dsf_headers(context)
    except OSError as exc:
        return DsfHeaderBridgeResult(False, f"I/O error: {exc}")


def _bridge_context(
    request: DsfHeaderBridgeRequest, default_dsf_path: Path
) -> _BridgeContext:
    request.tmp_dir.mkdir(parents=True, exist_ok=True)
    tile_label = FNAMES.short_latlon(request.lat, request.lon)
    paths = _bridge_paths(request.tmp_dir, tile_label)
    return _BridgeContext(
        request=request,
        default_dsf_path=default_dsf_path,
        tile_label=tile_label,
        paths=paths,
        cleanup_paths=paths.cleanup_paths(),
    )


def _splice_native_dsf_headers(context: _BridgeContext) -> DsfHeaderBridgeResult:
    try:
        return _apply_native_dsf_headers(context)
    except _BridgeSkip as skip:
        return DsfHeaderBridgeResult(False, skip.reason)
    finally:
        _cleanup_paths(context.cleanup_paths)


def _apply_native_dsf_headers(context: _BridgeContext) -> DsfHeaderBridgeResult:
    default_path = _default_path_for_dsftool(context)
    _require(
        _convert_dsf_to_text(context, default_path, context.paths.default_text),
        "default DSF text conversion failed",
    )
    supported_lines = extract_supported_header_lines(
        _read_text(context.paths.default_text)
    )
    _require(bool(supported_lines), "no supported native header lines")
    _require(
        _convert_dsf_to_text(
            context, context.request.generated_dsf_path, context.paths.generated_text
        ),
        "generated DSF text conversion failed",
    )
    _write_spliced_text(context, supported_lines)
    _require(_convert_text_to_dsf(context), "spliced DSF binary conversion failed")
    os.replace(context.paths.staged_binary, context.request.generated_dsf_path)
    return DsfHeaderBridgeResult(
        True, "native header lines spliced", len(supported_lines)
    )


def _default_path_for_dsftool(context: _BridgeContext) -> Path:
    default_path = _prepare_default_dsf_for_dsftool(context)
    _require(default_path is not None, "compressed default DSF extraction failed")
    if default_path is None:
        raise AssertionError("unreachable default DSF path")
    return default_path


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise _BridgeSkip(reason)


def _find_default_dsf(request: DsfHeaderBridgeRequest) -> Path | None:
    relative = (
        Path("Earth nav data") / f"{FNAMES.long_latlon(request.lat, request.lon)}.dsf"
    )
    for root in (request.primary_overlay_src, request.alternate_overlay_src):
        if not root:
            continue
        candidate = Path(root) / relative
        if candidate.exists():
            return candidate
    return None


def _prepare_default_dsf_for_dsftool(context: _BridgeContext) -> Path | None:
    if context.default_dsf_path.read_bytes()[:2] != b"7z":
        return context.default_dsf_path

    extracted_path = context.request.tmp_dir / f"{context.tile_label}.dsf"
    archive_path = Path(str(extracted_path) + ".7z")
    context.cleanup_paths.extend([archive_path, extracted_path])
    shutil.copy(context.default_dsf_path, extracted_path)
    os.replace(extracted_path, archive_path)
    result = context.request.run_external_tool(
        "7z",
        ["e", f"-o{context.request.tmp_dir}", str(archive_path)],
        executable=context.request.unzip_executable,
    )
    if not _tool_result_ok(result) or not extracted_path.exists():
        return None
    return extracted_path


def _bridge_paths(tmp_path: Path, tile_label: str) -> _BridgePaths:
    return _BridgePaths(
        default_text=tmp_path / f"{tile_label}_native_default.txt",
        generated_text=tmp_path / f"{tile_label}_ortho_generated.txt",
        spliced_text=tmp_path / f"{tile_label}_ortho_native_headers.txt",
        staged_binary=tmp_path / f"{tile_label}_ortho_native_headers.dsf",
    )


def _convert_dsf_to_text(
    context: _BridgeContext, source: Path, destination: Path
) -> bool:
    return _tool_result_ok(_run_dsftool(context, ["--dsf2text", source, destination]))


def _convert_text_to_dsf(context: _BridgeContext) -> bool:
    paths = context.paths
    return _tool_result_ok(
        _run_dsftool(context, ["--text2dsf", paths.spliced_text, paths.staged_binary])
    )


def _write_spliced_text(
    context: _BridgeContext, supported_lines: tuple[str, ...]
) -> None:
    spliced_text = splice_supported_header_lines(
        _read_text(context.paths.generated_text),
        supported_lines,
    )
    context.paths.spliced_text.write_text(spliced_text, encoding="utf-8", newline="\n")


def _run_dsftool(context: _BridgeContext, args):
    return context.request.run_external_tool(
        "DSFTool",
        [str(arg) for arg in args],
        executable=context.request.dsftool_executable,
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tool_result_ok(result) -> bool:
    return result is not None and getattr(result, "ok", False)


def _cleanup_paths(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink()
        except OSError:
            pass


def _log_bridge_result(result: DsfHeaderBridgeResult, UI) -> None:
    if result.applied:
        UI.vprint(
            1,
            "-> Native DSF header bridge applied:",
            result.supported_line_count,
            "header lines",
        )
        return
    UI.vprint(2, "-> Native DSF header bridge skipped:", result.reason)
