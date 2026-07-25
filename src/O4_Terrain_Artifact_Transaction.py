"""Atomically replace generated terrain files with rollback preservation.

Every candidate and backup is staged beside its terrain file so ``os.replace``
has same-filesystem semantics.  Preparation failures remove partial staging;
commit failures restore already-replaced originals; failed rollback keeps the
exact recoverable backup and reports its path.
"""

import contextlib
import os

from O4_Texture_Finalization_Models import TextureFinalizationError


def replace_terrain_files_atomically(updated_files):
    """Stage all terrain updates before committing any replacement."""
    staged = _stage_terrain_files(updated_files)
    _commit_staged_terrain_files(staged)


def _stage_terrain_files(updated_files):
    """Write same-directory candidates and byte-identical backups."""
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
    return staged


def _commit_staged_terrain_files(staged):
    """Commit candidates in order and roll back the committed prefix on error."""
    replaced = []
    try:
        for terrain_file, candidate, backup in staged:
            os.replace(candidate, terrain_file)
            replaced.append((terrain_file, backup))
    except OSError as exc:
        _raise_commit_failure(exc, replaced, staged)
    _cleanup_staged_files(staged)


def _raise_commit_failure(exc, replaced, staged):
    """Raise one error containing any recoverable rollback evidence."""
    rollback_errors, retained_backups = _rollback_replaced_files(replaced)
    _cleanup_staged_files(staged, preserve=retained_backups)
    message = f"atomic terrain rewrite failed: {exc}"
    if rollback_errors:
        message += "; rollback failed: " + ", ".join(rollback_errors)
    raise TextureFinalizationError(message) from exc


def _rollback_replaced_files(replaced):
    """Restore originals in reverse commit order and retain failed backups."""
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
    """Remove candidates and consumed backups except explicit recovery files."""
    preserved_paths = set(preserve)
    for _terrain_file, candidate, backup in staged:
        _unlink_staged_file(candidate, preserved_paths)
        _unlink_staged_file(backup, preserved_paths)


def _unlink_staged_file(path, preserved_paths):
    """Best-effort cleanup must never hide the transaction's primary error."""
    if path in preserved_paths:
        return
    with contextlib.suppress(FileNotFoundError, OSError):
        path.unlink()
