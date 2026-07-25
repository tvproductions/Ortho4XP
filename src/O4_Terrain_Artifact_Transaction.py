"""Atomically replace generated terrain files with rollback preservation.

Every candidate and backup is staged beside its terrain file so ``os.replace``
has same-filesystem semantics.  Preparation failures remove partial staging;
commit failures restore already-replaced originals; failed rollback keeps the
exact recoverable backup and reports its path.

Mode ownership is deliberately split across the transaction phases. Staging
copies the original mode to both possible replacement sources. Immediately
before each forward or rollback replacement, the existing destination becomes
temporarily writable for Windows, then returns to its original mode after
success or failure. Cleanup applies the same writable retry to unconsumed
staging without touching a backup retained as recovery evidence.
"""

import os
import shutil
import stat

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
            shutil.copymode(terrain_file, candidate)
            backup.write_bytes(original)
            shutil.copymode(terrain_file, backup)
    except OSError as exc:
        cleanup_errors = _cleanup_staged_files(staged)
        message = f"atomic terrain rewrite failed before replacement: {exc}"
        if cleanup_errors:
            message += "; staging cleanup failed: " + ", ".join(cleanup_errors)
        raise TextureFinalizationError(message) from exc
    return staged


def _commit_staged_terrain_files(staged):
    """Commit candidates in order and roll back the committed prefix on error."""
    replaced = []
    try:
        for terrain_file, candidate, backup in staged:
            original_mode = _replace_staged_file(candidate, terrain_file)
            replaced.append((terrain_file, backup))
            terrain_file.chmod(original_mode)
    except OSError as exc:
        _raise_commit_failure(exc, replaced, staged)
    cleanup_errors = _cleanup_staged_files(staged)
    if cleanup_errors:
        raise TextureFinalizationError(
            "atomic terrain rewrite cleanup failed: " + ", ".join(cleanup_errors)
        )


def _raise_commit_failure(exc, replaced, staged):
    """Raise one error containing any recoverable rollback evidence."""
    rollback_errors, retained_backups = _rollback_replaced_files(replaced)
    cleanup_errors = _cleanup_staged_files(staged, preserve=retained_backups)
    message = f"atomic terrain rewrite failed: {exc}"
    if rollback_errors:
        message += "; rollback failed: " + ", ".join(rollback_errors)
    if cleanup_errors:
        message += "; staging cleanup failed: " + ", ".join(cleanup_errors)
    raise TextureFinalizationError(message) from exc


def _rollback_replaced_files(replaced):
    """Restore originals in reverse commit order and retain failed backups."""
    errors = []
    retained_backups = set()
    for terrain_file, backup in reversed(replaced):
        try:
            original_mode = _replace_staged_file(backup, terrain_file)
            terrain_file.chmod(original_mode)
        except OSError as exc:
            if backup.exists():
                retained_backups.add(backup)
                evidence = f"; original backup retained at {backup}"
            else:
                evidence = "; original content restored but mode restoration failed"
            errors.append(f"{terrain_file}: {exc}{evidence}")
    return errors, retained_backups


def _replace_staged_file(source, destination):
    """Replace one file after temporarily making its destination writable."""
    original_mode = stat.S_IMODE(destination.stat().st_mode)
    if not original_mode & stat.S_IWRITE:
        destination.chmod(original_mode | stat.S_IWRITE)
    try:
        os.replace(source, destination)
    except OSError as exc:
        try:
            destination.chmod(original_mode)
        except FileNotFoundError:
            pass
        except OSError as mode_exc:
            raise OSError(
                f"{exc}; failed to restore destination mode: {mode_exc}"
            ) from exc
        raise
    return original_mode


def _cleanup_staged_files(staged, preserve=()):
    """Remove candidates and consumed backups except explicit recovery files."""
    preserved_paths = set(preserve)
    errors = []
    for _terrain_file, candidate, backup in staged:
        for path in (candidate, backup):
            error = _unlink_staged_file(path, preserved_paths)
            if error:
                errors.append(error)
    return errors


def _unlink_staged_file(path, preserved_paths):
    """Remove one staged file, retrying after clearing its read-only bit."""
    if path in preserved_paths:
        return None
    try:
        path.unlink()
        return None
    except FileNotFoundError:
        return None
    except OSError:
        pass
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        path.chmod(mode | stat.S_IWRITE)
        path.unlink()
    except FileNotFoundError:
        return None
    except OSError as exc:
        return f"{path}: {exc}"
    return None
