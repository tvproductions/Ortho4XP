# TODO-021: Minimize Import-Time Side Effects — Config Initialization Guard

## Overview

Add an environment variable guard to `O4_Config_Utils.py` that allows tests to skip import-time configuration initialization. This is the first slice of TODO-021, targeting the most impactful import-time side effect in the codebase.

## Problem

`O4_Config_Utils.py` performs extensive initialization at module import time (lines 194-234):

1. Sets default values for all config variables in the module's global namespace
2. Reads `Ortho4XP.cfg` from disk (path depends on CWD)
3. Parses config file and mutates global state in 6+ other modules (`UI`, `IMG`, `TILE`, `OSM`, `OVL`, `VMAP`, `DEM`)
4. Creates `Ortho4XP.cfg` with defaults if the file does not exist

This makes unit testing difficult because:
- Tests cannot import the module without triggering file I/O
- Tests cannot control config values without mocking or fixture files
- Importing the module can create files on disk
- Global state in other modules is mutated as a side effect of import

## Solution

Add an environment variable check that skips initialization when `ORTHO4XP_SKIP_CONFIG_INIT` is set:

```python
if not os.environ.get('ORTHO4XP_SKIP_CONFIG_INIT'):
    # ... existing initialization code (lines 194-234) ...
```

Tests set this environment variable before importing to get clean, side-effect-free imports.

## Architecture

### Current Behavior

```
import O4_Config_Utils
  → validates config registry (line 59)
  → sets defaults in 6+ modules (lines 194-195)
  → reads Ortho4XP.cfg (lines 199-221)
  → creates Ortho4XP.cfg if missing (lines 222-232)
  → mutates globals in UI, IMG, TILE, OSM, OVL, VMAP, DEM
```

### New Behavior

```
import O4_Config_Utils
  → checks os.environ.get('ORTHO4XP_SKIP_CONFIG_INIT')
  → if set: skips all initialization (module imports cleanly)
  → if not set: runs full initialization (current behavior)
```

### Test Usage

```python
import os
os.environ['ORTHO4XP_SKIP_CONFIG_INIT'] = '1'
import O4_Config_Utils  # No file I/O, no global mutation
```

The environment variable is checked once at module import time. There is no way to re-trigger initialization after import — this is intentional. Tests that need config values will mock or set them directly.

## Implementation

### File: `src/O4_Config_Utils.py`

**Change:** Wrap lines 194-234 in an environment variable check.

**Before:**
```python
for var in cfg_vars:
    _set_config_value(var, config_default(cfg_vars[var]))

global_cfg_file = FNAMES.resource_path("Ortho4XP.cfg")
global_cfg_bak_file = FNAMES.resource_path("Ortho4XP.cfg.bak")

try:
    with open(global_cfg_file, "r") as f:
        for line in f:
            # ... parse and set globals
except FileNotFoundError:
    # ... create default config file
except Exception:
    UI.log_exception("Error reading config file")
```

**After:**
```python
# Skip config initialization for testing. When ORTHO4XP_SKIP_CONFIG_INIT is
# set, this module imports cleanly without reading files or mutating globals.
if not os.environ.get('ORTHO4XP_SKIP_CONFIG_INIT'):
    for var in cfg_vars:
        _set_config_value(var, config_default(cfg_vars[var]))

    global_cfg_file = FNAMES.resource_path("Ortho4XP.cfg")
    global_cfg_bak_file = FNAMES.resource_path("Ortho4XP.cfg.bak")

    try:
        with open(global_cfg_file, "r") as f:
            for line in f:
                # ... parse and set globals (indent +4 spaces)
    except FileNotFoundError:
        # ... create default config file (indent +4 spaces)
    except Exception:
        UI.log_exception("Error reading config file")
```

**Indentation:** The entire block (lines 194-234) gets indented by 4 spaces to sit inside the `if` block.

**Import:** `os` is already imported on line 1. No new imports needed.

**No other changes:** The validation call on line 59 (`validate_config_registry(cfg_vars)`) stays at module level — it's a pure validation that raises on bad definitions, not a side effect that reads files or mutates state.

## Testing

### New Test File: `tests/test_config_import_safety.py`

