# Release Process

This document describes how to build, verify, and publish Ortho4XP releases as PyInstaller onedir bundles for Windows 11, Apple Silicon macOS, and Ubuntu.

## Supported Release Targets

| Platform | Architecture | Runner | Bundle Format |
|----------|--------------|--------|---------------|
| Windows 11 | x64 (`win_amd64`) | Local or CI x64 | `dist/Ortho4XP/` directory |
| macOS (Apple Silicon) | arm64 | Local or CI `macos-15` | `dist/Ortho4XP/` directory |
| Ubuntu 24.04+ | x64 | Local or CI `ubuntu-24.04` | `dist/Ortho4XP/` directory |

Each platform produces a self-contained directory with the `Ortho4XP` executable, Python runtime, dependencies, and bundled data assets. Do not assume cross-packaging; build each target on its native platform.

## Versioning Policy

This fork uses Semantic Versioning (SemVer) starting at `v1.0.0`. The current `pyproject.toml` version (`1.4`) and `src/O4_Version.py` version (`1.40.13`) reflect legacy upstream numbering. The first fork release under SemVer will be `v1.0.0`.

Version locations:

- `pyproject.toml`: `version = "1.4"` (project metadata)
- `Utils/CMakeLists.txt`: `project(Ortho4XP VERSION 1.4 LANGUAGES C)` (native build)
- `src/O4_Version.py`: `version = "1.40.13"` (runtime display)

Update all three locations together when bumping versions. For SemVer:

- **MAJOR**: Incompatible API or scenery output changes.
- **MINOR**: Backward-compatible functionality or provider additions.
- **PATCH**: Backward-compatible bug fixes.

## Prerequisites

### All Platforms

- Python 3.13+
- `uv` for dependency management
- PyInstaller: `uv pip install pyinstaller` (dev dependency or ad hoc install)

### Windows

- LLVM/Clang for native builds (installed via `choco install llvm`)
- CMake and Ninja (`choco install cmake ninja`)
- Bundled wheels in `Utils/win/` for GDAL and scikit-fmm

### macOS (Apple Silicon)

- Homebrew: `brew install gdal llvm ninja spatialindex`
- Bundled wheels in `Utils/mac/` for NumPy (if needed)

### Ubuntu

- System packages: `sudo apt-get install clang clang-format clang-tidy cmake gdal-bin lld libgdal-dev libspatialindex-dev ninja-build python3-tk`

## Native Tool Production

Native C utilities are built with LLVM/Clang through CMake presets. Build artifacts stay in `Utils/build/...` and are copied into platform staging directories only when intentionally refreshing bundled release tools.

### Build Triangle4XP

```bash
clang-tidy --verify-config
cmake --preset llvm-release -S Utils
cmake --build Utils/build/llvm-release --target Triangle4XP
```

### Stage Bundled Tools

After building, copy executables into the platform-specific staging directory:

**Windows:**
```powershell
Copy-Item Utils/build/llvm-release/Triangle4XP.exe Utils/win/
Copy-Item Utils/build/llvm-release/triangle.exe Utils/win/
```

**macOS:**
```bash
cp Utils/build/llvm-release/Triangle4XP Utils/mac/
cp Utils/build/llvm-release/triangle Utils/mac/
```

**Ubuntu:**
```bash
cp Utils/build/llvm-release/Triangle4XP Utils/lin/
cp Utils/build/llvm-release/triangle Utils/lin/
```

### Platform-Specific Bundled Tools

Each platform directory contains pre-built or third-party executables:

**`Utils/win/`:**
- `Triangle4XP.exe`, `triangle.exe` (CMake-built)
- `DSFTool.exe` (X-Plane SDK)
- `7z.exe`, `7z.dll`, `7-zip.dll` (7-Zip)
- `moulinette.exe`, `medit-2.3-win.exe` (mesh tools)
- `gdal-3.12.2-cp313-cp313-win_amd64.whl`, `scikit_fmm-2025.6.23-cp313-cp313-win_amd64.whl`

