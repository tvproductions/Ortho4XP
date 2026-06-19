# TODO

Each TODO below is intended to become one GitHub Issue (GHI). Numbers are execution-priority order and may be renumbered when dependencies change. Keep issue bodies scoped, actionable, independently mergeable, and aligned with the current repo policy: Python 3.13.x, `uv`, `ruff`, `ty`, `unittest`, and LLVM/Clang.

GitHub issue numbers are references only; they are not expected to match TODO
numbers. Some completed TODOs were captured retroactively after the work was
already done, so their GHI numbers are out of sequence.

## Phase 0: Baseline Foundation

### TODO-001: Add Linux CI Baseline

Status: Done

GitHub Issue: #1

Create a GitHub Actions workflow for pushes and pull requests.

Acceptance criteria:

- Installs dependencies with `uv sync --dev`.
- Runs Python syntax/import smoke checks.
- Runs CLI startup validation.
- Runs the `unittest` suite.
- Runs Ruff and the current ty baseline.
- Checks changed C/C++ code with clang-format/clang-tidy.
- Builds `Triangle4XP` with LLVM/Clang.

Suggested labels: `ci`, `quality`, `quick-win`

### TODO-002: Add Modern Python Tooling

Status: Done

GitHub Issue: #20

Add modern project tooling configuration.

Acceptance criteria:

- Adds `pyproject.toml`.
- Requires Python 3.13.x.
- Uses committed `uv.lock`.
- Configures Ruff check and format.
- Configures ty baseline.
- Configures clang-format and clang-tidy for native utility code.
- Defines development dependencies.

Suggested labels: `tooling`, `dependencies`, `quick-win`

### TODO-003: Add Initial Unittest Suite

Status: Done

GitHub Issue: #2

Add deterministic `unittest` coverage for low-risk helpers.

Acceptance criteria:

- Adds a working `python -m unittest discover -s tests` command.
- Tests selected coordinate conversion helpers in `src/O4_Geo_Utils.py`.
- Tests selected file/path helpers in `src/O4_File_Names.py`.
- Documents how to run tests locally.

Suggested labels: `tests`, `quality`, `quick-win`

## Phase 1: Modern CI, Setup, and Safety Rails

### TODO-004: Add Windows and macOS CI Jobs

Status: Done

GitHub Issue: #21

Extend CI beyond Linux for the target platforms.

Acceptance criteria:

- Adds Windows 11 CI.
- Adds current Apple Silicon macOS CI where runner support allows.
- Uses `uv sync --dev`.
- Runs `unittest`, Ruff, and ty baseline.
- Builds or validates `Triangle4XP` with LLVM/Clang presets.
- Documents any platform skips or runner limitations.

Suggested labels: `ci`, `windows`, `macos`

### TODO-005: Document Development and Dependency Setup

Status: Done

GitHub Issue: #22

Create contributor-facing setup documentation that matches the modern toolchain.

Acceptance criteria:

- Documents Python 3.13.x, `uv sync --dev`, Ruff, ty, and `unittest`.
- Documents LLVM/Clang native build prerequisites.
- Documents Windows 11, Apple Silicon macOS, and Ubuntu expectations.
- Documents local-only generated data directories.
- Explains local wheel handling for GDAL and scikit-fmm.

Suggested labels: `documentation`, `onboarding`, `development`

### TODO-006: Add Application Startup Smoke Tests

Status: Done

GitHub Issue: #23

Add lightweight startup checks that avoid GUI and external service dependencies.

Acceptance criteria:

- Verifies `Ortho4XP.py --help` behavior.
- Verifies core modules import without CI-breaking side effects.
- Verifies provider dictionaries can initialize in test context.
- Verifies required resource directories are detected cleanly.
- Avoids creating committed config/cache artifacts during tests.

Suggested labels: `tests`, `startup`, `quality`

### TODO-007: Replace Unsafe Provider Parsing Eval Usage

Status: Done

GitHub Issue: #24

Replace provider parsing `eval` calls with safe parsing and explicit validation.

Acceptance criteria:

- Replaces provider parsing `eval` calls with `ast.literal_eval` or safer structured parsing.
- Validates parsed header values and booleans.
- Adds `unittest` coverage for valid and invalid provider metadata.
- Invalid provider values produce actionable error messages.

Suggested labels: `security`, `providers`, `quick-win`

### TODO-008: Modernize Provider Definitions

Status: Done

GitHub Issue: #25

Move provider metadata toward schema-backed structured definitions.

Acceptance criteria:

- Defines a schema for provider definitions.
- Adds validation for known provider files.
- Improves error messages for invalid provider files.
- Evaluates TOML, JSON, YAML, or another safe provider format.
- Adds tests for known provider definitions.

Suggested labels: `providers`, `schema`, `reliability`

### TODO-008-1: Migrate Provider Definitions to JSON and Evaluate Pydantic

Status: Done

GitHub Issue: #3 (closed)

Move provider source files from the legacy `.lay` key/value format to JSON and
decide whether Pydantic should own provider validation.

Completed by adopting Pydantic v2 as a runtime dependency, converting checked-in
provider definitions to JSON, committing generated JSON Schema documentation,
and removing the legacy `.lay` runtime parser.

Acceptance criteria:

- Converts checked-in provider definitions from `.lay` to `.lay.json`.
- Preserves provider codes, directories, runtime defaults, and downstream
  `providers_dict` behavior.
- Represents booleans, integers, float arrays, and header dictionaries as native
  JSON values.
