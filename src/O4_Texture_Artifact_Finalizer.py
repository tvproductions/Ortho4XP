import os
from pathlib import Path

import O4_File_Names as FNAMES

_BASE_TEXTURE_PREFIX = "BASE_TEX_NOWRAP ../textures/"


class TextureFinalizationError(RuntimeError):
    pass


def finalize_terrain_texture_references(tile, results):
    mappings = _validated_mappings(tile, results)
    if not mappings:
        return 0
    changed_mappings = {
        requested: resolved
        for requested, resolved in mappings.items()
        if requested != resolved
    }
    terrain_dir = Path(tile.build_dir) / "terrain"
    terrain_files = sorted(terrain_dir.glob("*.ter"))
    updated_files = {}
    matched = dict.fromkeys(mappings, 0)
    try:
        for terrain_file in terrain_files:
            original = terrain_file.read_bytes()
            updated_bytes, file_matches = _rewrite_terrain_references(
                original,
                mappings,
                changed_mappings,
            )
            for requested_name, count in file_matches.items():
                matched[requested_name] += count
            if updated_bytes != original:
                updated_files[terrain_file] = (original, updated_bytes)
    except (OSError, UnicodeError) as exc:
        raise TextureFinalizationError(
            f"terrain reference validation failed: {exc}"
        ) from exc
    missing = [name for name, count in matched.items() if count == 0]
    if missing:
        raise TextureFinalizationError(
            "resolved DDS not referenced by terrain: " + ", ".join(missing)
        )
    _replace_terrain_files_atomically(updated_files)
    return len(updated_files)


def _rewrite_terrain_references(original, mappings, changed_mappings):
    matched = dict.fromkeys(mappings, 0)
    updated_lines = []
    for original_line in original.decode("utf-8").splitlines(keepends=True):
        body = original_line.rstrip("\r\n")
        line_ending = original_line[len(body) :]
        if body.startswith(_BASE_TEXTURE_PREFIX):
            requested_name = body[len(_BASE_TEXTURE_PREFIX) :]
            if requested_name in mappings:
                matched[requested_name] += 1
                if requested_name in changed_mappings:
                    original_line = (
                        _BASE_TEXTURE_PREFIX
                        + changed_mappings[requested_name]
                        + line_ending
                    )
        updated_lines.append(original_line)
    return "".join(updated_lines).encode("utf-8"), matched


def _validated_mappings(tile, results):
    mappings = {}
    output_names = set()
    for result in results:
        if not result.ok:
            raise TextureFinalizationError(
                f"texture conversion failed: {result.display_name}"
            )
        if not isinstance(result.display_name, str) or not result.display_name:
            raise TextureFinalizationError(
                f"invalid texture display name: {result.display_name!r}"
            )
        requested_attrs = result.requested_attrs
        resolved_attrs = result.resolved_attrs
        if requested_attrs is None and resolved_attrs is None:
            raise TextureFinalizationError(
                f"missing texture resolution metadata: {result.display_name}"
            )
        if requested_attrs is None or resolved_attrs is None:
            raise TextureFinalizationError(
                f"incomplete texture resolution metadata: {result.display_name}"
            )
        requested_attrs = _validated_texture_attrs(
            "requested",
            requested_attrs,
            result.display_name,
        )
        resolved_attrs = _validated_texture_attrs(
            "resolved",
            resolved_attrs,
            result.display_name,
        )
        if requested_attrs[:3] != resolved_attrs[:3]:
            raise TextureFinalizationError(
                "requested/resolved texture coordinates and zoom differ: "
                f"{requested_attrs[:3]}, {resolved_attrs[:3]}"
            )
        if resolved_attrs[3] != result.provider_code:
            raise TextureFinalizationError(
                "resolved provider mismatch: "
                f"{resolved_attrs[3]}, {result.provider_code}"
            )
        requested_name = FNAMES.dds_file_name_from_attributes(*requested_attrs)
        resolved_name = FNAMES.dds_file_name_from_attributes(*resolved_attrs)
        if result.display_name != resolved_name:
            raise TextureFinalizationError(
                "resolved DDS display name mismatch: "
                f"{result.display_name}, {resolved_name}"
            )
        output_names.add(resolved_name)
        previous = mappings.setdefault(requested_name, resolved_name)
        if previous != resolved_name:
            raise TextureFinalizationError(
                f"conflicting resolutions for {requested_name}: "
                f"{previous}, {resolved_name}"
            )
    texture_dir = Path(tile.build_dir) / "textures"
    missing_outputs = sorted(
        name for name in output_names if not (texture_dir / name).is_file()
    )
    if missing_outputs:
        raise TextureFinalizationError(
            "missing DDS output: " + ", ".join(missing_outputs)
        )
    return mappings


def _validated_texture_attrs(label, attrs, display_name):
    if not isinstance(attrs, tuple) or len(attrs) != 4:
        raise TextureFinalizationError(
            f"invalid {label} texture attributes for {display_name}: {attrs!r}"
        )
    til_x_left, til_y_top, zoomlevel, provider_code = attrs
    if any(type(value) is not int for value in (til_x_left, til_y_top, zoomlevel)):
        raise TextureFinalizationError(
            f"invalid {label} texture attributes for {display_name}: {attrs!r}"
        )
    if not isinstance(provider_code, str) or not provider_code:
        raise TextureFinalizationError(
            f"invalid {label} texture attributes for {display_name}: {attrs!r}"
        )
    return attrs


def _replace_terrain_files_atomically(updated_files):
    staged = []
    try:
        for terrain_file, (original, updated) in updated_files.items():
            candidate = terrain_file.with_name(terrain_file.name + ".finalizing")
            backup = terrain_file.with_name(terrain_file.name + ".finalizing-backup")
            staged.append((terrain_file, candidate, backup))
            candidate.write_bytes(updated)
            backup.write_bytes(original)
    except OSError as exc:
        _cleanup_staged_files(staged)
        raise TextureFinalizationError(
            f"atomic terrain rewrite failed before replacement: {exc}"
        ) from exc

    replaced = []
    try:
        for terrain_file, candidate, backup in staged:
            os.replace(candidate, terrain_file)
            replaced.append((terrain_file, backup))
    except OSError as exc:
        rollback_errors, retained_backups = _rollback_replaced_files(replaced)
        _cleanup_staged_files(staged, preserve=retained_backups)
        message = f"atomic terrain rewrite failed: {exc}"
        if rollback_errors:
            message += "; rollback failed: " + ", ".join(rollback_errors)
        raise TextureFinalizationError(message) from exc

    _cleanup_staged_files(staged)


def _rollback_replaced_files(replaced):
    errors = []
    retained_backups = set()
    for terrain_file, backup in reversed(replaced):
        try:
            os.replace(backup, terrain_file)
        except OSError as exc:
            retained_backups.add(backup)
            errors.append(
                f"{terrain_file}: {exc}; original backup retained at {backup}"
            )
    return errors, retained_backups


def _cleanup_staged_files(staged, preserve=()):
    preserved_paths = set(preserve)
    for _terrain_file, candidate, backup in staged:
        for path in (candidate, backup):
            if path in preserved_paths:
                continue
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
