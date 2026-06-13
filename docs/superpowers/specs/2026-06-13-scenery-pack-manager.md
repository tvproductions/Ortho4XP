# Scenery Pack Manager — Symlink + scenery_packs.ini Management

Date: 2026-06-13
Issue: Follow-up 7.6 from TODO-027 / GHI #31
Previous: docs/superpowers/specs/2026-06-13-xp12-native-scenery-compiler-audit.md

## 1. Purpose & Scope

Add CLI-based management of Ortho4XP-generated scenery packages in X-Plane's
`scenery_packs.ini`, coupled with the existing symlink visibility mechanism.
This is the missing piece after Phase 2 (naming, metadata, validation, upgrade):
packages now have clean names and metadata, but there is no way to control
their placement in the X-Plane scenery loading order.

Scope covers: scenery_packs.ini parsing, Ortho4XP package detection, symlink
management from CLI, entry reordering, and validation. The existing GUI symlink
toggle (Ctrl+click on tile map) is left unchanged — the CLI manager operates
independently.

## 2. Module Structure

### 2.1 `src/O4_Scenery_INI.py` — Low-level ini parser

Reads and writes `scenery_packs.ini` with a line-based parser that preserves
comments, blank lines, and unknown entries. No structural understanding of
non-Ortho4XP entries.

Key interface:

```python
class SceneryINI:
    def __init__(self, path: str | None = None)
    def read(self) -> None                                # Parse file
    def write(self) -> None                                # Write changes back
    def entries(self) -> list[SceneryEntry]                # All entries
    def find_by_dirname(self, name: str) -> SceneryEntry | None
    def add_entry(self, path: str, after: str | None = None) -> None
    def remove_entry(self, path: str) -> bool
    def move_entry(self, path: str, after: str | None = None) -> None
    def disable_entry(self, path: str) -> bool
    def enable_entry(self, path: str) -> bool

@dataclass
class SceneryEntry:
    path: str                        # Relative path (e.g. "Custom Scenery/Ortho4XP_Mesh_+43-079")
    disabled: bool                   # SCENERY_PACK vs SCENERY_PACK_DISABLED
    raw_line: str                    # Original line text for round-trip preservation
```

Ini format parsed:

```
I
1000 Version

SCENERY_PACK Custom Scenery/Global Airports/
SCENERY_PACK Custom Scenery/simHeaven_X-World_Europe-1-vfr/
SCENERY_PACK_DISABLED Custom Scenery/Some Old Package/
SCENERY_PACK Custom Scenery/Ortho4XP_Mesh_+43-079/
```

### 2.2 `src/O4_Scenery_Manager.py` — High-level operations

Calls `SceneryINI` for ini operations and `os.symlink`/`os.remove` for symlink
management. Uses `FNAMES.tile_dir()`, `FNAMES.overlay_dir_name()`, and
`FNAMES.build_dir()` from `O4_File_Names.py` for path computation.

Key interface:

```python
class SceneryManager:
    def __init__(self, xplane_root: str | None = None)
    def add_tile(self, lat: int, lon: int) -> None
    def add_overlay(self) -> None
    def remove_tile(self, lat: int, lon: int) -> bool
    def remove_overlay(self) -> bool
    def list_entries(self) -> list[SceneryEntry]
    def list_ortho4xp(self) -> list[SceneryEntry]
    def reorder(self) -> None
    def validate(self) -> list[ValidationIssue]

@dataclass
class ValidationIssue:
    severity: str                    # "error" | "warning"
    message: str
    entry: SceneryEntry | None
```

### 2.3 CLI commands in `src/O4_CLI_Run.py`

| Command | Args | Description |
|---------|------|-------------|
| `scenery add` | `<lat> <lon>` or `overlay` | Symlink + ini entry at correct position |
| `scenery remove` | `<lat> <lon>` or `overlay` | Remove symlink + ini entry |
| `scenery list` | — | List all Ortho4XP entries in ini |
| `scenery reorder` | — | Reorder all Ortho4XP entries to correct positions |
| `scenery validate` | — | Check ordering, directory existence, disabled entries |

## 3. Ortho4XP Package Detection

An entry in `scenery_packs.ini` is identified as an Ortho4XP-managed package if
the directory it points to contains `package.json` with field
`generation.tool == "Ortho4XP"`, **or** if the directory name matches any of
these patterns in order of precedence:

1. `{prefix}_{purpose_token}_{latlon}` — current naming (config-aware)
2. `{prefix}_{monolithic_overlay_name}` — current overlay naming
3. `{prefix}_{purpose_token}_+*` — any lat/lon mesh
4. `zOrtho4XP_+*` — legacy mesh naming
5. `yOrtho4XP*` — legacy overlay naming

Where `{prefix}`, `{purpose_token}`, `{monolithic_overlay_name}` come from the
current config (with fallback to defaults).

This ensures the manager detects both newly-generated packages and legacy
packages that haven't been upgraded yet.

## 4. Ordering Rules

The `reorder` command arranges Ortho4XP entries as follows:

```
[Higher priority — non-Ortho4XP entries preserved in original order]
...
[Ortho4XP_Overlay_* or Ortho4XP_Overlays entries — sorted alphabetically]
[Ortho4XP_Mesh_* entries — sorted alphabetically by latlon]
[Lower priority — entries below Ortho4XP preserved in original order]
```

