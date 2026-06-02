# TODO-022 Headless CLI Transition Design

## Problem

TODO-022 begins the headless automation breakaway: expose a CLI engine that can
validate and run multi-tile build jobs from a structured `build_job.toml` file
without requiring a display server or GUI imports.

The current launcher and batch build surfaces are not clean enough for that:

- `Ortho4XP.py` handles PyInstaller setup, path setup, runtime directory
  creation, provider initialization, GUI launch, positional CLI parsing, and
  build dispatch in one file.
- `Ortho4XP.py` imports `O4_GUI_Utils` and `O4_Config_Utils` at module load.
  That means a new headless subcommand delegated too late would still import
  Tk GUI code and trigger config initialization.
- `O4_Config_Utils` imports safely, but runtime builds must call
  `initialize_global_config()` before constructing `CFG.Tile` because tile
  objects expect initialized config globals.
- `O4_Build_Core.build_tile_all(tile)` is the shared all-in-one core boundary
  for one tile, but it does not model multi-tile batches, selected steps,
  overlay extraction, config override behavior, or aggregate results.
- GUI batch builds still call `O4_Tile_Utils.build_tile_list(...)`, which
  handles multi-tile work and overlays but returns legacy `1` or `0` values and
  contains GUI cleanup behavior.

The new CLI must therefore add a real job parser and validator, add structured
batch results to the core layer, and arrange launcher dispatch so headless
commands remain headless.

## Goals

- Add a headless CLI entry point driven by a structured `build_job.toml` file.
- Support both explicit tile lists and inclusive rectangular tile bounds.
- Support one job-level provider key, zoom level, output directory, step list,
  and config override flag.
- Validate a multi-tile build plan without importing GUI modules, constructing
  `CFG.Tile`, creating generated runtime directories, or creating config files.
- Execute validated jobs through a core batch API with structured per-tile and
  aggregate results.
- Keep GUI as presentation over the same core build API by making GUI batch
  migration part of this TODO's implementation.
- Preserve legacy positional CLI behavior and GUI launch behavior for users who
  do not invoke the new headless subcommands.
- Add deterministic `unittest` coverage and CI smoke coverage for validation.

## Non-Goals

- Do not add package metadata or console scripts. `pyproject.toml` currently
  has `tool.uv.package = false`, so the source-checkout entry point remains
  `python Ortho4XP.py ...`.
- Do not initialize global config during validation-only headless commands.
- Do not add per-tile provider, zoom, or output overrides in the first slice.
- Do not add zone polygon syntax to `build_job.toml`; existing tile config
  `zone_list` support remains file-driven.
- Do not remove the legacy positional CLI in this TODO.
- Do not remove `O4_Tile_Utils.build_tile_list(...)` unless all current callers
  have been safely migrated. A compatibility wrapper is acceptable.
- Do not perform real network, X-Plane, GDAL, imagery-provider, or native
  utility work in tests.

## Current Responsibility Map

`Ortho4XP.py` currently:

- handles `--help` before runtime setup;
- sets PyInstaller resource and PROJ environment variables;
- adds `src` and provider paths to `sys.path`;
- imports GUI, config, imagery, CLI, and build modules;
- creates generated runtime directories;
- initializes extents, filters, providers, and combined providers;
- launches GUI when no arguments are supplied;
- parses legacy positional CLI arguments;
- constructs `CFG.Tile`;
- calls `O4_Build_Core.build_tile_all(tile)`.

`O4_Build_Core.py` currently:

- exposes `BuildResult(ok, step, message)` for one tile;
- runs vector, mesh, masks, and tile/DSF imagery steps in all-in-one order;
- retries incomplete imagery once;
- reports remaining incomplete imagery through `O4_UI_Utils.lvprint`;
- does not include overlays or multi-tile aggregate results.

`O4_Tile_Utils.py::build_tile_list(...)` currently:

- accepts a seed tile, selected tile coordinates, step booleans, overlay flag,
  and config override flag;
