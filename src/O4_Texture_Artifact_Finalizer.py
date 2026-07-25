"""Finalize resolved DDS references before activating a generated DSF.

This facade coordinates three deliberately separate phases: validate worker
results, scan original terrain directives exactly once, then atomically commit
only the files whose canonical ``BASE_TEX_NOWRAP`` target changed.
"""

from pathlib import Path

import O4_Terrain_Artifact_Transaction as TAT
import O4_Texture_Artifact_Validation as TAV
from O4_Texture_Finalization_Models import TextureFinalizationError

_BASE_TEXTURE_PREFIX = "BASE_TEX_NOWRAP ../textures/"


def finalize_terrain_texture_references(tile, results):
    """Validate results, rewrite terrain files, and return the changed count."""
    mappings = TAV.validated_mappings(tile, results)
    if not mappings:
        return 0
    updated_files, matched = _terrain_updates(tile, mappings)
    _require_terrain_references(matched)
    TAT.replace_terrain_files_atomically(updated_files)
    return len(updated_files)


def _terrain_updates(tile, mappings):
    """Scan every generated terrain against the immutable original mapping."""
    changed = {
        requested: resolved
        for requested, resolved in mappings.items()
        if requested != resolved
    }
    updated_files = {}
    matched = dict.fromkeys(mappings, 0)
    terrain_dir = Path(tile.build_dir) / "terrain"
    try:
        for terrain_file in sorted(terrain_dir.glob("*.ter")):
            original = terrain_file.read_bytes()
            updated, file_matches = _rewrite_terrain_references(
                original,
                mappings,
                changed,
            )
            _merge_match_counts(matched, file_matches)
            if updated != original:
                updated_files[terrain_file] = (original, updated)
    except (OSError, UnicodeError) as exc:
        raise TextureFinalizationError(
            f"terrain reference validation failed: {exc}"
        ) from exc
    return updated_files, matched


def _merge_match_counts(matched, file_matches):
    """Accumulate exact requested references across all terrain files."""
    for requested_name, count in file_matches.items():
        matched[requested_name] += count


def _require_terrain_references(matched):
    """Reject successful resolutions that no generated terrain consumes."""
    missing = [name for name, count in matched.items() if count == 0]
    if missing:
        raise TextureFinalizationError(
            "resolved DDS not referenced by terrain: " + ", ".join(missing)
        )


def _rewrite_terrain_references(original, mappings, changed_mappings):
    """Rewrite exact directives once without cascading chained mappings."""
    matched = dict.fromkeys(mappings, 0)
    updated_lines = []
    for original_line in original.decode("utf-8").splitlines(keepends=True):
        updated_line, requested_name = _rewrite_terrain_line(
            original_line,
            mappings,
            changed_mappings,
        )
        if requested_name is not None:
            matched[requested_name] += 1
        updated_lines.append(updated_line)
    return "".join(updated_lines).encode("utf-8"), matched


def _rewrite_terrain_line(original_line, mappings, changed_mappings):
    """Return one rewritten line and the exact requested target it matched."""
    body = original_line.rstrip("\r\n")
    requested_name = _base_texture_target(body)
    if requested_name not in mappings:
        return original_line, None
    if requested_name not in changed_mappings:
        return original_line, requested_name
    line_ending = original_line[len(body) :]
    return (
        _BASE_TEXTURE_PREFIX + changed_mappings[requested_name] + line_ending,
        requested_name,
    )


def _base_texture_target(line):
    """Parse only the canonical terrain directive, excluding lookalikes."""
    if not line.startswith(_BASE_TEXTURE_PREFIX):
        return None
    return line[len(_BASE_TEXTURE_PREFIX) :]
