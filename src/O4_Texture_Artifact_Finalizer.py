import os
from pathlib import Path

import O4_File_Names as FNAMES


class TextureFinalizationError(RuntimeError):
    pass


def finalize_terrain_texture_references(tile, results):
    mappings = _validated_mappings(tile, results)
    if not mappings:
        return 0
    terrain_dir = Path(tile.build_dir) / "terrain"
    terrain_files = sorted(terrain_dir.glob("*.ter"))
    updated_files = {}
    matched = dict.fromkeys(mappings, 0)
    try:
        for terrain_file in terrain_files:
            original = terrain_file.read_bytes()
            updated = original.decode("utf-8")
            for requested_name, resolved_name in mappings.items():
                old_line = f"BASE_TEX_NOWRAP ../textures/{requested_name}"
                new_line = f"BASE_TEX_NOWRAP ../textures/{resolved_name}"
                count = updated.count(old_line)
                if count:
                    matched[requested_name] += count
                    updated = updated.replace(old_line, new_line)
            updated_bytes = updated.encode("utf-8")
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


def _validated_mappings(tile, results):
    mappings = {}
    output_names = set()
    for result in results:
        if not result.ok:
            raise TextureFinalizationError(
                f"texture conversion failed: {result.display_name}"
            )
        requested_attrs = result.requested_attrs
        resolved_attrs = result.resolved_attrs
        if (requested_attrs is None) != (resolved_attrs is None):
            raise TextureFinalizationError(
                f"incomplete texture resolution metadata: {result.display_name}"
            )
        if requested_attrs is None:
            output_names.add(result.display_name)
            continue
        requested_name = FNAMES.dds_file_name_from_attributes(*requested_attrs)
        resolved_name = FNAMES.dds_file_name_from_attributes(*resolved_attrs)
        if result.display_name != resolved_name:
            raise TextureFinalizationError(
                f"resolved DDS name mismatch: {result.display_name}, {resolved_name}"
            )
        output_names.add(resolved_name)
        if requested_name == resolved_name:
            continue
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
        rollback_errors = _rollback_replaced_files(replaced)
        _cleanup_staged_files(staged)
        message = f"atomic terrain rewrite failed: {exc}"
        if rollback_errors:
            message += "; rollback failed: " + ", ".join(rollback_errors)
        raise TextureFinalizationError(message) from exc

    _cleanup_staged_files(staged)


def _rollback_replaced_files(replaced):
    errors = []
    for terrain_file, backup in reversed(replaced):
        try:
            os.replace(backup, terrain_file)
        except OSError as exc:
            errors.append(f"{terrain_file}: {exc}")
    return errors


def _cleanup_staged_files(staged):
    for _terrain_file, candidate, backup in staged:
        for path in (candidate, backup):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
