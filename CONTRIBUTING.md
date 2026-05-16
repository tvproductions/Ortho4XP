# Contributing

This fork is being modernized around Python 3.13+, `uv`, `unittest`, Ruff, ty, and LLVM/Clang for native utilities. Keep changes portable across Windows, current Apple Silicon macOS, and Ubuntu unless a platform-specific limitation is documented.

## Development Environment

Install Python 3.13 and `uv`, then sync the project environment from the repository root:

```bash
uv sync --dev
```

The committed `.python-version`, `pyproject.toml`, and `uv.lock` are the source of truth for local development. Do not add `requirements.txt`, manual virtual environment instructions, or alternate dependency managers for normal development.

## Platform Notes

Windows 11 is the primary development environment for this fork. The repository includes Windows Python wheels for GDAL and scikit-fmm in `Utils/win`, and `uv sync --dev` uses those local wheels on Windows. The current GitHub Actions Windows job runs on an x64 runner because the hosted Windows 11 runner is arm64 while these wheels are `win_amd64`.

On Apple Silicon macOS, install Homebrew first. The setup script installs Python 3.13, Tk, SpatialIndex, p7zip, PROJ, GDAL, and `uv`:

```bash
./install_mac.sh
```

On Ubuntu, install system packages for Tk, GDAL, SpatialIndex, CMake, Ninja, LLVM/Clang, clang-tidy, clang-format, and lld before running `uv sync --dev`. The CI workflow is the reference for package names on Ubuntu 24.04.

## Validation

Run the deterministic Python test suite with:

```bash
uv run python -m unittest discover -s tests
```

Run linting and the current type-check baseline with:

```bash
uv run ruff check Ortho4XP.py src
uv run ty check tests src/O4_Geo_Utils.py src/O4_File_Names.py
```

When changing Python files, also run `ty` on the changed files and keep tests under `tests/` using standard-library `unittest`.

## Native Utility Build

Build `Triangle4XP` with LLVM/Clang through the CMake preset:

```bash
clang-tidy --verify-config
cmake --preset llvm-release -S Utils
cmake --build Utils/build/llvm-release --target Triangle4XP
```

Use `.clang-format` and `.clang-tidy` for changed native C/C++ code. Build output belongs under `Utils/build/...`. Copy rebuilt binaries into `Utils/win`, `Utils/mac`, or `Utils/lin` only when intentionally refreshing bundled release tools.

## Local Generated Data

Generated scenery, caches, and local runtime files must stay out of commits. Common local-only paths include:

- `OSM_data/`
- `Masks/`
- `Orthophotos/`
- `Elevation_data/`
- `Geotiffs/`
- `Tiles/`
- `tmp/`
- `yOrtho4XP_Overlays/`
- `Ortho4XP.cfg`
- `.venv/`
- `Utils/build/`

Provider definitions, filters, patches, previews, extents, license files, and bundled utility assets are source assets unless they are explicitly generated.