- Evaluates adding Pydantic as a runtime or development dependency for provider
  models, JSON Schema generation, strict validation, and diagnostics.
- If Pydantic is adopted, adds typed provider models and generated schema docs.
- If Pydantic is not adopted, documents why stdlib validation remains preferable.
- Adds tests for converted provider definitions and invalid JSON cases.
- Removes or archives the legacy `.lay` parser only after JSON parity is proven.

Suggested labels: `providers`, `schema`, `dependencies`

### TODO-008-2: Add Complexity and Maintainability Quality Gates

Status: Done

GitHub Issue: #26 (closed)

Add gzkit-style code quality gates for Python complexity and maintainability
without introducing a gzkit runtime dependency.

Acceptance criteria:

- Evaluates Xenon/Radon for cyclomatic complexity and maintainability reporting.
- Adds any accepted tool as a development dependency only.
- Defines initial thresholds that are realistic for the legacy Ortho4XP codebase.
- Runs the gate on changed Python files first, with a documented path to expand
  coverage.
- Integrates the gate into repo-local quality-check and repo-hygiene
  skills/scripts.
- Documents local commands in `AGENTS.md` and contributor docs.
- Adds tests or fixtures around any wrapper script behavior.
- Does not add a gzkit dependency.

Suggested labels: `quality`, `dependencies`

### TODO-008-3: Extend Pydantic to Configuration and Source Data

Status: Done

GitHub Issue: #27 (closed)

Apply the provider-model pattern to the remaining structured inputs that still
depend on ad hoc parsing, `exec`, or loosely typed dictionaries, and move all
repo-owned structured source data to JSON.

Completed by adding Pydantic models for source data and config values,
renaming provider JSON files to `<name>.lay.json`, converting extents, filters,
and combined providers to double-extension JSON, generating schemas, and adding
loader/config compatibility tests.

Acceptance criteria:

- Defines Pydantic models for global and tile configuration values currently
  described by `O4_Cfg_Vars.py`.
- Replaces config-file value coercion and assignment paths in
  `O4_Config_Utils.py` with validated model updates, without breaking existing
  `Ortho4XP.cfg` or per-tile `.cfg` files.
- Models custom zoom zone entries so `zone_list` parsing no longer needs
  compatibility `exec` paths.
- Migrates remaining repo-owned structured source formats to JSON, including
  extent `.ext`, color filter `.flt`, and combined provider `.comb` data.
- Preserves legacy format provenance with double-extension JSON filenames, such
  as `<name>.ext.json`, `<name>.flt.json`, `<name>.lay.json`, and
  `<name>.comb.json`, while the runtime loader reads JSON only for repo-owned
  source data.
- Verifies the recently migrated provider `.lay` data remains JSON-backed and
  does not reintroduce `.lay` parsing.
- Generates schema documentation for every JSON-backed structured source format.
- Adds `unittest` coverage for valid files, malformed files, type errors,
  unknown fields, JSON migration parity, and legacy user-config compatibility
  behavior.

Suggested labels: `schema`, `config`, `reliability`

### TODO-008-04: Consolidate Native Triangle Sources

Status: Done

GitHub Issue: #28 (closed)

Consolidate the native Triangle source surface after confirming Python only
binds to the built `Triangle4XP` and `triangle` executables.

Completed by removing the unbound `Triangle4XP_v130.c` historical source,
keeping `Triangle4XP.c` and `triangle.c` as CMake-built native targets,
documenting the runtime relationship in `Utils/src/README.md`, and preserving
repo-scope native quality checks against the CMake compile database.

Acceptance criteria:

- Removes the unbound `Triangle4XP_v130` source from active repo/build
  surfaces unless a current runtime requirement is found.
- Keeps the production `Triangle4XP` and generic `triangle` native utilities
  buildable through CMake.
- Documents the remaining native source files and their runtime relationship to
  Python.
- Keeps `quality-check` running against the repo native build graph.
- Verifies with the full repository quality check.

Suggested labels: `native`, `quality`, `cleanup`

### TODO-009: Replace Common Bare Exception Handlers

Status: Done

GitHub Issue: #4

Replace high-impact bare `except:` blocks with specific exception handling.

Acceptance criteria:

- Identifies common or high-traffic bare exception handlers.
- Replaces file operation handlers with `OSError` or more specific exceptions.
- Replaces network handlers with `requests.RequestException`.
- Replaces parsing handlers with `ValueError` or more specific exceptions.
- Logs exception details instead of silently swallowing failures.

Suggested labels: `reliability`, `diagnostics`, `quick-win`

## Phase 2: Diagnostics and Shared Execution Infrastructure

### TODO-010: Centralize Subprocess Execution

Status: Done

GitHub Issue: #5

Create a shared helper for external tool execution.

Acceptance criteria:

- Supports `Triangle4XP`, `triangle`, `moulinette`, `nvcompress`, `DDSTool`,
  and `7z`. GDAL CLI subprocess support was retired by TODO-028; GDAL raster
  work now uses `osgeo.gdal` Python bindings.
- Captures stdout and stderr.
- Logs command, return code, and a short error summary.
- Handles platform-specific environment setup.
- Returns structured success/failure information.

Suggested labels: `subprocess`, `diagnostics`, `refactor`

### TODO-011: Centralize Logging Behavior

Status: Done

GitHub Issue: #6

Introduce a logging abstraction that can replace scattered output paths over time.

Acceptance criteria:

