# Roadmap

This roadmap captures suggested improvements for the Ortho4XP codebase. Ortho4XP is a scenery generation tool for the X-Plane flight simulator that builds base mesh, DSF scenery, masks, overlays, and orthophoto texture layers from external elevation, vector, OSM, and imagery-provider data.

## Goals

- Improve reliability across Windows, macOS, and Linux.
- Make packaging and dependency management easier to maintain.
- Add automated validation for core geospatial, imagery, configuration, and native-tool workflows.
- Improve diagnostics for users when external tools, imagery providers, or network services fail.
- Document and improve the GIS/raster/imagery pipeline so GDAL, masks,
  projection handling, color processing, and texture compression decisions are
  explicit and testable.
- Evolve from an orthophoto tile baker into an XP12-native scenery
  compiler/workbench for base mesh, imagery, raster data, DSF preservation,
  package validation, and future GIS-derived companion layers.
- Reduce security and maintainability risks in provider parsing and broad exception handling.
- **XP12 Engine Exploitation:** Native integration with physical 3D bathymetry, dynamic seasons, micro-soundscapes, and advanced lighting shaders by discarding legacy backward-compatibility paths.
- **Hardware Maxxing:** Decouple from legacy single-threaded x86 binaries; route texture processing and geometry math through modern multi-core CPUs and discrete GPU hardware platforms (CUDA/Vulkan).

## Quick Wins

### 1. Add continuous integration

Add GitHub Actions workflows that run on pull requests and pushes.

Initial checks should include:

- Python syntax/import smoke tests.
- Dependency installation validation.
- Basic CLI startup validation.
- C utility build validation for `Triangle4XP`.
- Linting with Ruff.

Start with Linux CI, then expand to Windows and macOS because Ortho4XP ships platform-specific tools and scripts.

### 2. Add a test suite

Introduce a `unittest`-based `tests/` directory. Focus first on deterministic logic that does not require network access, X-Plane, GDAL binaries, or imagery providers.

Good first test targets:

- Coordinate conversion helpers in `src/O4_Geo_Utils.py`.
- File/path generation in `src/O4_File_Names.py`.
- Provider parsing in `src/O4_Imagery_Utils.py`.
- Configuration loading and saving in `src/O4_Config_Utils.py`.
- Queue/retry behavior in `src/O4_Tile_Utils.py`.

### 3. Add `pyproject.toml`

Add modern Python project tooling configuration for:

- Supported Python 3.13+ version range.
- `uv` dependency and environment management.
- Ruff linting/formatting.
- `ty` type checking.
- `unittest` discovery.
- Optional development dependencies.

This does not require fully packaging the application immediately, but it gives contributors a standard development entry point.

### 4. Replace unsafe `eval` usage

Provider parsing currently uses `eval` for values such as provider headers and booleans. Replace this with safer parsing.

Recommended options:

- Use `ast.literal_eval` for Python-literal compatibility.
- Prefer JSON/TOML-style provider metadata in the long term.
- Validate parsed values explicitly, especially headers and booleans.

### 5. Improve broad exception handling

Replace bare `except:` blocks with specific exceptions where possible.

Examples:

- Use `except OSError as exc:` for file operations.
- Use `except requests.RequestException as exc:` for network calls.
- Use `except ValueError as exc:` for parsing.
- Log exception details instead of silently ignoring them.

This will make user bug reports and support issues easier to diagnose.

### 6. Eliminate Legacy Mesh Fallbacks & Hardcode 3D Bathymetry
Legacy X-Plane 11 `water_tech` modes are removed from active configuration and rejected when found in existing config files. Continue by enforcing a bathymetry input contract for XP12 water tiles before DSF encoding. For TODO-014, XP12 Global Scenery raster extraction is the only implemented bathymetry provider; future custom or repo-owned bathymetry sources should plug into the same contract and must not bypass validation with mask heuristics. Once that boundary is proven, deeper mesh work can rewrite the core mesh path toward X-Plane 12 physical 3D waterbed vector meshes.

## Medium-Term Improvements

### 7. Centralize subprocess execution

Ortho4XP calls several external tools, including:

- `Triangle4XP`
- `triangle`
- `moulinette`
- `nvcompress`
- `DDSTool`
- `gdal_translate`
- `gdalwarp`
- `7z`

Create a shared subprocess helper that:

- Captures stdout and stderr.
- Logs command, return code, and a short error summary.
- Handles platform-specific environment setup.
- Returns structured success/failure information.

This would improve diagnostics for mesh generation, texture conversion, and packaging failures.

### 8. Centralize logging

Persistent logging now flows through `O4_UI_Utils` as JSONL in
`Ortho4XP.log.json`. Human-facing `print`, `UI.vprint`, and `UI.lvprint`
output remains readable in CLI and GUI contexts.

The remaining direction is to keep moving diagnostics into structured events:

- Preserve CLI and GUI console readability.
- Keep verbosity levels tied to human-visible output.
- Add structured context to batch-build, imagery, and network failures.

### 9. Add platform-specific CI jobs

After the first Linux workflow is stable, add Windows and macOS CI to validate:

- Dependency installation.
- Native utility availability or buildability.
- Startup scripts.
- PyInstaller-related imports and paths.
- GDAL-related installation assumptions.

### 10. Improve dependency management

The project pins platform-specific dependencies in `pyproject.toml` and `uv.lock`, including GDAL variants. Add documentation and validation around:

- Supported Python versions.
- Platform-specific GDAL installation requirements.
- Known-good dependency combinations.
- Whether packaged releases use the same dependencies as source installs.

Consider separate constraint files per platform if one file becomes difficult to maintain.

### 11. Add smoke tests for application startup

Add lightweight tests that verify:

- `Ortho4XP.py` can be imported.
- Core modules import without side effects that fail in CI.
- Provider dictionaries can be initialized.
- CLI argument validation works.
- Required resource directories are detected cleanly.

### 12. Native BC3 (DXT5) Coastal Alpha Texture Blending
Overhaul mask generation inside `src/O4_Mask_Utils.py` to completely eliminate harsh, opaque coastline imagery thresholds. Replace the legacy linear falloff equations within the distance field matrices (`distance_masks_too`) with a smooth, progressive logarithmic alpha gradient. Force the texture compilation pipeline to encode water boundary sheets strictly using BC3 (DXT5) texture compression profiles with explicit alpha channel preservation, allowing X-Plane 12's native subsurface light scattering and dynamic deep-water shader to blend fluidly over shallow reef or sandbar orthophotos.

## Larger Refactors

### 13. Separate GUI, CLI, and core build logic

The current entry point and modules mix GUI state, CLI behavior, global flags, and build orchestration.

Long-term improvements:

- Keep GUI code in a presentation layer.
- Keep CLI parsing in a CLI layer.
- Move tile build steps into a core library/API.
- Make build steps callable and testable independently.

### 14. Reduce global mutable state

Several modules rely on global state, such as provider dictionaries, UI flags, red/working flags, and imagery state.

Refactor gradually toward:

- Explicit context/config objects.
- Build state objects.
- Dependency injection for paths, logging, and network clients.
- Structured build results instead of global flags.

### 15. Make import-time behavior minimal

Some modules perform platform detection, path setup, provider loading, or user-visible printing during import.

Move import-time side effects into explicit initialization functions so that:

- Tests can import modules safely.
- Packaging behavior is easier to reason about.
- Errors can be reported through consistent logging.

### 16. Modernize provider definitions

Provider files are central to imagery handling. Improvements could include:

- Safer parsing.
- Schema validation.
- Better error messages for invalid provider files.
- Optional migration to TOML, JSON, or YAML.
- Tests for known provider definitions.

### 17. Improve error reporting for network and imagery failures

Imagery downloads depend on external servers and can fail due to 403, 404, 5xx, throttling, corrupt images, or provider changes.

Improve reporting by:

- Tracking failed provider, URL type, HTTP status, and retry count.
- Avoiding overly verbose full URL output unless debug logging is enabled.
- Summarizing failed textures at the end of a tile or batch build.
- Making retry limits configurable and documented.

### 18. Non-Destructive DSF Header Splicing (The Data Bridge)
Refactor Step 4 (`build_dsf`) inside `src/Ortho4XP_v140.py` or the Ypsos pipeline orchestrator to stop emitting sterile, featureless terrain arrays. Implement a programmatic Python `subprocess` loop that uses the X-Plane SDK `DSFTool` to disassemble the default global scenery `.dsf` for the active coordinates into a temporary text string pool. Build a strict token parser block to extract native X-Plane 12 data vectors—specifically `ATTR_season` multi-raster configurations, localized regional autogen vegetation rules, airport terminal acoustic layers (`sound`), and runway surface friction variables—and prepend/stitch them natively back into the head of the custom ortho `.dsf` string array right before final binary packing.

### 19. Automated sRGB Histogram & Color Normalization Pipeline
Neutralize the "patchwork quilt" effect caused by stitching adjacent textures from varying imagery providers or differing satellite capture angles. Integrate an image-processing correction loop using OpenCV (`cv2`) or Pillow directly into the tile retrieval worker pipeline inside `src/O4_Imagery_Utils.py`. The function must extract the mean luminance and RGB color distributions from the edge pixels of a previously processed tile quadrant and apply an automated sRGB gamma transformation curve to newly downloaded sheets, flattening extreme exposure steps and neutralizing color drift prior to `.dds` baking.

### 20. GIS/Raster/Imagery Technology Map

Harvest the project knowledge behind the geospatial and imagery toolchain before
adding more visual processing features. Document how `gdal_translate`,
`gdalwarp`, Pillow, NumPy, provider color filters, masks, GeoTIFF export, DDS
encoders, and XP12 DSF raster handling fit together. The audit should trace
provider imagery from download/cache through crop/warp, masking, static color
filters, optional sRGB normalization, GeoTIFF export, and DDS handoff.

