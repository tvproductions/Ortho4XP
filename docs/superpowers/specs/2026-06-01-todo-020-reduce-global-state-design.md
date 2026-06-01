# TODO-020 Reduce Global Mutable State

## Problem

The build pipeline reads process-state globals (`UI.red_flag`, `UI.is_working`,
`UI.verbosity`, `UI.cleaning_level`, `UI.gui`) from the `O4_UI_Utils` module
across 10+ consumer modules. These globals serve as the sole cancellation
mechanism, concurrency guard, output control, and GUI bridge for the entire
application.

While the `Tile` object (introduced in earlier work) snapshots tile
configuration at construction time, build step functions still reach into
`UI.*` module attributes directly. This creates hidden coupling: any function
that reads `UI.red_flag` depends on the `UI` module's global state without
that dependency being visible in its signature.

The broader global state landscape includes provider dictionaries, config
dispatch via `setattr()` on module objects, imagery failure tracking, and
scattered per-module scalars. This TODO addresses only the first slice:
process-state globals in the build pipeline.

## Goals

- Introduce a `BuildContext` object for the build pipeline workflow.
- Use a property facade so `BuildContext` delegates to `UI.*` globals, keeping
  the GUI stop button and existing readers consistent.
- Thread `ctx: BuildContext` as an explicit parameter through top-level build
  step functions (`build_poly_file`, `build_mesh`, `build_masks`, `build_tile`,
  `build_dsf`).
- Add deterministic `unittest` coverage using stdlib only.
- Preserve all existing behavior: GUI cancellation, concurrency guards,
  verbosity-gated output, cleaning-level-controlled temp file cleanup.

## Non-Goals

- Do not migrate sub-delegates deeper than the top-level build functions. They
  continue reading `UI.*` directly; the property facade keeps them consistent.
- Do not wrap provider dictionaries, config dispatch, imagery failure tracking,
  or per-module scalars (`scalx`, `overpass_server_choice`, etc.) in this slice.
- Do not change how `O4_GUI_Utils.py` writes `UI.red_flag` or `UI.is_working`.
- Do not remove or restructure `O4_UI_Utils.py` module-level variables.
- Do not change the `Tile` class or config snapshot mechanism.
- Do not move import-time setup. TODO-021 owns that work.
- Do not introduce the headless CLI. TODO-022 owns that work.

## Design

### BuildContext Definition

New file: `src/O4_Build_Context.py`

`BuildContext` is a class with `@property` descriptors that delegate reads and
writes to `UI` module attributes. There is one source of truth (the `UI`
module), and the context is a typed, structured accessor.

Properties:

| Property | Type | Delegates to |
|---|---|---|
| `red_flag` | `bool` | `UI.red_flag` |
| `is_working` | `bool` | `UI.is_working` |
| `verbosity` | `int` | `UI.verbosity` |
| `cleaning_level` | `int` | `UI.cleaning_level` |
| `gui` | `Any \| None` | `UI.gui` |

A convenience method `vprint(level, msg)` provides verbosity-gated output
that delegates to `UI.vprint()`.

The facade is intentionally thin. The backing store remains `UI` module
attributes. Future TODOs can replace the facade with an independent backing
without changing the `BuildContext` API surface.

### Threading Through the Build Pipeline

The current call chain:

```
Ortho4XP.py → CORE.build_tile_all(tile)
  → VMAP.build_poly_file(tile)
  → MESH.build_mesh(tile)
  → MASK.build_masks(tile)
  → TILE.build_tile(tile)
  → DSF.build_dsf(tile)
```

Changes:

1. `build_tile_all(tile)` constructs `ctx = BuildContext()`, sets
   `ctx.is_working = True`, and passes `ctx` to each delegate.
2. Each top-level delegate gains `ctx: BuildContext` as a second parameter:
   `build_poly_file(tile, ctx)`, `build_mesh(tile, ctx)`, etc.
3. Inside each delegate, direct `UI.red_flag` reads become `ctx.red_flag`,
   `UI.is_working` becomes `ctx.is_working`, etc.
4. `O4_Tile_Utils.build_all()` (the TODO-019 compatibility wrapper) also
   constructs a `BuildContext` before delegating to `CORE`.

What does NOT change:

- Sub-delegates called by the top-level functions continue reading `UI.*`
  directly. The property facade keeps them consistent with `ctx.*` reads.
- `O4_GUI_Utils.py` continues writing `UI.red_flag` and `UI.is_working`
  directly. The facade ensures build steps see the changes immediately.
- `exit_message_and_bottom_line()` in `O4_UI_Utils.py` continues to set
  `UI.is_working = False`. Since `ctx.is_working` delegates to the same
  attribute, both paths stay consistent.

### Backward Compatibility

The property facade guarantees bidirectional consistency:

- GUI stop button writes `UI.red_flag = True` → build step reads
  `ctx.red_flag` → returns `True`.
- Build step writes `ctx.is_working = False` → GUI exit guard reads
  `UI.is_working` → returns `False`.

No sync calls, no snapshot gaps, no stale-state windows.

### Testing

New file: `tests/test_build_context.py` using stdlib `unittest` only.

1. **Construction** — `BuildContext()` reads current `UI.*` values through
   properties.
2. **Write-through** — Setting `ctx.red_flag = True` causes `UI.red_flag` to
   become `True`. Setting `UI.red_flag = True` causes `ctx.red_flag` to return
   `True`.
3. **vprint gating** — `ctx.vprint(2, msg)` prints when `ctx.verbosity >= 2`,
   silent otherwise.
4. **Mock-UI** — Patch `UI` module attributes and verify `BuildContext`
   reflects patched values.
5. **Pipeline integration** — `build_tile_all` constructs a `BuildContext` and
   passes it to delegates. Verified by patching a delegate and asserting it
   received a `BuildContext` instance.

No network, GUI, GDAL, imagery provider, or native utility dependencies in any
test.

## Global State Inventory Reference

The full inventory of global mutable state identified during design is
preserved here for future TODOs:

- **UI/Process state** (`O4_UI_Utils.py`): `red_flag`, `is_working`,
  `verbosity`, `cleaning_level`, `gui`, `log` — addressed by this TODO.
- **Provider dictionaries** (`O4_Imagery_Utils.py`): `providers_dict`,
  `combined_providers_dict`, `local_combined_providers_dict`, `extents_dict`,
  `color_filters_dict` — future TODO.
- **CFG namespace** (`O4_Config_Utils.py`): `zone_list`, `default_website`,
  `default_zl`, `custom_scenery_dir`, all tile config vars — future TODO.
- **Imagery failure tracking** (`O4_Imagery_Failures.py`): `incomplete_imgs`,
  `imagery_failure_records` — future TODO.
- **Scattered scalars**: `scalx` (`O4_Vector_Utils.py`),
  `overpass_server_choice` (`O4_OSM_Utils.py`), `custom_overlay_src`
  (`O4_Overlay_Utils.py`), tile config globals (`O4_Tile_Utils.py`) — future
  TODOs.