- Supports CLI output.
- Supports GUI console output.
- Writes persistent events as JSONL to `Ortho4XP.log.json`.
- Keeps verbosity scoped to human-visible CLI and GUI console output.
- Provides structured exception and external-command reporting suitable for batch builds.

Suggested labels: `logging`, `diagnostics`, `refactor`

### TODO-012: Improve Network and Imagery Failure Reporting

Status: Done

GitHub Issue: #7 (closed)

Make imagery download failures easier to diagnose without excessive noise.

Completed by adding structured sanitized imagery-failure logging,
retry-aware failure records, configurable texture retry limits,
end-of-download failure summaries, documentation, and deterministic tests.

Acceptance criteria:

- Tracks failed provider, URL type, HTTP status, and retry count.
- Avoids full URL output unless debug logging is enabled.
- Summarizes failed textures at the end of a tile or batch build.
- Makes retry limits configurable and documented.
- Adds tests for summary/reporting behavior where feasible.

Suggested labels: `imagery`, `network`, `diagnostics`

## Phase 3: XP12 Mesh, Mask, and Texture Pipeline

### TODO-013: Enforce XP12 Water Tech and Purge Legacy Flags

Status: Done

GitHub Issue: #8 (closed)

Remove backward-compatible water rendering states to prevent accidental legacy compilation.

Completed by fixing `water_tech` to XP12 in the config registry,
rejecting legacy XP11 water modes through shared config validation,
applying that validation to tile/global/backup/GUI config load paths,
and removing the legacy XP11 overlay branch from DSF generation.

Acceptance criteria:

- Removes `"XP11"` and `"XP11 + bathy"` choices from active configuration arrays.
- Hardcodes `water_tech = "XP12"` as the only supported default.
- Removes GUI controls for deprecated water modes.
- Adds validation that rejects legacy water mode values in existing configs with an actionable error.
- Adds tests for config migration/rejection behavior.

Suggested labels: `xp12max`, `mesh`, `breaking-change`

### TODO-014: Require Valid Bathymetry Inputs for Physical Water Meshes

Status: Done

GitHub Issue: #9 (closed)

Make XP12 3D bathymetry requirements explicit before deeper mesh rewrites.

Completed by defining a validated bathymetry raster contract, extracting
`elevation` and `sea_level` raster atoms from XP12 Global Scenery DSFs,
requiring those rasters only for tiles whose mesh contains water triangles,
failing DSF generation through the controlled UI error path when required input
is missing or invalid, and preserving validated DEMN/DEMS payloads in generated
XP12 DSFs. The implementation keeps future custom bathymetry providers behind
the same validation boundary.

Acceptance criteria:

- Identifies where mesh elevation and water-depth data enter `src/O4_Mesh_Utils.py`.
- Defines the minimum valid bathymetry data contract.
- Fails fast with an informative runtime exception when required bathymetry data is unavailable.
- Adds tests for validation behavior without requiring full tile builds.

Suggested labels: `xp12max`, `mesh`, `validation`

### TODO-015: Rewrite Alpha Masking for Logarithmic BC3 Blending

Status: Done

GitHub Issue: #10

Overhaul coastline transitions by mapping distance fields to progressive logarithmic alpha curves.

Acceptance criteria:

- Locates alpha generation blocks inside `src/O4_Mask_Utils.py`.
- Replaces flat linear transparency transformations in distance-field paths with a progressive logarithmic formula.
- Preserves clean transparency data for BC3/DXT5 output.
- Adds deterministic tests for the alpha mapping function.

Suggested labels: `xp12max`, `textures`, `masks`

### TODO-016: Integrate Automated sRGB Histogram Color Normalization

Status: Done

GitHub Issue: #11

Completed by adding opt-in neighbor-edge texture color normalization using
Pillow/NumPy sRGB linear-light statistics, bounded correction clamps, config
integration, documentation, and deterministic tests.

Neutralize mismatched imagery tile boundaries before texture compression.

Acceptance criteria:

- Adds an imaging filter hook in `src/O4_Imagery_Utils.py`.
- Uses Pillow first unless OpenCV is justified by measurable benefit.
- Computes edge-pixel luminance and RGB distributions from neighboring validated tiles.
- Applies an sRGB-aware correction curve before compressor handoff.
- Adds deterministic tests for the normalization function.

Suggested labels: `xp12max`, `imagery`, `color-pipeline`

### TODO-017: Develop Non-Destructive DSF Header Splicing Loop

Status: Done

GitHub Issue: #12 (closed)

Implemented by adding a staged DSFTool bridge that converts default and
generated DSFs to text through the shared subprocess helper, extracts only
allowlisted season/vegetation/sound/friction header lines, splices them into
generated DSF text, and replaces the generated `.dsf.tmp` only after
`--text2dsf` succeeds.

Build a data bridge using `DSFTool` to inherit native X-Plane 12 features into custom ortho tile headers.

Acceptance criteria:

- Identifies the current Step 4 DSF build entry point.
- Uses the shared subprocess helper for `DSFTool --dsf2text` and `--text2dsf`.
- Parses default DSF header tokens for seasons, vegetation, sound, and runway friction fields.
- Prepends supported native header data to generated ortho DSF text before binary packing.
- Adds parser tests with fixture text.

Suggested labels: `xp12max`, `dsf-bridge`, `seasons`

### TODO-018: Deploy Multi-Threaded Texture Encoder Backend

Status: Done

GitHub Issue: #13

Remove serial texturing bottlenecks before adding GPU-specific backends.

Acceptance criteria:

