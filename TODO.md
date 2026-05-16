# TODO

Each TODO below is intended to become one GitHub Issue (GHI). Keep issue bodies scoped, actionable, and independently mergeable where possible.

## Quick Wins

### TODO-001: Add basic Linux continuous integration

Status: Done

Create a GitHub Actions workflow that runs on pull requests and pushes.

Acceptance criteria:

- Installs project dependencies on Linux.
- Runs Python syntax/import smoke checks.
- Runs basic CLI startup validation.
- Builds or validates `Triangle4XP` where feasible.
- Runs Ruff linting.

Suggested labels: `ci`, `quality`, `quick-win`

### TODO-002: Add initial unittest test suite

Status: Done

Introduce a `unittest`-based `tests/` directory focused on deterministic logic that does not require network access, X-Plane, GDAL binaries, or imagery providers.

Acceptance criteria:

- Adds a working test command.
- Adds first tests for selected coordinate conversion helpers in `src/O4_Geo_Utils.py`.
- Adds first tests for selected file/path helpers in `src/O4_File_Names.py`.
- Documents how to run tests locally.

Suggested labels: `tests`, `quality`, `quick-win`

### TODO-003: Add modern Python tooling configuration

Add `pyproject.toml` with baseline project tooling configuration.

Acceptance criteria:

- Defines supported Python version range.
- Configures Ruff linting and formatting.
- Configures unittest discovery defaults.
- Defines optional development dependencies if supported by the chosen toolchain.

Suggested labels: `tooling`, `dependencies`, `quick-win`

### TODO-004: Replace unsafe provider parsing eval usage

Replace `eval` usage in provider parsing with safer parsing and explicit validation.

Acceptance criteria:

- Replaces provider parsing `eval` calls with `ast.literal_eval` or another safe parser.
- Validates parsed header values and booleans.
- Adds tests for valid and invalid provider metadata.
- Invalid provider values produce actionable error messages.

Suggested labels: `security`, `providers`, `quick-win`

### TODO-005: Replace common bare exception handlers

Replace high-impact bare `except:` blocks with specific exception handling.

Acceptance criteria:

- Identifies the most common or highest-traffic bare exception handlers.
- Replaces file operation handlers with `OSError` or more specific exceptions.
- Replaces network handlers with `requests.RequestException` where applicable.
- Replaces parsing handlers with `ValueError` or more specific exceptions.
- Logs exception details instead of silently swallowing failures.

Suggested labels: `reliability`, `diagnostics`, `quick-win`

## Medium-Term Improvements

### TODO-006: Centralize subprocess execution

Create a shared helper for external tool execution.

Acceptance criteria:

- Supports tools such as `Triangle4XP`, `triangle`, `moulinette`, `nvcompress`, `DDSTool`, `gdal_translate`, `gdalwarp`, and `7z`.
- Captures stdout and stderr.
- Logs command, return code, and a short error summary.
- Handles platform-specific environment setup.
- Returns structured success/failure information.

Suggested labels: `subprocess`, `diagnostics`, `refactor`

### TODO-007: Centralize logging behavior

Introduce a logging abstraction that can replace scattered output paths over time.

Acceptance criteria:

- Supports CLI output.
- Supports GUI console output.
- Supports log files.
- Supports verbosity levels.
- Provides structured error reporting suitable for batch builds.

Suggested labels: `logging`, `diagnostics`, `refactor`

### TODO-008: Add Windows and macOS CI jobs

Extend CI beyond Linux once the first workflow is stable.

Acceptance criteria:

- Adds Windows CI for dependency installation and startup validation.
- Adds macOS CI for dependency installation and startup validation.
- Validates startup scripts where feasible.
- Checks native utility availability or buildability where feasible.
- Documents any platform limitations or skipped checks.

Suggested labels: `ci`, `windows`, `macos`

### TODO-009: Improve dependency management documentation and validation

Clarify platform-specific dependency requirements, especially GDAL.

Acceptance criteria:

- Documents supported Python versions.
- Documents platform-specific GDAL installation requirements.
- Captures known-good dependency combinations.
- Clarifies packaged release dependencies versus source install dependencies.
- Evaluates whether separate platform constraint files are needed.