Mesh entries are moved below overlay entries. Within each group, entries sort
alphabetically by directory name (which sorts by lat/lon naturally).

Algorithm for `reorder`:

1. Scan entries to identify which are Ortho4XP-managed.
2. Record the position of the first Ortho4XP entry in the original list.
3. Remove all Ortho4XP entries from the list.
4. Insert the Ortho4XP block at the position recorded in step 2 (or at the
   end of the file if no Ortho4XP entries were found).
5. Within the block, overlays come first (sorted alphabetically), then mesh
   entries (sorted alphabetically by directory name).

For `add`, the same logic applies: the new entry is inserted at the position
that `reorder` would assign it, without disturbing other Ortho4XP entries.

## 5. `add` Behavior

When adding a tile:

1. **Symlink**: Created in `custom_scenery_dir` pointing to the tile build
   directory (same logic as current `O4_GUI_Utils.add_symlink`).
2. **INI entry**: `SCENERY_PACK Custom Scenery/<tile_dir_name>` inserted
   at the correct position per section 4 ordering rules.

When adding the overlay:

1. **Symlink**: Created in `custom_scenery_dir` pointing to `Overlay_dir`.
2. **INI entry**: Inserted in the overlay group position.

If the custom_scenery_dir is the same as the build directory (tiles are built
directly in Custom Scenery), no symlink is created — only the ini entry is added.

If the ini entry already exists (same path), it's enabled if disabled, or
reported as already present.

## 6. `remove` Behavior

1. Removes the symlink from `custom_scenery_dir` (if it exists and matches)
2. Removes or disables the ini entry (removes by default; `--disable` flag keeps
   entry as `SCENERY_PACK_DISABLED`)

## 7. `validate` Checks

| Check | Severity | Condition |
|-------|----------|-----------|
| Missing directory | error | Entry points to non-existent directory |
| Wrong order | warning | Overlay entry below a mesh entry |
| Disabled entry | warning | Ortho4XP entry is `SCENERY_PACK_DISABLED` |
| Missing symlink | warning | Tile/overlay dir exists but no symlink in custom_scenery_dir |
| Orphaned symlink | warning | Symlink exists but no ini entry |
| Duplicate entries | error | Same dir name appears more than once |
| Custom_scenery_dir not set | error | `CFG.custom_scenery_dir` is empty |

## 8. Edge Cases

- **custom_build_dir == custom_scenery_dir**: No symlink; ini entry points to
  the tile dir directly.
- **Grouped tiles** (custom_build_dir with basename): `add` creates a single
  symlink for the group directory; `remove` removes it.
- **No custom_scenery_dir set**: All operations error out with a clear message
  telling the user to set it in config.
- **scenery_packs.ini doesn't exist**: Created with standard header + Ortho4XP
  entries.
- **Permissions error**: Caught with actionable error message per platform.
- **Windows junctions vs symlinks**: Uses existing platform detection from
  `O4_GUI_Utils.py` logic (junction on Windows, symlink on Mac/Linux).

## 9. Integration with Existing Code

- `O4_File_Names.py`: No changes needed — already provides `tile_dir()`,
  `overlay_dir_name()`, `build_dir()`.
- `O4_CLI_Run.py`: Add `scenery` subcommand group.
- `Ortho4XP.py`: Add `scenery` to headless command dispatch.
- `O4_GUI_Utils.py`: No changes — GUI symlink toggles continue to work
  independently.
- `O4_Package_Validator.py`: No changes — standalone package validation
  is separate from scenery stack validation.
- `O4_Package_Upgrader.py`: Consider adding `scenery reorder` call after
  upgrade to register renamed packages in the ini.

## 10. Testing Strategy

- **`tests/test_scenery_ini.py`**: Unit tests for `SceneryINI` parser with
  fixture files covering: empty ini, standard ini, entries with disabled,
  entries with comments/blanks, malformed headers, round-trip preservation.
- **`tests/test_scenery_manager.py`**: Unit tests with mock filesystem for
  `SceneryManager` operations: add/remove/reorder/validate, each with and
  without symlinks, with and without `custom_scenery_dir`.
- **No X-Plane dependency**: All tests use temp directories and fixture ini
  files. No real X-Plane install needed.

## 11. Non-Goals

1. **No GUI changes** — The existing GUI symlink toggle is preserved as-is.
2. **No non-Ortho4XP package reordering** — Only Ortho4XP entries are managed.
   Third-party packages are left in place.
3. **No auto-detection of X-Plane root** — The user sets `custom_scenery_dir`
   in config; the manager derives the ini path from it
   (`<custom_scenery_dir>/../scenery_packs.ini`).
4. **No automatic reorder on build** — The user explicitly calls `reorder` or
   `add` which places the entry at the correct position. Build itself doesn't
   touch the ini.

## 12. References

- Phase 1 Audit: docs/superpowers/specs/2026-06-13-xp12-native-scenery-compiler-audit.md
- Phase 2 Naming: docs/superpowers/specs/2026-06-13-xp12-native-scenery-compiler-phase2-naming.md
- Existing symlink code: src/O4_GUI_Utils.py (add_symlink, remove_symlink, add_overlay_symlink)
- X-Plane scenery_packs.ini docs: developer.x-plane.com/article/scenery-packs/
