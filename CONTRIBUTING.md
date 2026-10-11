# Contributing

This fork uses Python 3.14.8, `uv`, `unittest`, Ruff, ty, and LLVM/Clang for native utilities. Keep changes portable across Windows, current Apple Silicon macOS, and Ubuntu unless a platform-specific limitation is documented.

## Development Environment

Install Python 3.14.8 and `uv`, then sync the project environment from the repository root:

```bash
uv sync --dev
```

The committed `.python-version`, `pyproject.toml`, and `uv.lock` are the source of truth for local development. Do not add `requirements.txt`, manual virtual environment instructions, or alternate dependency managers for normal development.

## Platform Notes

Windows 11 is the primary development environment for this fork. The repository includes CPython 3.14 Windows wheels for GDAL and scikit-fmm in `Utils/win`, and `uv sync --dev` uses those local wheels on Windows. The scikit-fmm wheel was built from the released 2025.6.23 source with Visual Studio C++ on Python 3.14.8 and passed all 374 upstream tests. The current GitHub Actions Windows job runs on an x64 runner because the hosted Windows 11 runner is arm64 while these wheels are `win_amd64`.

On Apple Silicon macOS, install Homebrew first. The setup script installs Python 3.14, Tk, SpatialIndex, p7zip, PROJ, GDAL, and `uv`. It uses Homebrew Python so Tk is available and checks that the native GDAL version matches the 3.13.3 Python bindings:

```bash
./install_mac.sh
```

On Ubuntu, the GDAL Python bindings require native GDAL 3.13.3. Ubuntu 24.04's default library does not match this pin. Install the development prerequisites below, then build the checksum-verified GDAL release into a user-owned prefix before syncing. The bootstrap keeps the default GDAL drivers whose development dependencies are available; it does not install Python bindings itself.

```bash
sudo apt-get update
sudo apt-get install -y clang clang-format clang-tidy cmake curl g++ lld \
  libcurl4-openssl-dev libexpat1-dev libgeos-dev libjpeg-dev libjson-c-dev \
  liblerc-dev liblzma-dev libpng-dev libproj-dev libspatialindex-dev \
  libsqlite3-dev libtiff-dev libwebp-dev libzstd-dev ninja-build python3-tk zlib1g-dev
bash scripts/install_linux_gdal.sh "$HOME/.local/ortho4xp-gdal"
export PATH="$HOME/.local/ortho4xp-gdal/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/.local/ortho4xp-gdal/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
uv sync --dev
```

Use an interpreter with Tk support for the GUI. A uv-managed Python provides the headless CLI; distribution Tk packages alone do not add Tk to an unrelated interpreter. CI checks the matching source-build path on Ubuntu 24.04. Linux and macOS execution evidence must come from those platforms; a Windows pass does not verify them.

The macOS NumPy 2.5.4 CPython 3.14 Apple Silicon wheel is retained in `Utils/mac` as a source asset. Normal `uv` resolution uses the matching PyPI release.

Deeper maintenance tools are installed only when needed:

```bash
uv sync --dev --group hygiene
```

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
- `Ortho4XP.log.json`
- `.venv/`
- `Utils/build/`

Provider definitions, filters, patches, previews, extents, license files, and bundled utility assets are source assets unless they are explicitly generated.
