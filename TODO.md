# TODO

Each TODO below is intended to become one GitHub Issue (GHI). Numbers are execution-priority order and may be renumbered when dependencies change. Keep issue bodies scoped, actionable, independently mergeable, and aligned with the current repo policy: Python 3.13+, `uv`, `ruff`, `ty`, `unittest`, and LLVM/Clang.

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
- Requires Python 3.13+.
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

- Documents Python 3.13+, `uv sync --dev`, Ruff, ty, and `unittest`.
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

- Supports `Triangle4XP`, `triangle`, `moulinette`, `nvcompress`, `DDSTool`, `gdal_translate`, `gdalwarp`, and `7z`.
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

GitHub Issue: #11

Neutralize mismatched imagery tile boundaries before texture compression.

Acceptance criteria:

- Adds an imaging filter hook in `src/O4_Imagery_Utils.py`.
- Uses Pillow first unless OpenCV is justified by measurable benefit.
- Computes edge-pixel luminance and RGB distributions from neighboring validated tiles.
- Applies an sRGB-aware correction curve before compressor handoff.
- Adds deterministic tests for the normalization function.

Suggested labels: `xp12max`, `imagery`, `color-pipeline`

### TODO-017: Develop Non-Destructive DSF Header Splicing Loop

GitHub Issue: #12

Build a data bridge using `DSFTool` to inherit native X-Plane 12 features into custom ortho tile headers.

Acceptance criteria:

- Identifies the current Step 4 DSF build entry point.
- Uses the shared subprocess helper for `DSFTool --dsf2text` and `--text2dsf`.
- Parses default DSF header tokens for seasons, vegetation, sound, and runway friction fields.
- Prepends supported native header data to generated ortho DSF text before binary packing.
- Adds parser tests with fixture text.

Suggested labels: `xp12max`, `dsf-bridge`, `seasons`

### TODO-018: Deploy Multi-Threaded Texture Encoder Backend

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

GitHub Issue: #14

Begin separating presentation, command-line parsing, and build orchestration.

Acceptance criteria:

- Identifies current GUI, CLI, and core build responsibilities.
- Proposes a staged migration path.
- Moves one small build step behind a callable core API.
- Adds tests for the extracted behavior.

Suggested labels: `architecture`, `refactor`, `long-term`

### TODO-020: Reduce Global Mutable State

GitHub Issue: #15

Gradually replace global state with explicit context and result objects.

Acceptance criteria:

- Identifies major global state used by provider dictionaries, UI flags, red/working flags, and imagery state.
- Introduces a small context/config object for one workflow.
- Avoids broad rewrites in the first issue.
- Adds tests or smoke checks for the migrated path.

Suggested labels: `architecture`, `state`, `refactor`

### TODO-021: Minimize Import-Time Side Effects

GitHub Issue: #16

Move side effects out of module import paths and into explicit initialization functions.

Acceptance criteria:

- Identifies modules with platform detection, path setup, provider loading, or printing during import.
- Extracts one side-effecting import path into an explicit initializer.
- Ensures tests can import the changed module safely.
- Routes errors through the shared logging path where available.

Suggested labels: `imports`, `tests`, `refactor`

### TODO-022: Execute Headless CLI Transition

GitHub Issue: #17

Expose a pure, headless CLI engine for batch automation.

Acceptance criteria:

- Adds a CLI entry point driven by a structured `build_job.toml` file.
- Supports tile bounds, provider keys, zoom levels, and output directories.
- Validates a multi-tile build plan without display server dependencies.
- Keeps GUI as a presentation layer over the same core build API.

Suggested labels: `breakaway`, `architecture`, `headless`

## Phase 5: Repository Health and Releases

### TODO-023: Add or Verify Repository Metadata

GitHub Issue: #18

Add standard repository metadata and community files.

Acceptance criteria:

- Verifies current license state and adds or updates `LICENSE` if appropriate.
- Adds `CONTRIBUTING.md`.
- Adds `SECURITY.md`.
- Adds issue templates if issues are enabled.
- Adds a pull request template.
- Recommends GitHub topics such as `x-plane`, `scenery`, `orthophoto`, `gis`, and `flight-simulator`.

Suggested labels: `repository-health`, `documentation`

### TODO-024: Publish Release Guidance

GitHub Issue: #19

Document the release process for PyInstaller onedir bundles.

Acceptance criteria:

- Documents Windows 11, current Apple Silicon macOS, and Ubuntu release targets.
- Documents per-platform PyInstaller build commands.
- Documents bundled data layout.
- Documents how bundled native tools are produced and staged.
- Documents how packaged dependencies differ from source dependencies.
- Documents release verification steps before publishing.

Suggested labels: `release`, `documentation`, `packaging`

### TODO-025: Decompose Legacy Oversized Python Modules and Classes

GitHub Issue: #29

Reduce the module/class size warnings now surfaced by the gzkit-parity
quality-check code-quality audit.

Acceptance criteria:

- Breaks the current warning set into independently mergeable decomposition
  issues or resolves a first representative module/class.
- Replaces broad size waivers with narrower waivers as modules are split.
- Keeps quality-check green throughout; no unwaived hard-cap module or
  class-size blocks.
- Adds focused tests for any extracted behavior.

Suggested labels: `quality`, `architecture`, `refactor`
