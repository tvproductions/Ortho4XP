# Repository Guidelines

## Project Structure & Module Organization

`Ortho4XP.py` is the launcher. Core Python modules live in `src/` and follow the existing `O4_*` module naming pattern. Unit tests live in `tests/` and use standard-library `unittest` only. Native C utility sources and CMake files live in `Utils/`; bundled platform tools are staged in `Utils/win`, `Utils/mac`, and `Utils/lin`. Provider and asset data live in `Providers/`, `Filters/`, `Extents/`, `Patches/`, `Previews/`, and `Licence/`.

## Modern Toolchain

Windows 11 is the primary development environment for now. Keep choices portable to current Apple Silicon macOS and Ubuntu. Python 3.13+ is required; `.python-version` pins local `uv` environments to Python 3.13. `uv.lock` is committed and authoritative.

Use:

- `uv sync --dev`
- `uv run python -m unittest discover -s tests`
- `uv run ruff check Ortho4XP.py src`
- `uv run ruff format .`
- `uv run ty check <changed-python-files>`

Run `ty` on changed Python files and expand the checked baseline as files are modernized.

## Native Builds

Native C utilities should use LLVM/Clang through the CMake presets for a uniform Windows/macOS/Linux posture. Any LLVM install is acceptable if CMake can find `clang`, `llvm-rc` on Windows, and lld.

Build `Triangle4XP` with:

```bash
clang-tidy --verify-config
cmake --preset llvm-release -S Utils
cmake --build Utils/build/llvm-release --target Triangle4XP
```

Use `.clang-format` and `.clang-tidy` for changed native C/C++ code. The project hygiene script checks changed native lines to avoid reformatting the legacy Triangle baseline all at once.

Build artifacts stay in `Utils/build/...`. Copy into `Utils/win`, `Utils/mac`, or `Utils/lin` only when intentionally refreshing bundled release tools.

## Testing Rules

Use `unittest` only. Name files `tests/test_*.py` and classes `*Tests`. Keep tests deterministic and independent of network access, X-Plane installs, GDAL command-line tools, or imagery providers. Reuse `tests/_path.py` for import-path setup.

## Generated Data

Generated scenery/cache data is local-only and must not be committed: `OSM_data/`, `Masks/`, `Orthophotos/`, `Elevation_data/`, `Geotiffs/`, `Tiles/`, `tmp/`, and `yOrtho4XP_Overlays/`. Provider definitions, filters, patches, previews, and bundled utilities are source assets unless explicitly generated.

## Workflow & Priorities

Work on `master` by default for this fork. Use short-lived branches only for risky, experimental, or externally reviewed changes. Keep commits scoped and use concise imperative messages.

Use `TODO.md` as the actionable queue. Use `ROADMAP.md` for direction and rationale. If TODO ordering blocks practical implementation, reorder or phase `TODO.md` before proceeding so the next item is genuinely executable.

## Releases

Releases are PyInstaller onedir bundles built per target OS/architecture; do not assume cross-packaging. Target Windows 11, current Apple Silicon macOS, and Ubuntu. Package data should include `Utils`, `Extents`, `Filters`, `Licence`, `Patches`, `Previews`, `Providers`, and `community_server.txt`; trim platform-inapplicable utility folders before distribution.
