# XP12-Native Scenery Compiler/Workbench Strategy — Phase 2: Naming, Layout & Metadata

Date: 2026-06-13
Issue: TODO-027 / GHI #31 (Phase 2)
Previous: docs/superpowers/specs/2026-06-13-xp12-native-scenery-compiler-audit.md

## 1. Purpose & Scope

This document defines the future naming convention, package layout, and package
metadata schema for Ortho4XP-generated scenery packages. It replaces the legacy
`zOrtho4XP_` / `yOrtho4XP_` prefix conventions with a configurable, descriptive,
metadata-rich scheme designed for XP12-native scenery compilation.

Changes proposed here affect the generated package directory names and the
contents of each package (adding metadata files). No DSF format changes, no
texture format changes, and no changes to generated scenery output in this
phase.

## 2. Default Naming Convention

### 2.1 Mesh/Ortho Tile Packages

**Default format:**
```
Ortho4XP_Mesh_+43-079
```

Components:
- `Ortho4XP` — configurable prefix (default: `Ortho4XP_`)
- `Mesh` — purpose token (configurable, default `Mesh`)
- `+43-079` — spatial location in `short_latlon` format (configurable)

### 2.2 Overlay Packages

For per-tile overlay packages (replacing the monolithic `yOrtho4XP_Overlays`):

**Default format:**
```
Ortho4XP_Overlay_+43-079
```

For regional/grouped overlay packages (future option):
```
Ortho4XP_Overlay_Europe
```

### 2.3 Monolithic Overlay Package (Transitional)

A single monolithic overlay package may still be useful for users who do not
use X-World or other regional overlay packages. Its naming is adjusted to match:

```
Ortho4XP_Overlays
```

This replaces `yOrtho4XP_Overlays`. The transitional package aggregates per-tile
overlay DSFs as the current system does. Long-term, the per-tile overlay model
(recommendation 7.4) replaces this.

### 2.4 scenery_packs.ini Sorting Behavior

The new names sort naturally in `scenery_packs.ini` alphabetical fallback order:

| Priority | Entry | Notes |
|----------|-------|-------|
| Higher | `Ortho4XP_Mesh_+43-079` | Mesh/ortho tiles sort before `simHeaven_X-World_*` |
| | `Ortho4XP_Overlay_+43-079` | Per-tile overlays sort before mesh |
| | `Ortho4XP_Overlays` | Monolithic overlay sorts before mesh |
| Lower | `simHeaven_X-World_*` | X-World layers sort below Ortho4XP entries |

**However**, the correct ini order is:
```
Higher: X-World overlay layers
Middle: Ortho4XP_Overlay_* (if used without X-World)
Lower:  Ortho4XP_Mesh_*
```

This means alphabetical sorting alone is insufficient — explicit ini management
(follow-up 7.6) remains required for correct ordering. The new naming convention
makes the package purpose clear in the directory name, which makes manual or
tool-assisted ini editing more reliable.

## 3. Configurable Naming Options

### 3.1 Configuration Schema

The following keys are added to the global config (in `O4_Cfg_Vars.py`):

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `package_prefix` | str | `"Ortho4XP"` | Prefix for all generated package directory names |
| `package_separator` | str | `"_"` | Separator between name components |
| `mesh_purpose_token` | str | `"Mesh"` | Purpose token for mesh/ortho tile packages |
| `overlay_purpose_token` | str | `"Overlay"` | Purpose token for overlay packages |
| `monolithic_overlay_name` | str | `"Overlays"` | Name for the monolithic overlay package (plural) |
| `latlon_format` | str | `"short"` | Lat/lon format: `"short"` (+43-079), `"hem"` (N43W079), `"long"` (+40-080/+43-079) |
| `per_tile_overlays` | bool | `False` | Generate per-tile overlay packages instead of monolithic |

### 3.2 Resolution Logic

The package directory name is assembled as:

```
{package_prefix}{package_separator}{purpose_token}{package_separator}{location_suffix}
```

Where `location_suffix` depends on context:
- For mesh tiles: `short_latlon(lat, lon)` (or configured format)
- For per-tile overlays: `short_latlon(lat, lon)` (or configured format)
- For monolithic overlays: no location suffix; uses `monolithic_overlay_name` as the purpose token
- For grouped tiles (via `custom_build_dir`): the existing override behavior is preserved

### 3.3 Backward Compatibility

When all config values are at defaults:
```
Ortho4XP_Mesh_+43-079
Ortho4XP_Overlay_+43-079
Ortho4XP_Overlays
```

Users migrating from legacy names can set:
```toml
package_prefix = "zOrtho4XP"
```
To produce `zOrtho4XP_Mesh_+43-079`, preserving the old prefix while gaining
the new purpose-token structure.

Users who want the exact legacy `zOrtho4XP_+43-079` format can set:
```toml
package_prefix = "zOrtho4XP_"
mesh_purpose_token = ""
```
(Empty purpose token with separator stripped.)

## 4. Package Metadata Schema

### 4.1 File: `package.json` in Package Root

Every generated package contains a `package.json` file in its root directory
with the following schema:

```json
{
  "$schema": "https://schemas.ortho4xp.dev/package-v1.json",
  "name": "Ortho4XP_Mesh_+43-079",
  "version": "1.0.0",
  "author": "Ortho4XP",
  "description": "Ortho4XP-generated mesh and orthophoto tile for +43-079",
  "type": "mesh",

  "compatibility": {
    "min_xplane_version": "12.0.0"
  },

  "tile": {
    "lat": 43.0,
    "lon": -79.0,
    "lat_rounded": 40,
    "lon_rounded": -80
  },

  "generation": {
    "tool": "Ortho4XP",
    "tool_version": "1.0.0",
    "timestamp": "2026-06-13T12:00:00Z"
  },

  "imagery": {
    "provider": "BI",
    "zoom_level": 17
  },

  "overlay": {
    "source": "X-Plane Global Scenery",
    "excluded_polygon_types": [0],
    "excluded_network_types": []
  },

  "mesh": {
    "triangulation_method": "Triangle4XP",
    "coast_ratio": 0.1,
    "mask_imprinted": true
  }
}
```

