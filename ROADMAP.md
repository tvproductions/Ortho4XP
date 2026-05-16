# Roadmap

This roadmap captures suggested improvements for the Ortho4XP codebase. Ortho4XP is a scenery generation tool for the X-Plane flight simulator that builds base mesh, DSF scenery, masks, overlays, and orthophoto texture layers from external elevation, vector, OSM, and imagery-provider data.

## Goals

- Improve reliability across Windows, macOS, and Linux.
- Make packaging and dependency management easier to maintain.
- Add automated validation for core geospatial, imagery, configuration, and native-tool workflows.
- Improve diagnostics for users when external tools, imagery providers, or network services fail.
- Reduce security and maintainability risks in provider parsing and broad exception handling.

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

Introduce `pytest` and a `tests/` directory. Focus first on deterministic logic that does not require network access, X-Plane, GDAL binaries, or imagery providers.

Good first test targets:

- Coordinate conversion helpers in `src/O4_Geo_Utils.py`.
- File/path generation in `src/O4_File_Names.py`.
- Provider parsing in `src/O4_Imagery_Utils.py`.
- Configuration loading and saving in `src/O4_Config_Utils.py`.
- Queue/retry behavior in `src/O4_Tile_Utils.py`.

### 3. Add `pyproject.toml`

Add modern Python project tooling configuration for:

- Supported Python version range.
- Ruff linting/formatting.
- Pytest configuration.
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

## Medium-Term Improvements

### 6. Centralize subprocess execution

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

### 7. Centralize logging

The codebase currently mixes `print`, `UI.vprint`, `UI.lvprint`, `UI.logprint`, and silent exception handling.

A logging abstraction should support:

- CLI output.
- GUI console output.
- Log files.
- Verbosity levels.
- Structured error reporting for batch builds.

### 8. Add platform-specific CI jobs

After the first Linux workflow is stable, add Windows and macOS CI to validate:

- Dependency installation.
- Native utility availability or buildability.
- Startup scripts.
- PyInstaller-related imports and paths.
- GDAL-related installation assumptions.

### 9. Improve dependency management

The project pins platform-specific dependencies in `requirements.txt`, including GDAL variants. Add documentation and validation around:

- Supported Python versions.
- Platform-specific GDAL installation requirements.
- Known-good dependency combinations.
- Whether packaged releases use the same dependencies as source installs.

Consider separate constraint files per platform if one file becomes difficult to maintain.

### 10. Add smoke tests for application startup

Add lightweight tests that verify:

- `Ortho4XP.py` can be imported.
- Core modules import without side effects that fail in CI.
- Provider dictionaries can be initialized.
- CLI argument validation works.
- Required resource directories are detected cleanly.

## Larger Refactors

### 11. Separate GUI, CLI, and core build logic

The current entry point and modules mix GUI state, CLI behavior, global flags, and build orchestration.

Long-term improvements:

- Keep GUI code in a presentation layer.
- Keep CLI parsing in a CLI layer.
- Move tile build steps into a core library/API.
- Make build steps callable and testable independently.

### 12. Reduce global mutable state

Several modules rely on global state, such as provider dictionaries, UI flags, red/working flags, and imagery state.

Refactor gradually toward:

- Explicit context/config objects.
- Build state objects.
- Dependency injection for paths, logging, and network clients.
- Structured build results instead of global flags.

### 13. Make import-time behavior minimal

Some modules perform platform detection, path setup, provider loading, or user-visible printing during import.

Move import-time side effects into explicit initialization functions so that:

- Tests can import modules safely.
- Packaging behavior is easier to reason about.
- Errors can be reported through consistent logging.

### 14. Modernize provider definitions

Provider files are central to imagery handling. Improvements could include:

- Safer parsing.
- Schema validation.
- Better error messages for invalid provider files.
- Optional migration to TOML, JSON, or YAML.
- Tests for known provider definitions.

### 15. Improve error reporting for network and imagery failures

Imagery downloads depend on external servers and can fail due to 403, 404, 5xx, throttling, corrupt images, or provider changes.

Improve reporting by:

- Tracking failed provider, URL type, HTTP status, and retry count.
- Avoiding overly verbose full URL output unless debug logging is enabled.
- Summarizing failed textures at the end of a tile or batch build.
- Making retry limits configurable and documented.

## Repository Health

### 16. Add or verify project metadata

Recommended files and settings:

- `LICENSE`
- `CONTRIBUTING.md`
- `SECURITY.md`
- Issue templates, if issues are enabled in the future.
- Pull request template.
- GitHub topics such as `x-plane`, `scenery`, `orthophoto`, `gis`, and `flight-simulator`.

### 17. Document development setup

Add a development section to `README.md` or a dedicated `CONTRIBUTING.md` covering:

- Python version.
- Virtual environment setup.
- Installing dependencies.
- Building native utilities.
- Running tests.
- Running lint/format checks.
- Running the app from source.

### 18. Publish release guidance

If this fork distributes packaged builds, document:

- How to build releases.
- Which platforms are supported.
- How bundled native tools are produced.
- How packaged dependencies differ from source dependencies.
- How to verify a release before publishing.

## Suggested First Pull Requests

1. Add a basic GitHub Actions CI workflow for Linux.
2. Add `pyproject.toml` with Ruff and Pytest configuration.
3. Add initial unit tests for path helpers, provider parsing, and coordinate conversions.
4. Replace `eval` in provider parsing with safe parsing.
5. Improve subprocess error messages for mesh generation and texture conversion.
6. Replace the most common bare `except:` blocks in high-traffic modules.
7. Add development setup documentation.

## Success Metrics

The roadmap is working if:

- Pull requests receive automated feedback before merge.
- New contributors can set up a development environment from documentation alone.
- Common failures produce actionable error messages.
- Provider parsing failures identify the exact file and field.
- Core utility functions have unit test coverage.
- Native utility build or availability is validated automatically.
- Cross-platform behavior is checked regularly in CI.