**`Utils/mac/`:**
- `Triangle4XP`, `triangle` (CMake-built, Universal or arm64)
- `DSFTool`, `DDSTool`, `nvcompress` (texture/mesh tools)
- `7zz` (7-Zip)
- `numpy-2.4.4-cp313-cp313-macosx_11_0_arm64.whl`

**`Utils/lin/`:**
- `Triangle4XP`, `triangle` (CMake-built)
- `DSFTool`, `nvcompress`, `moulinette`, `medit-2.3-linux` (texture/mesh tools)
- `libnvtt.so.30205` (NVIDIA Texture Tools library)

Refresh these only when updating tool versions or fixing platform-specific bugs.

## PyInstaller Build Commands

### Windows

```powershell
uv sync --dev
uv pip install pyinstaller
uv run pyinstaller Ortho4XP.spec
```

Output: `dist/Ortho4XP/`

### macOS

```bash
uv sync --dev
uv pip install pyinstaller
uv run pyinstaller Ortho4XP.spec
```

Output: `dist/Ortho4XP/`

### Ubuntu

```bash
uv sync --dev
uv pip install pyinstaller
uv run pyinstaller Ortho4XP.spec
```

Output: `dist/Ortho4XP/`

## Bundled Data Layout

The `Ortho4XP.spec` file bundles the following data directories into `Ortho4XP_Data/` inside the bundle:

```
dist/Ortho4XP/
├── Ortho4XP.exe (or Ortho4XP on macOS/Linux)
├── _internal/
│   ├── pyproj/proj_dir/share/proj/proj.db
│   └── (Python runtime, dependencies)
└── Ortho4XP_Data/
    ├── Utils/
    │   ├── win/ (Windows only)
    │   ├── mac/ (macOS only)
    │   ├── lin/ (Linux only)
    │   └── (shared assets)
    ├── Extents/
    ├── Filters/
    ├── Licence/
    ├── Patches/
    ├── Previews/
    ├── Providers/
    ├── community_server.txt
    └── overpass_servers.txt
```

### Platform-Specific Trimming

Before distribution, remove inapplicable utility folders:

**Windows release:**
```powershell
Remove-Item -Recurse dist/Ortho4XP/Ortho4XP_Data/Utils/mac
Remove-Item -Recurse dist/Ortho4XP/Ortho4XP_Data/Utils/lin
```

**macOS release:**
```bash
rm -rf dist/Ortho4XP/Ortho4XP_Data/Utils/win
rm -rf dist/Ortho4XP/Ortho4XP_Data/Utils/lin
```

**Ubuntu release:**
```bash
rm -rf dist/Ortho4XP/Ortho4XP_Data/Utils/win
rm -rf dist/Ortho4XP/Ortho4XP_Data/Utils/mac
```

### PROJ Database

The spec file resolves the system `proj.db` (version 5+) from OSGeo4W, Homebrew, or system packages and bundles it explicitly at `pyproj/proj_dir/share/proj/proj.db`. This prevents fallback to pyproj's outdated version 4 copy.

## Packaged vs. Source Dependencies

### Source Development

`uv sync --dev` installs dependencies from `pyproject.toml` and `uv.lock`. On Windows, local wheels in `Utils/win/` are used for GDAL and scikit-fmm:

```toml
[tool.uv.sources]
gdal = [
  { path = "Utils/win/gdal-3.12.2-cp313-cp313-win_amd64.whl", marker = "platform_system == 'Windows'" },
]
scikit-fmm = [
  { path = "Utils/win/scikit_fmm-2025.6.23-cp313-cp313-win_amd64.whl", marker = "platform_system == 'Windows'" },
]
```

### Packaged Release

PyInstaller bundles the Python interpreter, all dependencies from the active `uv` environment, and the application code into a self-contained directory. Users do not need Python, `uv`, or system packages installed. Bundled dependencies match the source `uv.lock` at build time.

Platform-specific GDAL wheels ensure the bundled GDAL version matches the system GDAL assumptions (3.12.2 on Windows, 3.12.3 on macOS, 3.9.0 on Linux).

## Release Verification