### 4.2 Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | Yes | string | Package directory name |
| `version` | Yes | string | SemVer version (starts at `1.0.0`) |
| `author` | Yes | string | Tool or user who generated the package |
| `description` | Yes | string | Human-readable description |
| `type` | Yes | enum | `"mesh"`, `"overlay"`, `"library"` |
| `compatibility.min_xplane_version` | Yes | string | Minimum X-Plane version (e.g. `"12.0.0"`) |
| `tile` | Yes* | object | Tile coordinates (required for mesh/overlay types) |
| `generation.tool` | Yes | string | Generating tool name |
| `generation.tool_version` | Yes | string | Generating tool version |
| `generation.timestamp` | Yes | string | ISO 8601 generation timestamp |
| `imagery` | Conditional | object | Required for `type=mesh`; provider and ZL info |
| `overlay` | Conditional | object | Source info for overlay packages |
| `mesh.triangulation_method` | Conditional | string | Required for `type=mesh` |

### 4.3 Validation

Package metadata is validated against a JSON Schema (`package-v1.json`) at
generation time. Invalid metadata (missing required fields, type errors) causes
a build failure with an actionable error message.

A CLI validation command (`validate-package`) checks existing packages for
schema compliance.

## 5. File Layout Changes

### 5.1 Mesh/Ortho Tile Package (New Layout)

```
Ortho4XP_Mesh_+43-079/
  package.json                     # Package metadata (NEW)
  Earth nav data/
    +40-080/
      +43-079.dsf
  terrain/
    *_*.ter
  textures/
    *_*_<provider><ZL>.dds
    water_transition.png
```

Intermediate build artifacts (`.mesh`, `.node`, `.ele`, `.poly`, `.apt`,
`.weight`, `.alt`) are moved to a build-cache directory outside the package.
See recommendation 7.5.

### 5.2 Overlay Package (Per-Tile, New Layout)

```
Ortho4XP_Overlay_+43-079/
  package.json                     # Package metadata (NEW)
  Earth nav data/
    +40-080/
      +43-079.dsf                  # Overlay DSF with PROPERTY sim/overlay 1
```

### 5.3 Overlay Package (Monolithic, Transitional Layout)

```
Ortho4XP_Overlays/
  package.json                     # Package metadata (NEW)
  Earth nav data/
    +40-080/
      +43-079.dsf
      +44-080.dsf
      ...
```

## 6. Migration Path

### 6.1 New Tiles

All new tiles use the new naming convention and include `package.json`. The
configuration defaults produce the `Ortho4XP_` prefix — no user action needed
to adopt the new scheme.

### 6.2 Existing Tiles

Existing `zOrtho4XP_+*` and `yOrtho4XP_Overlays` directories are not renamed or
modified. A future `upgrade-package` CLI command may offer to:
1. Rename the directory to the new convention
2. Generate a `package.json` for each existing package
3. Update `scenery_packs.ini` references if managed

### 6.3 Compatibility Wrapper

During the transition, `O4_File_Names.py` supports both the old `tile_dir()`
function and the new convention via the config settings. Consumers that import
`tile_dir` get the new naming when config defaults are active; setting
`package_prefix = "zOrtho4XP_"` and `mesh_purpose_token = ""` restores the
legacy naming.

## 7. Implementation Plan (Concrete Steps)

The following steps are ordered serially, one at a time:

### Step 1: Add config keys

Add `package_prefix`, `package_separator`, `mesh_purpose_token`,
`overlay_purpose_token`, `monolithic_overlay_name`, `latlon_format`, and
`per_tile_overlays` to `O4_Cfg_Vars.py` config registry with defaults.

### Step 2: Update O4_File_Names.py

Replace the hardcoded `tile_dir()` function with a config-driven naming
function. Add `overlay_dir()` that uses the new naming. Keep backward
compatibility through config defaults.

### Step 3: Add package.json generation

Add a `write_package_metadata(build_dir, tile, package_type)` function that
writes `package.json` to the package root. Call it from `build_tile()` and
`build_overlay()`.

### Step 4: Rename overlay output directory

Replace the hardcoded `yOrtho4XP_Overlays` path in `O4_File_Names.py:34` with
the new config-driven name. Update `O4_Overlay_Utils.py` consumers.

### Step 5: Update all internal references

Update any code that checks for the `zOrtho4XP_` or `yOrtho4XP_` prefix
string to use the configured naming instead.

### Step 6: Add package validation

Add `validate-package` CLI command that reads `package.json` and checks
schema compliance, required DSF rasters, and tile coordinate consistency.

### Step 7: Add upgrade-package command

Add an optional `upgrade-package` CLI command for migrating existing
`zOrtho4XP_+*` packages to the new naming with generated metadata.

## 8. References

- Phase 1 Audit: docs/superpowers/specs/2026-06-13-xp12-native-scenery-compiler-audit.md
- Prior art: simHeaven X-World naming (`simHeaven_X-World_<continent>-<N>-<layer>`)
- X-Plane scenery pack convention: `Earth nav data/` mandatory, rest is optional
- Ortho4XP source: src/O4_File_Names.py, src/O4_Cfg_Vars.py, src/O4_Overlay_Utils.py