- Decouples image slicing and `.dds` conversion loops in `src/O4_Tile_Utils.py` from serial external calls.
- Uses `concurrent.futures` for bounded CPU parallelism.
- Routes all external encoder calls through the shared subprocess helper.
- Defines extension points for CUDA/Vulkan encoder backends.
- Adds tests for task planning and failure aggregation.

Suggested labels: `xp12max`, `performance`, `gpu`

## Phase 4: Architecture Breakaway

### TODO-019: Separate GUI, CLI, and Core Build Logic

Status: Done

GitHub Issue: #14

Begin separating presentation, command-line parsing, and build orchestration.

Completed by adding a tested `O4_Build_Core.build_tile_all()` orchestration
boundary for the current all-in-one tile sequence, preserving
`O4_Tile_Utils.build_all()` as a compatibility wrapper, and routing the
launcher's command-line all-in-one path through the same structured core API.
The GUI all-in-one button continues to target the compatibility wrapper, so GUI
and CLI all-in-one behavior now share the core build boundary.

Acceptance criteria:

- Identifies current GUI, CLI, and core build responsibilities.
- Proposes a staged migration path.
- Moves one small build step behind a callable core API.
- Adds tests for the extracted behavior.

Suggested labels: `architecture`, `refactor`, `long-term`

### TODO-020: Reduce Global Mutable State

Status: Done

GitHub Issue: #15

Gradually replace global state with explicit context and result objects.

Completed by adding `BuildContext` property facade over UI process-state globals
(`red_flag`, `is_working`, `verbosity`, `cleaning_level`, `gui`) and threading
it as an explicit parameter through the build pipeline. Build step functions
(`build_poly_file`, `build_mesh`, `build_masks`, `build_tile`) accept `ctx=None`
with internal fallback. `build_tile_all`, GUI handlers, and `build_tile_list`
construct and pass `BuildContext` explicitly. Sub-delegate functions continue
reading `UI.*` directly; the facade keeps them consistent.

Acceptance criteria:

- Identifies major global state used by provider dictionaries, UI flags, red/working flags, and imagery state.
- Introduces a small context/config object for one workflow.
- Avoids broad rewrites in the first issue.
- Adds tests or smoke checks for the migrated path.

Suggested labels: `architecture`, `state`, `refactor`

### TODO-021: Minimize Import-Time Side Effects

Status: Done

GitHub Issue: #16

Move side effects out of module import paths and into explicit initialization functions.

Completed by moving `O4_Config_Utils` runtime configuration initialization
behind an idempotent `initialize_global_config()` function, preserving direct
tile construction through lazy initialization in `CFG.Tile`, and adding import
safety tests that prove plain import no longer reads or creates `Ortho4XP.cfg`
or mutates config-backed globals.

Acceptance criteria:

- Identifies modules with platform detection, path setup, provider loading, or printing during import.
- Extracts one side-effecting import path into an explicit initializer.
- Ensures tests can import the changed module safely.
- Routes errors through the shared logging path where available.

Suggested labels: `imports`, `tests`, `refactor`

### TODO-022: Execute Headless CLI Transition

Status: Done

GitHub Issue: #17

Completed by adding early-dispatched `validate-job` and `build-job` headless
subcommands, a tested `build_job.toml` parser, neutral build plan/result
models, and `O4_Build_Core.build_batch()` for multi-tile execution. Validation
runs without GUI/config side effects, supports explicit tiles plus inclusive
bounds, validates normal and combined provider keys, resolves relative output
directories from the job file, and returns deterministic exit codes. GUI batch
work now routes through the same core batch API.

Expose a pure, headless CLI engine for batch automation.

Acceptance criteria:

- Adds a CLI entry point driven by a structured `build_job.toml` file.
- Supports tile bounds, provider keys, zoom levels, and output directories.
- Validates a multi-tile build plan without display server dependencies.
- Keeps GUI as a presentation layer over the same core build API.

Suggested labels: `breakaway`, `architecture`, `headless`

## Phase 5: Repository Health and Releases

### TODO-023: Add or Verify Repository Metadata

Status: Done

GitHub Issue: #18

Add standard repository metadata and community files.

Completed by adding a root `LICENSE` (GPL v3, same text as `Licence/gpl.txt`),
`SECURITY.md` pointing to GitHub Security Advisories, bug report and feature
request issue templates with community contact links, and a pull request
template. GitHub topics (`x-plane`, `scenery`, `orthophoto`, `gis`,
`flight-simulator`) should be set in the repository settings.

Acceptance criteria:

- Verifies current license state and adds or updates `LICENSE` if appropriate.
- Adds `CONTRIBUTING.md`.
- Adds `SECURITY.md`.
- Adds issue templates if issues are enabled.
- Adds a pull request template.
- Recommends GitHub topics such as `x-plane`, `scenery`, `orthophoto`, `gis`, and `flight-simulator`.

Suggested labels: `repository-health`, `documentation`

### TODO-024: Publish Release Guidance

Status: Done

GitHub Issue: #19

Document the release process for PyInstaller onedir bundles.

Completed by adding `RELEASE.md` covering per-platform build targets,
PyInstaller commands, bundled data layout, native tool production and staging,
packaged vs. source dependency differences, SemVer versioning policy starting at
`v1.0.0`, release verification steps, and GitHub Release publishing guidance.

Acceptance criteria:

- Documents Windows 11, current Apple Silicon macOS, and Ubuntu release targets.
- Documents per-platform PyInstaller build commands.
- Documents bundled data layout.
- Documents how bundled native tools are produced and staged.
- Documents how packaged dependencies differ from source dependencies.
- Defines release versioning policy, including the fork's switch to SemVer at
  `v1.0.0`.
- Documents release verification steps before publishing.

Suggested labels: `release`, `documentation`, `packaging`

### TODO-025: Decompose Legacy Oversized Python Modules and Classes

Status: Done

GitHub Issue: #29

Reduce the module/class size warnings now surfaced by the gzkit-parity
quality-check code-quality audit.

Completed by decomposing `O4_Airport_Utils.py` (1382 lines, 14 functions) into
three focused modules: `O4_Airport_Discovery.py` (OSM parsing, airport
identification, runway reconstruction, reporting), `O4_Airport_Geometry.py`
(surface geometry construction, DEM smoothing, boundary updates), and
`O4_Airport_Encoding.py` (encoding airport features into the vector map).
The single consumer `O4_Vector_Map.py` was updated to import from the three
new modules. The broad module-size waiver for `O4_Airport_Utils.py` was
replaced with a narrower waiver for `O4_Airport_Discovery.py` (667 lines,
soft warning only; the other two modules are under the 600-line threshold).
The complexity baseline was regenerated. Import tests were added.

Acceptance criteria:

- Breaks the current warning set into independently mergeable decomposition
  issues or resolves a first representative module/class.
- Replaces broad size waivers with narrower waivers as modules are split.
- Keeps quality-check green throughout; no unwaived hard-cap module or
  class-size blocks.
- Adds focused tests for any extracted behavior.

Suggested labels: `quality`, `architecture`, `refactor`

## Phase 6: GIS, Raster, and Imagery Modernization

### TODO-026: Document GIS/Raster/Imagery Technology Map

Status: Done

GitHub Issue: #30

Harvest the current project understanding of the GIS, raster, and imagery
toolchain before adding more visual processing features.

Acceptance criteria:

- Inventories active GIS/raster/imagery tools and libraries, including
  historical `gdal_translate`/`gdalwarp` use, current GDAL bindings, Pillow,
  NumPy, DDS encoders, provider color filters, mask generation, GeoTIFF export,
  and XP12 DSF raster handling.
- Traces imagery and raster data flow from provider download/cache through
  crop/warp, masks, color filters, optional normalization, GeoTIFF export, and
  DDS handoff.
- Documents CRS/projection assumptions, GDAL command options that existed before
  the bindings migration, and where internal/Pillow paths were used instead of
  GDAL.
- Documents current resampling, nodata, alpha, mask, and compression
  assumptions, including known gaps or undefined behavior.
- Evaluates staged opportunities such as GDAL VRT use, explicit resampling
  policy, overviews/COG-style debug exports, rasterio/GDAL Python bindings,
  OpenCV, sharpening, color correction, and compression-aware image QA.
- Recommends concrete follow-up issues for sharpening, color correction, GDAL
  pipeline improvements, and texture compression validation.
- Keeps the first deliverable documentation/audit focused; does not add new
  runtime dependencies or change generated scenery output in this issue.

Suggested labels: `documentation`, `imagery`, `gis`, `color-pipeline`

### TODO-027: Define XP12-Native Scenery Compiler/Workbench Strategy

Status: Done

Inventory / completion note: the TODO-027 strategy work is represented by
`docs/superpowers/specs/2026-06-13-xp12-native-scenery-compiler-audit.md`
and
`docs/superpowers/specs/2026-06-13-xp12-native-scenery-compiler-phase2-naming.md`.
The audit documents legacy `zOrtho4XP_` / `yOrtho4XP_` assumptions, XP12
scenery-stack interaction, SimHeaven/X-WORLD architectural patterns, project
ownership boundaries, first-phase non-goals, and concrete follow-up slices.
The naming/layout design defines the XP12-native package naming, metadata,
validation, and migration strategy. Follow-up implementation work has also
landed: package naming config, `package.json` generation, `validate-package`,
`upgrade-package`, `SceneryINI`, `SceneryManager`, `scenery` CLI commands, and
`upgrade-package --update-scenery`.

Verification note: TODO-027-focused tests passed with 92 tests, and full
`unittest` discovery passed with 320 tests. The remaining full quality gate is
tracked separately by TODO-049 / GHI #32 for repo-wide Ruff baseline drift.

GitHub Issue: #31 (closed 2026-06-14)

Define the beyond-ortho direction for the fork as an XP12-native scenery
compiler/workbench. The goal is to understand public scenery-stack techniques
and architecture, not to copy third-party assets or redistribute third-party
packages.

Acceptance criteria:

- Audits current `zOrtho4XP_` naming, package layout, and scenery-order
  assumptions; identifies what XP12 still requires versus what is legacy
  convention.
- Documents how generated ortho/base-mesh packages interact with XP12 Global
  Scenery, overlays, SimHeaven/X-WORLD-style packages, libraries, and
  `scenery_packs.ini` ordering.
- Studies public SimHeaven/X-WORLD/X-WORLD Pro techniques at the architecture
  level only: layered packages, OSM/building-footprint data use, vegetation
  libraries, regionalization, sound/effect layers, VFR object layers, optional
  orthos, and install/validation ergonomics.
- Defines project ownership boundaries: mesh generation, imagery/raster
  pipeline, bathymetry, DSF metadata/header preservation, generated package
  validation, dependency checks, and compatibility reporting.