- mutates the seed tile for each coordinate;
- reads tile or global config per tile;
- runs selected steps and overlay extraction;
- retries incomplete imagery once;
- updates GUI earth-window selected-tile state when a GUI is present;
- returns `1` or `0`.

## Recommended Architecture

Add a pure job parser and validation module, neutral build models, a headless
command module, and a batch-oriented core API.

### Job Parser And Validator

New module: `src/O4_CLI_Jobs.py`

Responsibilities:

- parse TOML bytes or text using stdlib `tomllib`;
- validate schema and value types;
- normalize explicit tiles plus bounds into a sorted, deduplicated tile list;
- validate provider keys against initialized provider dictionaries when the
  caller supplies available provider keys;
- validate zoom level, output directory, steps, and config override flag;
- produce neutral build model objects from `O4_Build_Models`;
- serialize validation output for human and JSON CLI modes.

The CLI parser must not define build execution models that the core imports.
That would make the core layer depend on the CLI layer. `O4_CLI_Jobs` may define
validation-specific error/result helpers, but build plan and result dataclasses
belong in the neutral build model module described below.

Validation-specific dataclasses:

```python
@dataclass(frozen=True)
class TileCoordinate:
    lat: int
    lon: int


@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str
    value: object | None = None
```

### Build Models

New module: `src/O4_Build_Models.py`

Responsibilities:

- define the build plan contract consumed by core execution;
- define per-tile and aggregate build result contracts;
- remain independent of CLI parsing, GUI widgets, and legacy tile utilities.

Public dataclasses:

```python
@dataclass(frozen=True)
class BuildTilePlan:
    lat: int
    lon: int
    provider: str
    zoom_level: int
    output_dir: str
    custom_build_dir: str
    steps: tuple[str, ...]
    override_tile_config: bool


@dataclass(frozen=True)
class BuildPlan:
    tiles: tuple[BuildTilePlan, ...]


@dataclass(frozen=True)
class BuildTileResult:
    lat: int
    lon: int
    ok: bool
    step: str
    message: str = ""


@dataclass(frozen=True)
class BuildBatchResult:
    ok: bool
    tiles: tuple[BuildTileResult, ...]
    message: str = ""
```

`custom_build_dir` is derived from `output_dir` by guaranteeing trailing path
separator semantics before passing the value to existing path helpers. This
makes `output_dir` a base directory, not a grouped one-tile package path.

### Job File Contract

Minimum valid file:

```toml
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 43
lon = -79
```

Supported optional fields:

```toml
steps = ["vector", "mesh", "masks", "tile"]
override_tile_config = false

[bounds]
lat_min = 42
lat_max = 43
lon_min = -80
lon_max = -79
```

Rules:

- `provider` is required and must be a provider or combined-provider key.
- `zoom_level` is required, must be an integer greater than zero, and must not
  exceed a selected normal provider's static `max_zl` when that metadata is
  present. Combined-provider local layer limits remain enforced by existing
  build-time provider logic.
- `output_dir` is required and must be a non-empty string.
- `steps` is optional and defaults to `["vector", "mesh", "masks", "tile"]`.
- Allowed steps are `vector`, `mesh`, `masks`, `tile`, and `overlays`.
- `override_tile_config` is optional and defaults to `false`.
- At least one `[[tiles]]` entry or `[bounds]` block is required.
- `[[tiles]]` entries must contain integer `lat` and `lon`.
- Latitude must be in `[-90, 89]`; longitude must be in `[-180, 179]`.
- `[bounds]` is inclusive and must contain integer `lat_min`, `lat_max`,
  `lon_min`, and `lon_max`.
- Bounds must satisfy `lat_min <= lat_max` and `lon_min <= lon_max`.
- Explicit tiles and bounds may both appear. The validator combines them,
  deduplicates them, and sorts them by `(lat, lon)`.
- Per-tile provider, zoom, output, and step overrides are rejected in this
  slice to keep the first contract small and testable.

### Output Directory Semantics

`output_dir` always means a base directory for generated tile packages.
Relative `output_dir` values are resolved relative to the `build_job.toml`
file's parent directory, not the process current working directory. Absolute
paths are preserved.

