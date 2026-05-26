# TODO-019 Build Core Design

## Problem

TODO-019 starts the Phase 4 architecture breakaway work: separate GUI,
command-line parsing, and core build orchestration. The current code still
mixes those concerns across the launcher, GUI handlers, and tile utilities:

- `Ortho4XP.py` performs runtime setup, initializes source dictionaries, parses
  CLI arguments, creates tiles, and directly runs the full tile build sequence.
- `src/O4_GUI_Utils.py` is the presentation layer, but its button handlers
  construct tiles, create build directories, and launch build functions in
  worker threads.
- `src/O4_Tile_Utils.py` owns Step 3 texture/DSF orchestration, the current
  all-in-one sequence, batch builds, and GUI map cleanup after batch work.

This makes future headless CLI work harder because there is no narrow callable
core API for presentation layers to share. The first slice should create that
boundary without rewriting the legacy build steps.

## Goals

- Identify the current GUI, CLI, and core build responsibilities.
- Add one callable core API for the all-in-one tile build sequence.
- Preserve current GUI and CLI behavior.
- Keep legacy callers compatible while moving them toward the new core API.
- Add deterministic `unittest` coverage with mocked build steps.
- Avoid real network, X-Plane, GDAL, imagery provider, or native utility work in
  tests.

## Non-Goals

- Do not rewrite Step 1 vector assembly, Step 2 mesh generation, Step 2.5 mask
  generation, or Step 3 imagery/DSF internals.
- Do not introduce the TODO-022 headless `build_job.toml` interface yet.
- Do not remove `O4_Tile_Utils.build_all()` in this slice; keep it as a
  compatibility wrapper.
- Do not change batch build behavior beyond routing future all-in-one reuse
  through the new boundary when safe.
- Do not replace global UI state in this issue. TODO-020 owns the larger state
  migration.
- Do not move import-time setup in this issue. TODO-021 owns import-side-effect
  cleanup.

## Current Responsibility Map

`Ortho4XP.py` currently owns launcher-level concerns and too much build work:

- detects PyInstaller runtime paths;
- sets `PROJ_DATA`, `DYLD_LIBRARY_PATH`, and pyproj data directory;
- adds `src` and provider paths to `sys.path`;
- ensures runtime directories exist;
- initializes imagery extents, color filters, providers, and combined
  providers;
- parses positional CLI arguments;
- creates a `CFG.Tile`;
- directly calls Step 1, Step 2, Step 2.5, and Step 3 build functions.

`src/O4_GUI_Utils.py` currently owns presentation and some orchestration:

- renders the main Tk UI and earth preview window;
- validates coordinates from text fields;
- handles unsaved config-window prompts;
- creates `CFG.Tile` objects from UI state;
- creates tile directories before launch;
- starts worker threads for individual steps and all-in-one builds;
- starts batch builds from selected earth-window tiles.

`src/O4_Tile_Utils.py` currently owns Step 3 and broader build workflows:

- downloads imagery and schedules DDS conversion;
- builds and activates DSF files;
- cleans intermediate files according to UI config;
- implements `build_all()` by calling Step 1, Step 2, Step 2.5, and Step 3;
- retries Step 3 once when incomplete imagery is detected;
- implements batch tile builds and updates GUI earth-window state when present.

## Recommended Approach

Add a narrow core module for all-in-one tile orchestration:
`src/O4_Build_Core.py`.

The module should expose this public contract:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class BuildResult:
    ok: bool
    step: str
    message: str = ""


def build_tile_all(tile) -> BuildResult:
    """Run the current all-in-one tile sequence and return its structured result."""
```

The core function should preserve the current all-in-one sequence:

1. call `O4_Vector_Map.build_poly_file(tile)`;
2. stop if `UI.red_flag` is set;
3. call `O4_Mesh_Utils.build_mesh(tile)`;
4. stop if `UI.red_flag` is set;
5. call `O4_Mask_Utils.build_masks(tile)`;
6. stop if `UI.red_flag` is set;
7. call `O4_Tile_Utils.build_tile(tile)`;
8. if the current tile has incomplete imagery, delete incomplete images and run
   Step 3 once more, matching current `build_all()` behavior;
9. stop if `UI.red_flag` is set;
10. report remaining incomplete imagery through the existing UI logging path;
11. return `BuildResult(ok=True, step="all")` on success.

`BuildResult.step` should name the phase that failed or stopped:
`"vector"`, `"mesh"`, `"masks"`, `"tile"`, `"retry"`, or `"all"`. This keeps
the result useful for future CLI reporting while keeping the first
implementation small.

`src/O4_Tile_Utils.py::build_all()` should become a compatibility wrapper:

```python
def build_all(tile):
    result = CORE.build_tile_all(tile)
    return 1 if result.ok else 0
```

That wrapper preserves callers that still expect legacy integer truth values.
It also keeps Step 3-specific helpers such as `delete_incomplete_imgs()` in
`O4_Tile_Utils.py` for now. The core module may call that helper rather than
moving deletion logic in the first slice.

The CLI should call the same core API for the all-in-one positional build path.
The GUI "All in one" button can continue launching a background thread, but the
thread target should be the shared core-facing wrapper so GUI and CLI behavior
remain aligned.

## Error Handling

The core API should not add broad exception swallowing. Existing outer
boundaries already handle the user-facing crash cases:

- `Ortho4XP.py` catches exceptions around command-line builds and prints
  `Crash!`.
- GUI button handlers catch tile creation and setup failures before starting
  worker threads.
- individual build steps continue to use `O4_UI_Utils` for progress and error
  messages.

The new core function should stop on `UI.red_flag`, call
`UI.exit_message_and_bottom_line("")` where the current all-in-one flow does,
and return a failed `BuildResult` for interrupted work. This preserves
observable behavior while giving future CLI code a structured result.

## Testing

Add `tests/test_build_core.py` using standard-library `unittest`.

The tests should mock all heavy build steps and verify:

- successful all-in-one calls happen in Step 1, Step 2, Step 2.5, Step 3 order;
- a red flag after Step 1 stops before Step 2 and returns a failed vector
  result;
- a red flag after Step 2 stops before masks and returns a failed mesh result;
- incomplete imagery causes `delete_incomplete_imgs(tile)` and exactly one
  Step 3 retry;
- remaining incomplete imagery is reported through `UI.lvprint`;
- `O4_Tile_Utils.build_all()` returns `1` or `0` based on the core result.

The tests should use a `types.SimpleNamespace` tile with `lat`, `lon`, and
`build_dir` attributes. They should not create real tile data or call external
tools.

## Documentation And Tracking

Update `TODO.md` only after implementation and verification, marking TODO-019
done and summarizing the delivered boundary. Add an implementation/evidence
comment to GitHub issue #14 before closing it.

No README user-facing behavior change is expected from this slice because the
CLI invocation remains positional and GUI controls remain the same.

## Success Criteria

- `src/O4_Build_Core.py` provides a tested callable all-in-one build API.
- CLI and GUI all-in-one paths share the core orchestration boundary.
- `O4_Tile_Utils.build_all()` remains compatible for legacy callers.
- Tests cover success, interruption, incomplete imagery retry, and wrapper
  compatibility.
- The implementation avoids new runtime dependencies and keeps existing build
  output behavior intact.
