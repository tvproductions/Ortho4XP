---
name: updating-bundled-tools
description: Use when bundled tools in Utils/ need version checks, updates, or staging across Windows/macOS/Linux platforms
---

# Updating Bundled Tools

## Overview

Ortho4XP bundles platform-specific executables and libraries under `Utils/<platform>/`. These tools are checked into the repo and must be updated when upstream releases new versions. This skill documents where each tool comes from, how to check its version, and how to stage an update.

## Tool Manifest

### X-Plane SDK Tools (DSFTool, DDSTool)

| Property | Value |
|----------|-------|
| **Source** | https://developer.x-plane.com/tools/xptools/ |
| **Download (Win)** | `https://files.x-plane.com/public/xptools/xptools_win_24-5.zip` |
| **Download (Mac)** | `https://files.x-plane.com/public/xptools/xptools_mac_24-5.zip` |
| **Download (Lin)** | `https://files.x-plane.com/public/xptools/xptools_lin_24-5.zip` |
| **Current version** | 24-5 (check page for newer) |
| **Contents** | `DSFTool`, `DDSTool` (Win/Mac/Lin) |
| **Staging (Win)** | Extract `DSFTool.exe` to `Utils/win/` |
| **Staging (Mac)** | Extract `DSFTool` + `DDSTool` to `Utils/mac/` |
| **Staging (Lin)** | Extract `DSFTool` to `Utils/lin/` |
| **Verify** | `DSFTool --help` (Mac/Lin) / `DSFTool.exe --help` (Win) — non-zero exit but prints usage |

Version URLs follow the pattern `xptools_<platform>_YY-N.zip`. Check the page for the latest release number.

### NVIDIA Texture Tools (nvcompress) — Windows & Linux only

| Property | Value |
|----------|-------|
| **Source** | https://developer.nvidia.com/gpu-accelerated-texture-compression |
| **Download (Win)** | NVIDIA Texture Tools Exporter (includes `nvcompress.exe`) |
| **Download (Lin)** | NVTT 3 SDK for Linux x86_64 (includes `nvcompress` + `libnvtt.so`) |
| **Current version** | 3.2.5 (check page for updates) |
| **Staging (Win)** | Copy `nvcompress.exe` to `Utils/win/nvcompress/` |
| **Staging (Lin)** | Copy `nvcompress` + `libnvtt.so.*` to `Utils/lin/` |
| **Verify** | Run `nvcompress` — prints version and usage to stderr |

Requires NVIDIA developer account to download. macOS has no NVIDIA-provided NVTT binary; use DDSTool (X-Plane SDK) on macOS.

**Command reference** (these are the caps-max flags we use):
```
nvcompress -bc1 -highest -mipfilter kaiser -alpha_dithering <input> <output>
nvcompress -bc3 -highest -mipfilter kaiser -alpha_dithering -alpha <input> <output>
```

### Triangle4XP & triangle (self-built)

| Property | Value |
|----------|-------|
| **Source** | Built from source in `Utils/src/` |
| **Build system** | CMake with LLVM/Clang |
| **Build preset** | `llvm-release` |
| **Build command** | `cmake --preset llvm-release -S Utils && cmake --build Utils/build/llvm-release --target Triangle4XP && cmake --build Utils/build/llvm-release --target triangle` |
| **Staging (Win)** | Copy `Triangle4XP.exe` + `triangle.exe` to `Utils/win/` |
| **Staging (Mac)** | Copy `Triangle4XP` + `triangle` to `Utils/mac/` |
| **Staging (Lin)** | Copy `Triangle4XP` + `triangle` to `Utils/lin/` |
| **Verify** | Run `Triangle4XP` (prints usage) and `triangle -h` |

### 7-Zip (7z/7zz)

| Property | Value |
|----------|-------|
| **Source** | https://7-zip.org/ |
| **Current version** | Check 7-zip.org for latest |
| **Staging (Win)** | `7z.exe`, `7z.dll` from 7-Zip extra package → `Utils/win/` |
| **Staging (Mac)** | `7zz` from 7-Zip macOS build → `Utils/mac/7zz` |
| **Verify** | `7z` (Win) or `7zz` (Mac) — prints version and command list |

### moulinette

| Property | Value |
|----------|-------|
| **Source** | Bundled in Ortho4XP repo; source unknown |
| **Staging (Win)** | `moulinette.exe` → `Utils/win/` |
| **Staging (Lin)** | `moulinette` → `Utils/lin/` |
| **Verify** | Run with `--help` |

No known upstream source. If moulinette source is located, it should be transitioned to a CMake build like Triangle4XP.

## General Update Workflow

### For each tool being updated:

1. **Check upstream** — visit the source URL and compare versions
2. **Download** — get the release archive (automated where direct URLs exist; manual where login/EULA required)
3. **Verify integrity** — check checksum if published; otherwise run verification command
4. **Stage binaries** — copy to `Utils/<platform>/<tool>` following the manifest above
5. **Remove obsolete files** — delete old versions if filenames changed
6. **Update version** — update the version field in this manifest if the version table changes
7. **Verify on target platform** — run the verify command for each staged binary
8. **Commit** — commit with message format: `tools: update <tool> to <version> for <platform>`

### Automated check shortcut

For tools with direct download URLs, fetch the page and grep for version indicators:

```
# Check X-Plane tools version (bash/Unix):
curl -s https://developer.x-plane.com/tools/xptools/ | grep -oE "xptools_win_[0-9-]+"

# Check X-Plane tools version (PowerShell):
(Invoke-WebRequest -Uri https://developer.x-plane.com/tools/xptools/).Content -match "xptools_win_[\d-]+"

# Check nvcompress version (local, Win):
.\Utils\win\nvcompress\nvcompress.exe 2>&1 | Select-Object -First 1

# Check nvcompress version (local, Lin):
./Utils/lin/nvcompress 2>&1 | head -1
```

## Common Mistakes

- **Mixing platform binaries**: macOS binaries are Mach-O, Linux are ELF, Windows are PE. Verify with `file` on Unix or check extension.
- **Missing shared libraries**: nvcompress on Linux needs `libnvtt.so.*` in the same directory. On Windows it needs `nvtt*.dll`. macOS nvcompress is statically linked (no shared lib).
- **Version number assumptions**: X-Plane tools version format `YY-N` doesn't always increment — check the release date on the page.
- **macOS code signing**: Copied macOS binaries may need `xattr -cr` to remove quarantine attributes.