Before publishing a release, verify the bundle on the target platform:

### 1. Build the Bundle

```bash
uv sync --dev
uv pip install pyinstaller
uv run pyinstaller Ortho4XP.spec
```

### 2. Trim Platform Utilities

Remove inapplicable `Utils/{win,mac,lin}` directories as documented above.

### 3. Smoke Test CLI

```bash
./dist/Ortho4XP/Ortho4XP --help
./dist/Ortho4XP/Ortho4XP validate-job tests/fixtures/build_job_minimal.toml
```

### 4. Smoke Test GUI (Windows/macOS)

```bash
./dist/Ortho4XP/Ortho4XP
```

Verify the GUI opens without errors.

### 5. Verify Native Tools

Build a test tile or verify that `Triangle4XP` and `DSFTool` are present and executable in the bundled `Ortho4XP_Data/Utils/{win,mac,lin}/` directory.

### 6. Run Unit Tests (Optional)

If the bundle includes a test runner or you have a source checkout:

```bash
uv run python -m unittest discover -s tests
```

### 7. Check Bundle Size

Verify the bundle size is reasonable (typically 200-400 MB depending on platform and bundled tools).

### 8. Test on Clean System

Copy the bundle to a clean system without Python, `uv`, or development tools installed. Verify it runs without missing dependencies.

## Publishing Releases

### GitHub Releases

1. Tag the release: `git tag v1.0.0`
2. Push the tag: `git push origin v1.0.0`
3. Create a GitHub Release from the tag.
4. Attach platform-specific archives:
   - `Ortho4XP-v1.0.0-win-x64.zip` (Windows)
   - `Ortho4XP-v1.0.0-mac-arm64.zip` (macOS)
   - `Ortho4XP-v1.0.0-linux-x64.tar.gz` (Ubuntu)

### Archive Creation

**Windows:**
```powershell
Compress-Archive -Path dist/Ortho4XP -DestinationPath Ortho4XP-v1.0.0-win-x64.zip
```

**macOS/Linux:**
```bash
cd dist && tar -czf ../Ortho4XP-v1.0.0-mac-arm64.tar.gz Ortho4XP
```

### Release Notes

Include:

- Version number and date
- Summary of changes since the previous release
- Platform-specific notes (e.g., macOS Gatekeeper, Windows Defender SmartScreen)
- Known issues or breaking changes
- Link to the forum or issue tracker for support

## Troubleshooting

### PyInstaller Warnings

- **Missing hidden imports**: Add to `hiddenimports` in `Ortho4XP.spec`. The spec already includes `collect_submodules('PIL')`.
- **Missing data files**: Add to `datas` in `Ortho4XP.spec`.
- **proj.db not found**: Verify `projinfo --searchpaths` returns a valid path, or manually set `system_proj_dir` in the spec.

### Platform-Specific Issues

- **Windows**: Ensure LLVM and CMake are in `PATH` before building native tools.
- **macOS**: Gatekeeper may quarantine the bundle. Users can right-click and select "Open" or run `xattr -cr dist/Ortho4XP`.
- **Linux**: Ensure `libgdal.so` and `libspatialindex.so` are available on the target system if not fully bundled.

### Bundle Fails to Start

- Check `Ortho4XP.log.json` in the bundle directory for structured error logs.
- Run from a terminal to see stdout/stderr output.
- Verify all required data directories exist in `Ortho4XP_Data/`.

## Continuous Integration

The `.github/workflows/ci.yml` workflow runs on every push and pull request. It validates:

- Python syntax and imports
- Unit tests
- Ruff linting and ty type checks
- Native `Triangle4XP` build with LLVM/Clang

CI does not currently build PyInstaller bundles. Add a release workflow if automated bundle builds are needed.

## Future Improvements

- Add a GitHub Actions workflow for automated PyInstaller builds on tags.
- Sign macOS bundles with a Developer ID certificate.
- Add Windows code signing for SmartScreen reputation.
- Automate platform-specific utility trimming in the spec or a post-build script.
- Consider UPX compression for smaller bundle size (already enabled in the spec).