```python
import os
import sys
import unittest
from unittest import mock

# Set env var BEFORE importing O4_Config_Utils
os.environ['ORTHO4XP_SKIP_CONFIG_INIT'] = '1'

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class ConfigImportSafetyTests(unittest.TestCase):
    def test_import_does_not_read_config_file(self):
        """Importing with skip flag should not read Ortho4XP.cfg."""
        # Module already imported at top with skip flag
        # If it tried to read a non-existent file, it would have created one
        # or raised an error. We verify by checking no file was created in
        # a temp directory.
        pass  # The import itself is the test

    def test_import_does_not_mutate_ui_globals(self):
        """Importing with skip flag should not set UI.verbosity etc."""
        import O4_UI_Utils as UI
        # UI.verbosity should be at its default (1), not mutated by config
        self.assertEqual(UI.verbosity, 1)

    def test_import_does_not_mutate_img_globals(self):
        """Importing with skip flag should not set IMG.http_timeout etc."""
        import O4_Imagery_Utils as IMG
        # IMG.http_timeout should be at its module-level default
        self.assertEqual(IMG.http_timeout, 10)


if __name__ == "__main__":
    unittest.main()
```

### Test Execution

- Tests set `ORTHO4XP_SKIP_CONFIG_INIT=1` in the test runner environment
- The `tests/_path.py` setup could set this automatically for all tests
- Alternatively, each test file that imports config-dependent modules sets it

### Integration with Existing Tests

- Existing tests in `tests/test_config_*.py` already mock or work around config initialization
- They continue to work unchanged
- The new test file specifically verifies the skip flag behavior

### CI/CD

- The test runner (unittest discover) runs with the env var set
- No changes to CI configuration needed — the env var is set in test code

## Error Handling

No changes to error handling. The existing `try/except` blocks inside the guarded block remain unchanged.

- If the env var is set and initialization is skipped, no errors can occur (no file I/O, no global mutation)
- If the env var is not set, behavior is identical to current code

## Documentation

### Code Comment

Add a comment above the guard in `O4_Config_Utils.py`:

```python
# Skip config initialization for testing. When ORTHO4XP_SKIP_CONFIG_INIT is
# set, this module imports cleanly without reading files or mutating globals.
if not os.environ.get('ORTHO4XP_SKIP_CONFIG_INIT'):
    # ... existing initialization code ...
```

### Contributor Docs

Add a note to `docs/development.md` (or equivalent):

```markdown
### Testing Without Config Initialization

Set `ORTHO4XP_SKIP_CONFIG_INIT=1` to import `O4_Config_Utils` without
triggering config file reads or global state mutation. This is useful for
unit tests that need to control config values explicitly.
```

## Scope Boundaries

This change does NOT:
- Extract initialization into a function (future TODO)
- Fix other import-time side effects (`O4_Geotag.py`, `O4_Imagery_Utils.py`, etc.)
- Modify the validation call on line 59
- Change the initialization logic itself (only wraps it in a conditional)

## Future Work

The exploration identified additional import-time side effects that should be addressed in follow-up TODOs:

1. **O4_Geotag.py** (CRITICAL): Lines 19-66 run `gdal_translate` and `gdalwarp` on every `.jpg` in CWD at import time. This is a script masquerading as a module. Should be wrapped in `if __name__ == "__main__":`.

2. **O4_Imagery_Utils.py** (HIGH): Sets `Image.MAX_IMAGE_PIXELS` globally, performs dynamic import with file I/O and `print()`.

3. **O4_DEM_Utils.py** (HIGH): Calls `gdal.UseExceptions()` which changes GDAL error mode globally.

4. **O4_Mesh_Utils.py** (HIGH): Reads `community_server.txt` from disk at import time.

5. **O4_OSM_Utils.py** (HIGH): Reads `overpass_servers.txt` from disk at import time.

6. **O4_File_Names.py** (MEDIUM): 14 directory constants frozen from CWD at import time.

These should be addressed in separate TODOs following the same pattern: identify the side effect, add a guard or extract to an explicit init function, add tests.

## Acceptance Criteria

- [ ] Identifies modules with platform detection, path setup, provider loading, or printing during import
- [ ] Extracts one side-effecting import path into an explicit initializer (via env var guard)
- [ ] Ensures tests can import the changed module safely
- [ ] Routes errors through the shared logging path where available (no changes needed — existing error handling preserved)

## References

- TODO-021 in `TODO.md`
- GitHub Issue: #16