- Defines first-phase non-goals: no copying third-party assets, no
  redistributing SimHeaven data, no replacing SimHeaven packages, and no broad
  object-library generator until the base compiler architecture is understood.
- Proposes a future XP12-native package naming/layout strategy that does not
  depend on `zOrtho4XP_` as the primary mechanism.
- Recommends concrete follow-up issues for scenery-stack validation, package
  metadata generation, XP12 package layout modernization, optional companion
  overlay layers, and future naming/release-positioning work for `v1.0.0`.
- Keeps this first deliverable documentation/design focused; does not change
  generated scenery output in this issue.

Suggested labels: `documentation`, `architecture`, `xp12max`, `scenery-stack`

## Phase 7: Implementation Waves (from TODO-026 roadmap)

### TODO-028: GDAL Python Bindings Migration

Status: Done

Verification note: implemented in Wave 1. Focused GDAL binding tests, full
`unittest` discovery, changed-file Ruff/format, and changed-file `ty` passed.
The full repository quality gate is blocked by TODO-049 / GHI #32 due existing
repo-wide Ruff baseline drift outside this migration.

Replace all GDAL CLI subprocess calls (`gdal_translate`, `gdalwarp`) with
`osgeo.gdal` Python bindings. Remove `gdalwarp_alternative()` Pillow-based
reprojection. Make GDAL a hard runtime dependency.

Acceptance criteria:

- Adds `gdal` to `pyproject.toml` dependencies
- Replaces `gdal_translate`/`gdalwarp` subprocess calls in
  `O4_Texture_Conversion_Utils.py` with `gdal.Translate()`/`gdal.Warp()`
- Replaces `gdalwarp_alternative()` in `O4_Imagery_Utils.py` with `gdal.Warp()`
- Replaces `gdalwarp_alternative()` in `O4_Mask_Utils.py` with `gdal.Warp()`
- Makes `osgeo.gdal` import unconditional in `O4_DEM_Utils.py`
- Removes `resolve_tool("gdal_translate")` and `resolve_tool("gdalwarp")` from
  `O4_External_Tool_Paths.py`
- Adds GDAL to PyInstaller packaging for all three platforms
- Updates tests

Suggested labels: `gdal`, `dependencies`, `refactor`

### TODO-029: Upgrade nvcompress Flags

Status: Done

Verification note: implemented in Wave 1. Encoder command tests were updated in
the Wave 1 commits. The full repository quality gate is blocked by TODO-049 /
GHI #32 due existing repo-wide Ruff baseline drift outside this flag upgrade.

Upgrade nvcompress commands on Windows/Linux to use `-highest -mipfilter kaiser
-alpha_dithering` for maximum BC1/BC3 quality.

Acceptance criteria:

- Updates `O4_Native_Texture_Encoder.py` BC1 command to:
  `nvcompress -bc1 -highest -alpha_dithering -mipfilter kaiser <input> <output>`
- Updates BC3 command to:
  `nvcompress -bc3 -highest -alpha_dithering -mipfilter kaiser -alpha <input> <output>`
- Preserves DDSTool commands on macOS (already optimal)
- Adds tests for command construction

Suggested labels: `textures`, `quality`, `quick-win`

### TODO-030: aiohttp + asyncio Tile Downloads

Status: Done

GitHub Issue: #33

Completion note: implemented with `aiohttp` as a runtime dependency, a focused
async HTTP request state machine in `O4_Async_HTTP`, an async-compatible
`O4_Imagery_Utils.async_http_request_to_image()` path, and a synchronous
compatibility wrapper for existing callers. Texture downloads now route through
`O4_Texture_Download_Scheduler.async_download_textures()`, which uses asyncio
tasks with semaphore backpressure, preserves the conversion queue handoff,
keeps retry/failure aggregation, and dispatches JPEG build work through
`asyncio.to_thread()`.

Verification note: focused async imagery/scheduler tests, full `unittest`
discovery, Ruff, Ruff format, changed-file `ty`, complexity checks, clang-tidy,
and the native CMake build all passed through the full repository quality gate:
`uv run python .codex/skills/quality-check/scripts/quality_check.py`.

Replace `requests` + `ThreadPoolExecutor` with `aiohttp` + `asyncio` for tile
downloads. Provides native async I/O, connection pooling, backpressure via
semaphore, and easier cancellation.

Acceptance criteria:

- Adds `aiohttp` to `pyproject.toml` dependencies
- Replaces `http_request_to_image()` with async `aiohttp` implementation
- Replaces `ThreadPoolExecutor` download workers with `asyncio.gather()`
- Dispatches CPU-bound JPEG decoding via `asyncio.to_thread()`
- Maintains retry logic and failure tracking
- Adds tests for async download behavior

Suggested labels: `async`, `network`, `performance`

### TODO-031: Per-Stage Resampling Policy

Status: Done
GitHub: #34

Define per-stage resampling defaults with optional config overrides.

Acceptance criteria:

- Adds config keys for resampling method per stage:
  - Texture downscale (provider → 4096): LANCZOS default
  - Mask resize (6144 → 4096): NEAREST default
  - Reprojection warp (`gdal.Warp()`): BICUBIC default
  - Normalization edge sampling: BILINEAR default
- Replaces hardcoded `BICUBIC` throughout codebase with config-driven methods
- Documents resampling choices in config hints
- Adds tests for config-driven resampling selection

Suggested labels: `config`, `quality`, `quick-win`

### TODO-032: In-Memory VRT Pipeline

Status: Pending

GitHub Issue: #35