Suggested labels: `dependencies`, `documentation`, `platforms`

### TODO-010: Add application startup smoke tests

Add lightweight checks for import and startup behavior.

Acceptance criteria:

- Verifies `Ortho4XP.py` can be imported or loaded safely in test context.
- Verifies core modules import without CI-breaking side effects.
- Verifies provider dictionaries can be initialized.
- Verifies CLI argument validation behavior.
- Verifies required resource directories are detected cleanly.

Suggested labels: `tests`, `startup`, `quality`

## Larger Refactors

### TODO-011: Separate GUI, CLI, and core build logic

Begin separating presentation, command-line parsing, and build orchestration.

Acceptance criteria:

- Identifies current GUI, CLI, and core build responsibilities.
- Proposes a staged migration path.
- Moves one small build step behind a callable core API.
- Adds tests for the extracted behavior.

Suggested labels: `architecture`, `refactor`, `long-term`

### TODO-012: Reduce global mutable state

Gradually replace global state with explicit context and result objects.

Acceptance criteria:

- Identifies major global state used by provider dictionaries, UI flags, red/working flags, and imagery state.
- Introduces a small context/config object for one workflow.
- Avoids broad rewrites in the first issue.
- Adds tests or smoke checks for the migrated path.

Suggested labels: `architecture`, `state`, `refactor`

### TODO-013: Minimize import-time side effects

Move side effects out of module import paths and into explicit initialization functions.

Acceptance criteria:

- Identifies modules with platform detection, path setup, provider loading, or printing during import.
- Extracts one side-effecting import path into an explicit initializer.
- Ensures tests can import the changed module safely.
- Routes errors through the shared logging path where available.

Suggested labels: `imports`, `tests`, `refactor`

### TODO-014: Modernize provider definitions

Improve provider metadata safety, validation, and diagnostics.

Acceptance criteria:

- Defines a schema for provider definitions.
- Adds validation for known provider files.
- Improves error messages for invalid provider files.
- Evaluates TOML, JSON, YAML, or another safer provider format.
- Adds tests for known provider definitions.

Suggested labels: `providers`, `schema`, `reliability`

### TODO-015: Improve network and imagery failure reporting

Make imagery download failures easier to diagnose without excessive noise.

Acceptance criteria:

- Tracks failed provider, URL type, HTTP status, and retry count.
- Avoids full URL output unless debug logging is enabled.
- Summarizes failed textures at the end of a tile or batch build.
- Makes retry limits configurable and documented.
- Adds tests for summary/reporting behavior where feasible.

Suggested labels: `imagery`, `network`, `diagnostics`

## Repository Health

### TODO-016: Add or verify repository metadata

Add standard repository metadata and community files.

Acceptance criteria:

- Verifies current license state and adds or updates `LICENSE` if appropriate.
- Adds `CONTRIBUTING.md`.
- Adds `SECURITY.md`.
- Adds issue templates if issues are enabled.
- Adds a pull request template.
- Recommends GitHub topics such as `x-plane`, `scenery`, `orthophoto`, `gis`, and `flight-simulator`.

Suggested labels: `repository-health`, `documentation`

### TODO-017: Document development setup

Add contributor setup documentation.

Acceptance criteria:

- Documents Python version requirements.
- Documents virtual environment setup.
- Documents dependency installation.
- Documents native utility build steps.
- Documents how to run tests.
- Documents how to run lint and format checks.
- Documents how to run the app from source.

Suggested labels: `documentation`, `onboarding`, `development`

### TODO-018: Publish release guidance

Document the release process if this fork distributes packaged builds.

Acceptance criteria:

- Documents how to build releases.
- Documents supported platforms.
- Documents how bundled native tools are produced.
- Documents how packaged dependencies differ from source dependencies.
- Documents how to verify a release before publishing.

Suggested labels: `release`, `documentation`, `packaging`

## Suggested First Issues

1. TODO-001: Add basic Linux continuous integration.
2. TODO-003: Add modern Python tooling configuration.
3. TODO-002: Add initial unittest test suite.
4. TODO-004: Replace unsafe provider parsing eval usage.
5. TODO-006: Centralize subprocess execution.
6. TODO-005: Replace common bare exception handlers.
7. TODO-017: Document development setup.