For a job with:

```toml
output_dir = "D:/Ortho4XP/Tiles"

[[tiles]]
lat = 43
lon = -79
```

the tile build directory is:

```text
D:/Ortho4XP/Tiles/zOrtho4XP_+43-079
```

The implementation must not expose legacy grouped `custom_build_dir` semantics
through `build_job.toml`. Internally, the plan may pass a trailing-separator
`custom_build_dir` into existing `FNAMES.build_dir(...)` behavior so this rule
stays compatible with current path helpers.

### Resource Root Semantics

Headless validation must be independent of the process current working
directory.

Early CLI dispatch resolves the repository/application root from
`Path(__file__).resolve().parent` in source checkouts. In PyInstaller mode it
uses the existing frozen resource root. The headless path then:

- appends `<root>/src` for source imports;
- reads `Providers`, `Extents`, `Filters`, `Patches`, and other source assets
  from the resolved root;
- validates provider keys from root-relative provider resources;
- resolves relative `output_dir` values against the job file directory;
- avoids using CWD-derived `O4_File_Names` resource constants during validation
  unless they have first been initialized to the resolved root.

Tests must run validation from a temporary non-repo working directory to prove
that provider/resource lookup is root-relative and that no generated artifacts
are created in CWD.

### Provider Semantics

`provider` may name either:

- a normal provider key from `O4_Imagery_Utils.providers_dict`; or
- a combined provider key from `O4_Imagery_Utils.combined_providers_dict`.

Validation for `validate-job` initializes imagery provider dictionaries from the
resolved resource root, but does not import GUI modules, import
`O4_Config_Utils`, or construct tiles. Build execution also calls
`initialize_local_combined_providers_dict(tile)` through the existing tile build
path when needed. Zone-list-driven provider behavior remains controlled by tile
config files and is not expressed in `build_job.toml`.

### CLI Entry Point

Keep the source-checkout entry point in `Ortho4XP.py`:

```bash
python Ortho4XP.py validate-job build_job.toml
python Ortho4XP.py validate-job build_job.toml --json
python Ortho4XP.py build-job build_job.toml
python Ortho4XP.py build-job build_job.toml --dry-run
```

`Ortho4XP.py` must dispatch `validate-job` and `build-job` before importing
`O4_GUI_Utils` or `O4_Config_Utils`. The early path may perform PyInstaller
resource path setup and append `src` to `sys.path`, but it must not:

- import Tk GUI modules;
- import `O4_Config_Utils` during validation;
- call `ensure_runtime_dirs()` during validation or dry-run;
- construct `CFG.Tile` during validation or dry-run.

Legacy behavior remains:

```bash
python Ortho4XP.py --help
python Ortho4XP.py
python Ortho4XP.py 43 -79
python Ortho4XP.py 43 -79 BI 16
```

`--help` should include the new subcommands after implementation.

### Headless Command Module

New module: `src/O4_CLI_Run.py`

Responsibilities:

- parse headless subcommand arguments;
- load `build_job.toml`;
- initialize only the provider dictionaries required for validation, using the
  resolved resource root rather than CWD;
- call `O4_CLI_Jobs` to create a `BuildPlan`;
- print human validation summaries or JSON validation output;
- for `build-job`, import runtime build modules after validation succeeds;
- initialize runtime directories only for actual builds;
- call `O4_Build_Core.build_batch(plan)`;
- convert structured results to process exit codes.

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | validation succeeded, dry-run succeeded, or build succeeded |
| `1` | build failed or was interrupted |
| `2` | usage error, TOML parse error, schema error, or validation error |

### Core Batch API

Extend `src/O4_Build_Core.py` with a public batch entry point that consumes
models from `src/O4_Build_Models.py`.

```python
TileCompleteCallback = Callable[[BuildTileResult], None]
```

Public API:

```python
def build_batch(
    plan: BuildPlan,
    *,
    on_tile_complete: TileCompleteCallback | None = None,
) -> BuildBatchResult:
    """Run a validated multi-tile build plan and return aggregate results."""
```