Use the documentation to identify staged improvements rather than making broad
runtime changes in the first pass. Candidate follow-ups include explicit
resampling policy, GDAL VRT pipelines, nodata/alpha handling, compression-aware
image quality checks, sharpening, richer color correction, and a measured
decision on whether OpenCV, rasterio, or GDAL Python bindings add enough value
to justify their dependency cost.

### 21. XP12-Native Scenery Compiler/Workbench Strategy

Define the beyond-ortho direction for the fork. The goal is not to copy
third-party scenery packages or assets, but to understand the public techniques
behind modern XP12 scenery stacks: layered packages, OSM/building-footprint data
use, vegetation libraries, regionalization, sound/effect layers, VFR object
layers, optional orthos, and install/validation ergonomics.

Use that strategy to retire older assumptions where XP12 no longer needs them.
In particular, audit the legacy `zOrtho4XP_` naming and scenery-order model and
replace folder-name folklore with explicit package metadata, validation,
generated documentation, and compatibility checks. This project should own the
XP12-native terrain/scenery foundation: mesh generation, imagery/raster
processing, bathymetry, DSF metadata/header preservation, generated package
validation, dependency checks, and compatibility reporting.

### 22. GPU-Accelerated Texture Encoding Engine
Bypass legacy, single-threaded external CPU texturing binaries. Completely decouple texture tile sheet splitting and conversion paths inside `src/O4_Tile_Utils.py` from legacy single-threaded external executables (like serial `nvcompress` calls). Utilize Python's built-in `concurrent.futures` module to orchestrate massive parallel processing batches across host hardware threads, and implement direct hardware-accelerated wrapper configurations to offload the raw raster triangulation and format conversion tasks straight to discrete graphics processors (CUDA/Vulkan backends).

## Repository Health

### 23. Add or verify project metadata

Recommended files and settings:

- `LICENSE`
- `CONTRIBUTING.md`
- `SECURITY.md`
- Issue templates, if issues are enabled in the future.
- Pull request template.
- GitHub topics such as `x-plane`, `scenery`, `orthophoto`, `gis`, and `flight-simulator`.

### 24. Document development setup

Add a development section to `README.md` or a dedicated `CONTRIBUTING.md` covering:

- Python version.
- Virtual environment setup.
- Installing dependencies.
- Building native utilities.
- Running tests.
- Running lint/format checks.
- Running the app from source.

### 25. Publish release guidance

If this fork distributes packaged builds, document:

- How to build releases.
- Which platforms are supported.
- How bundled native tools are produced.
- How packaged dependencies differ from source dependencies.
- Release versioning policy, including the fork's switch to SemVer at `v1.0.0`.
- How to verify a release before publishing.

### 26. Full Standalone Decoupling (Breakaway Playbook)

In the event of upstream stagnation, completely sever backward compatibility ties. Purge all legacy UI widgets, deprecated X-Plane 11 formatting forks, and flat-water legacy codeblocks. Transition the core architecture to a headless, scriptable engine driven entirely by structured configuration files (JSON/TOML), allowing for automated, high-throughput batch tile compilation without graphical user interface overhead.

## Suggested First Pull Requests

1. Add a basic GitHub Actions CI workflow for Linux.
2. Add `pyproject.toml` with uv, Ruff, ty, and unittest configuration.
3. Add initial unit tests for path helpers, provider parsing, and coordinate conversions.
4. Replace `eval` in provider parsing with safe parsing.
5. Improve subprocess error messages for mesh generation and texture conversion.
6. Replace the most common bare `except:` blocks in high-traffic modules.
7. Add development setup documentation.
8. Require valid bathymetry inputs for physical XP12 water meshes.
9. Document the GIS/raster/imagery technology map before expanding sharpening,
   color correction, or GDAL pipeline behavior.
10. Define the XP12-native scenery compiler/workbench strategy before changing
    package naming, scenery-stack behavior, or beyond-ortho output scope.

## Success Metrics

The roadmap is working if:

- Pull requests receive automated feedback before merge.
- New contributors can set up a development environment from documentation alone.
- Common failures produce actionable error messages.
- Provider parsing failures identify the exact file and field.
- Core utility functions have unit test coverage.
- Native utility build or availability is validated automatically.
- Cross-platform behavior is checked regularly in CI.
- GIS/raster/imagery behavior is documented well enough that projection,
  resampling, masking, color, and compression changes can be reviewed against an
  explicit pipeline.
- XP12 scenery output is planned around explicit package metadata,
  compatibility checks, and native scenery features rather than legacy
  folder-name conventions alone.
- Pristine coastal transitions are generated natively with dynamic water shaders.
- High-fidelity ortho layers maintain native dynamic winter/spring seasonal shifts.
