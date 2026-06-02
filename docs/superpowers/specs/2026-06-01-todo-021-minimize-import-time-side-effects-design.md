# TODO-021: Minimize Import-Time Side Effects - Config Initialization Boundary

## Overview

Make `O4_Config_Utils.py` safe to import by moving runtime configuration
initialization behind an explicit `initialize_global_config()` function. This
addresses the highest-impact import-time side effect in the current codebase:
reading or creating `Ortho4XP.cfg` and mutating config-backed globals in other
modules while the module is imported.

## Problem

Before this change, importing `O4_Config_Utils` performed runtime work:

1. Set default values for all config variables in the module namespace and in
   modules such as `O4_UI_Utils`, `O4_Imagery_Utils`, `O4_Tile_Utils`,
   `O4_OSM_Utils`, `O4_Overlay_Utils`, `O4_Vector_Map`, and `O4_DEM_Utils`.
2. Read `Ortho4XP.cfg` from the active resource root.
3. Created `Ortho4XP.cfg` with defaults when the file was missing.
4. Logged config file access failures through the shared UI logging path.

That made imports order-dependent and hard to test. Unit tests that only needed
helpers or model definitions could trigger file I/O and process-wide global
mutation by importing a module that depends on `O4_Config_Utils`.

## Design

`O4_Config_Utils` keeps static registry validation at import time, because
`validate_config_registry(cfg_vars)` checks checked-in metadata and does not
perform runtime I/O. Runtime initialization moves to an idempotent function:

```python
def initialize_global_config(*, force: bool = False) -> None:
    ...
```

The initializer:

- assigns config defaults using the existing `cfg_vars` registry;
- reads `global_cfg_file` when present and applies loaded values;
- creates a default `Ortho4XP.cfg` when missing;
- preserves unsupported-value diagnostics and invalid-line handling;
- keeps file access errors routed through `UI.log_exception`;
- records initialization state through `is_global_config_initialized()`;
- supports `force=True` for tests that need to re-run initialization against a
  patched config path.

Importing `O4_Config_Utils` no longer calls the initializer. `CFG.Tile`
construction calls it lazily because tile construction is a config-dependent
runtime boundary.

## Runtime Wiring

The runtime boundaries are responsible for initialization:

- `CFG.Tile.__init__()` calls `initialize_global_config()` lazily so legacy
  direct tile construction remains valid after import-time initialization is
  removed.
- `O4_Config_Utils.initialize_global_config()` delegates the file I/O and
  default assignment work to `O4_Config_Runtime.GlobalConfigRuntime`, keeping
  the large legacy config module from absorbing the loader implementation.

Headless validation remains import-light: `validate-job` and `build-job
--dry-run` validate job files and provider dictionaries without importing
`O4_Config_Utils`, constructing tiles, creating runtime directories, or writing
`Ortho4XP.cfg`.

## Testing

`tests/test_config_import_safety.py` proves the boundary:

- plain import of `O4_Config_Utils` does not call `open`;
- plain import does not reset `UI.verbosity` or `IMG.http_timeout`;
- explicit initialization applies defaults and creates a missing config file.

Config loading and runtime tests prove the runtime wiring:

- direct `CFG.Tile` construction initializes missing defaults before reading
  tile config;
- launcher and batch build tests continue to exercise tile construction through
  the shared core paths.

## Error Handling

The initializer preserves existing config-file error handling. Missing config
files are created with defaults and logged with `UI.log_event`. Other `OSError`
failures are reported through `UI.log_exception`. Unsupported `water_tech`
values and invalid lines keep the existing human-readable diagnostics.

## Remaining Import-Time Side Effects

The TODO-021 exploration identified additional import-time side effects that are
outside this first config-boundary change and should be tracked as future work:

1. `O4_Geotag.py` runs GDAL commands over `.jpg` files in the current working
   directory at import time.
2. `O4_Imagery_Utils.py` changes `Image.MAX_IMAGE_PIXELS` globally and still has
   provider/parser diagnostic `print()` calls in explicit initializer paths.
3. `O4_DEM_Utils.py` calls `gdal.UseExceptions()`, changing GDAL process state.
4. `O4_Mesh_Utils.py` reads `community_server.txt` at import time.
5. `O4_OSM_Utils.py` reads `overpass_servers.txt` at import time.
6. `O4_File_Names.py` freezes resource directory constants from the current
   working directory at import time.

Those are now explicit follow-up candidates rather than blockers for
`O4_Config_Utils` import safety.

## Acceptance Criteria

- [x] Identifies modules with platform detection, path setup, provider loading,
  or printing during import.
- [x] Extracts one side-effecting import path into an explicit initializer.
- [x] Ensures tests can import the changed module safely.
- [x] Routes errors through the shared logging path where available.

## References

- `TODO.md` TODO-021
- GitHub Issue: #16
- `tests/test_config_import_safety.py`