Behavior:

1. Create one `BuildContext` for the batch.
2. Stop immediately with a failed aggregate result if `ctx.is_working` is true.
3. For each `BuildTilePlan`, construct a fresh `CFG.Tile`.
4. Apply `default_website`, `default_zl`, and base-output-directory-derived
   `custom_build_dir` from the plan.
5. Read tile config or global config according to `override_tile_config`.
6. Create tile directories only when a build step requires them.
7. Run selected steps in this order: `vector`, `mesh`, `masks`, `tile`,
   `overlays`.
8. Preserve the current incomplete-imagery retry behavior after the `tile`
   step.
9. Map a red-flag interruption to
   `BuildTileResult(ok=False, step=<current step>, message="interrupted")`.
10. Map any selected build step that returns a falsey value to
    `BuildTileResult(ok=False, step=<current step>, message="<step> failed")`.
11. Stop the batch on interruption or failed tile result and return structured
    failure details.
12. Call `on_tile_complete(result)` after each successful tile and after the
    failed tile that stops the batch, when a callback is supplied.
13. Report remaining incomplete imagery through the existing `UI.lvprint`
    path.

The API should use existing build step functions and not duplicate their
internals. Overlay extraction should call `O4_Overlay_Utils.build_overlay`
through the core batch path, not only from `O4_Tile_Utils.build_tile_list`.

### GUI Batch Migration

`O4_GUI_Utils` should remain the presentation layer:

- collect selected earth-window tile coordinates;
- collect step checkbox state;
- collect override-config checkbox state;
- collect custom build directory state;
- start a worker thread.

The worker target should be the new core batch API or a small compatibility
adapter that converts GUI state into a `BuildPlan` and calls the core batch API.
GUI-specific cleanup of selected red tiles should happen in an
`on_tile_complete` callback supplied by GUI code. The core batch loop must not
read `ctx.gui` or mutate GUI widgets directly.

`O4_Tile_Utils.build_tile_list(...)` may remain as a compatibility wrapper
during the transition, but the new headless CLI must not call it.

## Error Handling And Output

Validation errors should be deterministic and should not depend on incidental
Python exception text. Each validation error should include:

- field path, such as `bounds.lat_min` or `tiles[0].lat`;
- short message;
- offending value when useful and safe to print.

Human validation output should summarize:

- number of normalized tiles;
- provider;
- zoom level;
- output directory;
- selected steps;
- first few tile coordinates, with a count of remaining tiles when long.

`validate-job --json` should print stable JSON with at least:

```json
{
  "ok": true,
  "tile_count": 1,
  "provider": "BI",
  "zoom_level": 16,
  "output_dir": "Tiles",
  "steps": ["vector", "mesh", "masks", "tile"],
  "tiles": [{"lat": 43, "lon": -79}]
}
```

Validation failure JSON should print a stable error payload and return `2`:

```json
{
  "ok": false,
  "errors": [
    {
      "field": "bounds.lat_min",
      "message": "must be less than or equal to bounds.lat_max",
      "value": 44
    }
  ]
}
```

Build output should keep existing human progress messages from the build steps.
Final CLI result formatting should be deterministic:

- success: print a concise success summary and return `0`;
- validation failure: print validation errors and return `2`;
- build failure: print failed tile coordinate, failed step, message, and return
  `1`.
- build exception: route through `O4_UI_Utils.log_exception`, print a concise
  CLI failure summary, and return `1`.

Structured build events continue to use the existing `O4_UI_Utils.lvprint` and
JSON log path where build steps already do so.

## Dry-Run Guarantees

`validate-job` and `build-job --dry-run` must not create generated runtime
directories or config files. In a fresh temporary working directory, these
commands must not create:

- `Ortho4XP.cfg`;
- `Tiles/`;
- `OSM_data/`;
- `Masks/`;
- `Orthophotos/`;
- `Elevation_data/`;
- `Geotiffs/`;
- `tmp/`;
- `yOrtho4XP_Overlays/`.