Implement zero-intermediate-files streaming pipeline: HTTP tiles → VRT stitch →
warp → color → normalize → DDS, eliminating all intermediate JPEG/PNG/GeoTIFF
writes.

Acceptance criteria:

- Builds VRT in-memory from tile BytesIOs via `gdal.BuildVRT()`
- Streams through `gdal.Warp()` for reprojection
- Passes NumPy array to color filter and normalization
- Writes temp PNG only for nvcompress (or investigates stdin support)
- Removes intermediate cache-write paths from `O4_File_Names.py`
- Adds tests for VRT assembly and streaming

Suggested labels: `performance`, `architecture`, `gdal`

### TODO-033: COG-Style GeoTIFF Export

Status: Pending

Add optional Cloud-Optimized GeoTIFF mode with tiling and overviews.

Acceptance criteria:

- Adds `cog_export` config flag (default False)
- When enabled: `gdal.Translate(co=TILED=YES, BLOCKXSIZE=512, BLOCKYSIZE=512)`
- Adds `gdal.AddOverview()` for pyramid levels
- Documents COG benefits (streaming, progressive loading)
- Adds tests for COG export

Suggested labels: `geotiff`, `quality`

### TODO-034: DDS Compression QA

Status: Pending

Add optional compression-aware quality assurance step comparing source PNG with
compressed DDS using PSNR/SSIM metrics.

Acceptance criteria:

- Adds `dds_qa_enabled` config flag (default False)
- Decodes compressed DDS back to PNG
- Computes PSNR, SSIM, or MSE between source and decoded
- Warns if quality drops below configurable threshold
- Adds tests for QA metrics computation

Suggested labels: `quality`, `textures`

### TODO-035: Unsharp Mask Sharpening

Status: Pending

Add `"sharpen"` as a supported operation in the color filter pipeline.

Acceptance criteria:

- Adds `"sharpen"` operation to `color_transform()` with parameters
  `[radius, amount, threshold]` mapped to Pillow `ImageFilter.UnsharpMask()`
- Applies after color filter, before sRGB normalization
- Documents sharpening parameters in filter schema
- Adds tests for sharpening operation

Suggested labels: `imagery`, `quality`

### TODO-036: Event Bus

Status: Pending

Add event-driven architecture for module communication. Reference:
ORTHO4XP_V3 `O4_EventBus`.

Acceptance criteria:

- Implements singleton `EventBus` with thread-safe publish/subscribe
- Defines events: `TILE_START`, `TILE_PROGRESS`, `TILE_COMPLETE`, `TILE_ERROR`,
  `PIPELINE_STEP`, `CACHE_HIT`
- Emits events from build pipeline stages
- Adds tests for event emission and subscription

Suggested labels: `architecture`, `events`

### TODO-037: Pipeline Orchestrator

Status: Pending

Add named-step pipeline orchestration with timing, status tracking, and clean
failure handling. Reference: ORTHO4XP_V3 `O4_Pipeline`.

Acceptance criteria:

- Implements `Pipeline` class with named steps
- Tracks step timing and status (pending/running/complete/error)
- Publishes `PIPELINE_STEP` events
- Stops cleanly on step failure without file corruption
- Adds tests for pipeline execution and failure handling

Suggested labels: `architecture`, `pipeline`

### TODO-038: Smart Cache

Status: Pending

Add SHA256-based tile parameter caching to skip rebuilds when parameters are
unchanged. Reference: ORTHO4XP_V3 `O4_Dependency`.

Acceptance criteria:

- Computes SHA256 hash of tile build parameters
- Stores hash in `tile_meta.json` after successful build
- Skips rebuild if hash matches cached value
- Adds tests for cache hit/miss behavior

Suggested labels: `performance`, `cache`

### TODO-039: Provider Scoring

Status: Pending

Add automatic quality scoring for downloaded imagery. Reference: ORTHO4XP_V3
`O4_Provider_Score`.

Acceptance criteria:

- Scores each downloaded image on 5 criteria: noise, JPEG compression, clouds,
  color drift, seam risk
- Computes global score 0-100 with quality label
- Logs scores per provider
- Adds tests for scoring algorithms

Suggested labels: `imagery`, `quality`

### TODO-040: Provider Failover

Status: Pending

Add automatic provider failover with blacklist. Reference: ORTHO4XP_V3
`O4_Provider_Abstraction`.

Acceptance criteria:

- Implements provider abstraction layer between pipeline and imagery providers
- Blacklists provider after 3 consecutive failures (5-minute timeout)
- Auto-selects next active provider by priority order
- Thread-safe for parallel builds
- Adds tests for failover behavior

Suggested labels: `reliability`, `network`

### TODO-041: AI Cloud/Seam Detection

Status: Pending

Add AI-based cloud and seam detection for imagery quality control. Reference:
ORTHO4XP_V3 `O4_Provider_Score` enhanced.

Acceptance criteria:

- Detects clouds via 3 criteria: dense clouds, atmospheric veil, blue sky exclusion
- Tolerates up to 5% cloud coverage (avoids false positives)
- Detects fog/veil via local variance
- Analyzes seam risk on 4 independent edges
- Detects directional seams (1 problematic edge) and abrupt gradients
- Adds tests for detection algorithms

Suggested labels: `imagery`, `quality`, `ai`

### TODO-042: XP12 Materials

Status: Pending

Add automatic XP12 material property generation from imagery analysis.
Reference: ORTHO4XP_V3 `O4_XP12_Materials`.

Acceptance criteria:

- Detects ground type from imagery: forest, water, snow, urban, field, bare soil, beach
- Generates XP12 parameters: `WET`, `ROUGHNESS`, `SPECULAR`, `NORMAL_SCALE`
- Injects parameters into `.ter` terrain files
- Idempotent (re-application updates without duplication)
- Calibrates profiles per ground type (e.g., water: wet=1.0, specular=0.80)
- Adds tests for ground type detection and parameter generation

Suggested labels: `xp12max`, `materials`

### TODO-043: Night Continuity

Status: Pending

Add emissive mask generation from OSM semantic data for night-time visual
continuity. Reference: XP-Ortho-NC.

Acceptance criteria:

- Generates emissive mask from OSM roads (corridor lighting), land use (urban
  density), and places (settlement anchors)
- Produces semantic layers: `emissive_mask.png`, `road_energy.png`, `urban_density.png`
- Deterministic (same input → same output)
- Non-destructive (does not alter daytime imagery)
- Aligns with X-Plane scenery layering
- Adds tests for mask generation

Suggested labels: `xp12max`, `night`, `osm`

### TODO-044: GPU Backend

Status: Pending

Add GPU-accelerated texture processing with silent CPU fallback. Reference:
ORTHO4XP_V3 `O4_GPU_Backend` + TODO-018.

Acceptance criteria:

- Detects GPU availability (NVIDIA CUDA via CuPy or PyTorch)
- Routes histogram, color transfer, and feathering operations to GPU when available
- Falls back silently to CPU when no GPU
- Benchmarks CPU vs GPU performance
- Adds tests for GPU/CPU path selection

Suggested labels: `performance`, `gpu`

### TODO-045: Automatic Backups + Rollback

Status: Pending

Add timestamped automatic backups with 1-click rollback. Reference:
ORTHO4XP_V3 `O4_Backup_Manager`.

Acceptance criteria:

- Backs up critical files (`.py`, `.comb`, `.ccorr`, `.dds`, `.cfg`) before modification
- Stores timestamped backups with reason metadata
- Maximum 10 backups per file (auto-purge oldest)
- Provides `rollback.py` script for 1-click restore
- Adds tests for backup/rollback behavior

Suggested labels: `reliability`, `developer-experience`

### TODO-046: RAM Protection

Status: Pending

Add real-time RAM monitoring with automatic cleanup. Reference: ORTHO4XP_V3
`O4_Memory_Manager`.

Acceptance criteria:

- Monitors system RAM via `psutil` (graceful degradation if unavailable)
- Triggers cleanup when threshold exceeded (default: 80% system RAM)
- Configurable cache size limit (default: 8 GB)
- Provides `check_and_cleanup_memory()` for heavy loops
- Adds tests for memory monitoring

Suggested labels: `reliability`, `performance`

### TODO-047: Debug Visualizations

Status: Pending

Add diagnostic visualization outputs for build quality analysis. Reference:
ORTHO4XP_V3 `O4_Benchmark`.

Acceptance criteria:

- Generates `seam_risk_map.png` highlighting problematic zones in red
- Generates `color_transfer_compare.png` showing before/after side-by-side
- Generates `blur_map.png` showing sharpness (green=sharp, blue=blur)
- Outputs to `_debug_viz/` directory
- Adds tests for visualization generation

Suggested labels: `debug`, `quality`

### TODO-048: Theme Manager

Status: Pending

Add GUI theme management with multiple presets. Reference: ORTHO4XP_V3
`O4_Theme_Manager`.

Acceptance criteria:

- Implements 5 themes: default, slate, desert sand, deep ocean, custom
- Persists theme selection between sessions
- Cross-platform compatible (Windows, macOS, Linux)
- Adds tests for theme loading and persistence

Suggested labels: `gui`, `developer-experience`

### TODO-049: Repair Repo-Wide Ruff Quality Gate Baseline

Status: Done

GitHub Issue: #32

Completion note: verified on 2026-06-14 that the maintained quality gate now
passes through repo-wide Ruff, later Python quality stages, and native checks.
No script behavior change was needed; the previously recorded Ruff failure was
stale backlog evidence. Current verification showed:

- `uv run python .codex/skills/quality-check/scripts/quality_check.py --skip-native`
  passes all Python-side quality stages.
- `uv run python .codex/skills/quality-check/scripts/quality_check.py` passes
  the full gate, including LLVM/CMake native checks.
- `uv run python -m unittest discover -s tests` passes with 323 tests.
- Repo-wide Ruff check passes for `Ortho4XP.py`, `src`, `tests`, and maintained
  skill scripts.
- Ruff format, `ty`, whitespace, code-quality audits, Xenon/Radon/Lizard/
  Cohesion complexity gates, `clang-tidy`, and CMake native build checks pass.

Historical Wave 1 verification had reported 198 repo-wide Ruff findings before
the gate could reach later stages. That state no longer reproduces.

Acceptance criteria:

- Makes `uv run python .codex/skills/quality-check/scripts/quality_check.py`
  reach later quality stages instead of failing at repo-wide Ruff lint.
- Either fixes the repo-wide Ruff findings or introduces an explicit,
  documented baseline/target policy for legacy debt.
- Keeps changed-file Ruff, Ruff format, `ty`, and `unittest` checks strict for
  new work.
- Handles `src/Unused` and `.codex/skills` intentionally and documents the
  chosen policy.
- Adds or updates tests for quality-check target selection if script behavior
  changes.

Suggested labels: `quality`