This guarantee requires tests that run validation in a temporary current
working directory and assert the directory remains free of generated artifacts.

## Testing

Use standard-library `unittest` only.

Add focused tests for `O4_CLI_Jobs`:

- valid explicit tile job parses and normalizes;
- valid bounds job expands inclusive ranges;
- explicit tiles plus bounds deduplicate and sort;
- validation from a non-repo CWD still loads root-relative provider resources;
- missing provider, zoom level, output directory, and tile selection fail with
  stable validation errors;
- bounds with reversed min/max fail;
- latitude and longitude outside valid integer tile ranges fail;
- non-positive zoom levels fail;
- normal provider static `max_zl` is enforced when metadata is present;
- invalid step names fail;
- provider validation accepts normal providers and combined providers;
- per-tile overrides are rejected.

Add tests for headless launcher dispatch:

- `python Ortho4XP.py validate-job <file>` does not import `O4_GUI_Utils`;
- validation does not import `O4_Config_Utils`;
- validation in a temp cwd creates no generated directories or config file;
- validation in a temp cwd reads provider resources from the repo/application
  root, not from CWD;
- `validate-job --json` prints stable JSON and exits `0`;
- invalid `validate-job --json` prints stable failure JSON and exits `2`;
- invalid TOML or schema exits `2`;
- legacy `--help` still exits `0` and includes legacy usage.

Add tests for core batch execution with mocked build steps:

- selected steps run in order for each tile;
- `overlays` calls `O4_Overlay_Utils.build_overlay`;
- `override_tile_config = true` reads global config for each tile;
- `override_tile_config = false` reads tile config fallback behavior for each
  tile;
- incomplete imagery retry is preserved for the `tile` step;
- falsey selected step return maps to a failed `BuildTileResult`;
- interruption returns `BuildBatchResult(ok=False, ...)`;
- `on_tile_complete` is called with each completed tile result and does not
  require a GUI object in core code;
- aggregate success includes one `BuildTileResult` per tile.

Add GUI adapter tests where practical without creating Tk windows:

- selected GUI state is converted to `BuildPlan`;
- GUI batch path calls the core batch API rather than legacy build internals;
- GUI cleanup is supplied through `on_tile_complete`, not by reading `ctx.gui`
  in core.

No test should require network access, X-Plane installs, GDAL command-line
tools, real imagery providers, or native utility execution.

## CI And Documentation

Update CI on Linux, Windows, and macOS to add a smoke validation command after
the current CLI startup smoke test:

```bash
uv run python Ortho4XP.py validate-job tests/fixtures/build_job_minimal.toml
```

Add a small fixture file:

```toml
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
```

Update user-facing documentation with:

- new `validate-job` and `build-job` commands;
- `build_job.toml` example;
- exit codes;
- dry-run behavior;
- output directory semantics;
- note that normal and combined provider keys are accepted.

Update `TODO.md` and GitHub issue #17 only after implementation and
verification pass. The issue evidence comment should include focused tests,
full unittest discovery, Ruff, ty on changed Python files, CI-relevant smoke
coverage, and repository quality-check status.

## Success Criteria

- `python Ortho4XP.py validate-job build_job.toml` validates a normalized
  multi-tile plan without GUI/config side effects and without CWD-dependent
  resource lookup.
- `python Ortho4XP.py build-job build_job.toml --dry-run` validates and prints
  the plan without creating generated directories or config files.
- `python Ortho4XP.py build-job build_job.toml` executes through
  `O4_Build_Core.build_batch(plan)`.
- Job files support explicit `[[tiles]]`, inclusive `[bounds]`, provider,
  zoom level, output directory, selected steps, and config override flag.
- Provider validation accepts normal and combined provider keys.
- GUI batch work is routed through the same core batch API or a narrow adapter
  over that API, with GUI cleanup handled by callback.
- Legacy positional CLI and GUI launch behavior remain compatible.
- Exit codes are tested and deterministic.
- CI validates the minimal job fixture on all supported runner families.
