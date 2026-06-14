# XP12-Native Scenery Compiler/Workbench Strategy — Phase 1: Audit

Date: 2026-06-13
Issue: TODO-027 / GHI #31
Status: Audit phase — no generated scenery output changed
Reviewed: 2026-06-13 — all sections confirmed by maintainer

## 1. Purpose & Scope

This document is Phase 1 (audit) of the TODO-027 deliverable. It inventories the
current Ortho4XP scenery generation architecture, documents how generated
packages interact with the X-Plane 12 scenery stack, studies architectural
patterns from public SimHeaven/X-World packages, and defines project ownership
boundaries. The future-naming and package-layout strategy (Phase 2) follows in a
separate design document.

Scope covers: package naming, DSF layout, overlay handling, `scenery_packs.ini`
ordering, XP12-specific DSF requirements, and architectural patterns from public
scenery-stack packages. No generated scenery output is changed.

## 2. Current State Audit

### 2.1 Package Naming Convention

**Definition**: `zOrtho4XP_<short_latlon>` where `short_latlon` is a zero-padded
signed format like `+43-079`. Defined at `src/O4_File_Names.py:70-71`:

```python
def tile_dir(lat, lon):
    return "zOrtho4XP_" + short_latlon(lat, lon)
```

**Overlay naming**: `yOrtho4XP_Overlays` — a single monolithic overlay package
containing overlay DSFs from all built tiles. Defined at `src/O4_File_Names.py:34`.

**Properties of the current naming convention**:

| Aspect | Current behavior |
|--------|-----------------|
| Encodes spatial location | Yes (lat/lon in the name) |
| Encodes package purpose | Implicit only (the `z`/`y` prefix convention) |
| Encodes version | No |
| Encodes author/source | No |
| Encodes compatibility info | No |
| Human-readable | Debatable — the `z` prefix is legacy XP8 convention |
| Supports grouped tiles | Yes, via `custom_build_dir` override that replaces the name entirely |

**Legacy origin**: The `z` prefix dates to X-Plane 8/9 era, where alphabetical
ordering in `scenery_packs.ini` was the only priority mechanism. Packages
starting with `z` sorted to the bottom (lowest priority). LR added explicit
`scenery_packs.ini` priority ordering in XP10 — the `z` prefix is no longer
functionally required. Similarly `yOrtho4XP_Overlays` uses `y` to sort above `z`.

### 2.2 Generated Package Layout

Each tile generates:

```
Tiles/
  zOrtho4XP_+43-079/                  # Mesh + orthophoto package
    Earth nav data/
      +40-080/
        +43-079.dsf                    # Binary DSF with mesh + ortho textures
    terrain/
      *_*.ter                          # Terrain definition files
    textures/
      *_*_<provider><ZL>.dds           # BC3/DXT5 compressed orthophoto tiles
      water_transition.png
    Data+43-079.mesh                   # Triangle4XP mesh output
    Data+43-079.apt                    # Airport data
    Data+43-079.poly                   # Triangle input polygon
    Data+43-079.node                   # Triangle input nodes
    Data+43-079.ele                    # Triangle input elements
    Data+43-079.weight                 # Coast weight data
    Data+43-079.alt                    # Altitude data
```

The overlay package:

```
yOrtho4XP_Overlays/                    # Single overlay-only package
  Earth nav data/
    +40-080/
      +43-079.dsf                      # Overlay DSF (no mesh, PROPERTY sim/overlay 1)
```

### 2.3 DSF Encoding Summary

The DSF binary encoder lives in `src/O4_DSF_Utils.py:941-1204` and writes:

1. **Header**: `XPLNEDSF` + version uint32 `1`
2. **DAEH (Head)**: Contains `sim/west`, `sim/east`, `sim/south`, `sim/north`,
   `sim/creation_agent = "Ortho4XP"`
3. **NFED (Definitions)**: Terrain definition list, DEMN raster definitions
4. **DOEG (Geodata)**: Point pools with 7-element (land) or 9-element (water/overlay) planes
5. **SDMC (Commands)**: Triangle patches with LOD flags (1=physical, 2=overlay)
6. **DEMS**: Bathymetry raster data (XP12-only, when water tris present)
7. **MD5 checksum**: Appended to end of file

XP12 header bridge (`src/O4_DSF_Header_Bridge.py`) splices season/vegetation/
sound/friction properties from Global Scenery DSFs into generated DSF text via
DSFTool round-trip.

### 2.4 Overlay Extraction

Overlays are copied from existing scenery (Global Scenery or user-specified
source) via `src/O4_Overlay_Utils.py`:

- Source overlay DSF is found in `custom_overlay_src` or `custom_overlay_src_alternate`
- Converted to text via `DSFTool --dsf2text`
- PROPERTY lines, POLYGON_DEF, NETWORK_DEF, BEGIN_POLYGON/END_POLYGON,
  BEGIN_SEGMENT/END_SEGMENT blocks are copied
- Mesh data is NOT copied; overlay DSFs are marked `PROPERTY sim/overlay 1`
- A single monolithic `yOrtho4XP_Overlays` directory contains every tile's overlay DSF
- Excluded polygon types: `ovl_exclude_pol = [0]` (beaches)
- Excluded network types: `ovl_exclude_net = []` (none by default)

### 2.5 scenery_packs.ini Management

**Current state**: Ortho4XP does NOT write or modify `scenery_packs.ini`. It
relies on symlinks (placed in `custom_scenery_dir` via GUI) and assumes the user
will arrange the ini order manually (or let X-Plane rebuild it alphabetically,
which is an error-prone fallback).

Known scenery_packs.ini ordering (unwritten convention):

| Priority | Package | Source |
|----------|---------|--------|
| Higher | Custom airports | User-installed |
| | X-World packages | simHeaven |
| | yOrtho4XP_Overlays | Ortho4XP |
| | zOrtho4XP_+* | Ortho4XP |
| Lower | Global Scenery | X-Plane (implicit) |

This order is not documented anywhere in the codebase, not validated at build
time, and not checked for consistency before or after tile generation.

## 3. XP12 Requirements Audit

### 3.1 What Ortho4XP Does Correctly for XP12

| Feature | Implementation | File/Line |
|---------|---------------|-----------|
| Bathymetry DEMN/DEMS rasters | Extracted from Global Scenery, inserted into generated DSF | `src/O4_DSF_Utils.py:424-428` |
| Water triangle recutting | Coastline tris split for clean land/water boundaries | `src/O4_Bathymetry.py:16-191` |
| WATER_COLOR_MASK in .ter | Enables XP12 3D water rendering | `src/O4_DSF_Utils.py:305-307` |
| Depth-as-ratio encoding | Water verts use ratio [0.1, 1.0] instead of absolute depth | `src/O4_Bathymetry.py:9-13` |
| Season/vegetation header bridge | Preserves 4 property types from Global Scenery | `src/O4_DSF_Header_Text.py:11-16` |
| water_tech locked to XP12 | No legacy water modes allowed | `src/O4_Cfg_Vars.py:306-311` |
| Pool planes 7/9 | Correct per-vertex element counts for land, water, overlay | `src/O4_DSF_Utils.py:534-540` |

### 3.2 What XP12 Requires That Ortho4XP Does NOT Generate

| Feature | XP12 Status | Gap | Priority |
|---------|-------------|-----|----------|
| **Seasonal rasters** (`spr1`/`spr2`/`sum1`/`sum2`/`fal1`/`fal2`/`win1`/`win2`) | 8 required DEM rasters for vegetation seasonal transitions | Only bridged from Global Scenery headers; no native generation or validation | **Must fix** |
| **Soundscape raster** | Per-pixel environmental sound codes (0=barren, 30=water, 40=forest, etc.) | Not generated at all; missing from DSF entirely | **Must fix** |
| **Bathymetry fallback** | Required for water tris; currently requires Global Scenery | No custom bathymetry provider; fails if Global Scenery not found | Medium |
| **Package metadata** | No version, author, description, or compatibility info in package | ROADMAP.md explicitly calls this "folder-name folklore" | High |
| **scenery_packs.ini validation** | No ordering checks, no missing-dependency detection | User must manually arrange or accept alphabetical fallback | High |
| **DSF raster validation** | No self-check that required rasters (bathy, seasonal, soundscape) are present | Runtime failures from XP12 are opaque | Medium |

### 3.3 Legacy Conventions Kept for No Functional Reason

| Convention | XP12 functional requirement | Decision |
|------------|---------------------------|----------|
| `z` prefix in tile name | Not needed — ini priority replaced alphabetical sorting in XP10 | **Remove in Phase 2** |
| `y` prefix in overlay name | Not needed — same reason | **Remove in Phase 2** |
| Single monolithic overlay package | Overlay DSFs are additive; one package per tile would work | **Replace with per-tile/per-region overlay packages in Phase 2** |
| Intermediate mesh/weight files in tile dir | Build artifacts, not runtime scenery | Isolate to build-cache directory |

## 4. Scenery Stack Interaction Map

### 4.1 Scenery Pack Types in X-Plane

X-Plane 12 recognizes four scenery pack types based on content:

| Pack Type | Contains | `sim/overlay` | Ini Priority | Notes |
|-----------|----------|---------------|--------------|-------|
| **Mesh pack** | DSF with mesh patches + .ter | Absent | Lowest — only one per tile wins | Ortho4XP tile |
| **Overlay pack** | DSF with objects/forests/roads/exclusions | `1` | Above mesh | yOrtho4XP_Overlays, X-World |
| **Library pack** | `library.txt` exporting virtual paths | N/A | Must be loaded before referencing packs | OpenSceneryX, SimHeaven Vegetation Library |
| **Airport pack** | `apt.dat` + optional overlay DSF | Varies | Highest | Gateway airports, payware |

### 4.2 Recommended scenery_packs.ini Order (Per LR and SimHeaven)

```
Priority 1 (TOP): Custom Airports & Landmarks
Priority 2:       *GLOBAL_AIRPORTS*
Priority 3:       X-World overlay/object layers (8 layers per continent, numbered)
Priority 4:       Libraries (OpenSceneryX, SimHeaven Vegetation Library, etc.)
Priority 5:       yOrtho4XP_Overlays (if used in non-X-World areas)
Priority 6:       zOrtho4XP_* ortho tiles (mesh + orthophotos)
Priority 7 (BOTTOM): HD/UHD Mesh or other base mesh (only one mesh per tile)
```

**Critical principle**: Only one mesh per 1x1 degree tile is loaded — the
highest-priority mesh pack wins. Overlay packs stack additively. Exclusion zones
in higher-priority overlays remove objects from lower packs.

### 4.3 How Ortho4XP Packages Fit

**Generated mesh tiles (`zOrtho4XP_+*`)**:
- Provide base mesh + orthophoto textures for their 1x1 tile
- Coexist with Global Scenery (only one mesh per tile — Ortho4XP's replaces default)
- Must be placed BELOW overlays, ABOVE any other mesh (like HD Mesh)
- Compete with other mesh packs per-tile (meshes are all-or-nothing per tile)

**Overlay package (`yOrtho4XP_Overlays`)**:
- Provides autogen overlay data for tiles built with Ortho4XP
- Extracted from Global Scenery — it's a copy, not original content
- Redundant in areas covered by SimHeaven X-World (X-World layers include their
  own overlay data with exclusions)
- Must be placed ABOVE mesh tiles, BELOW X-World and libraries

### 4.4 SimHeaven X-World Integration

X-World is an 8-layer overlay system that provides OSM-driven autogen:

```
simHeaven_X-World_Europe-1-vfr         # VFR landmarks, exclusions
simHeaven_X-World_Europe-2-regions     # Regional object overrides
simHeaven_X-World_Europe-3-details     # Detail objects
simHeaven_X-World_Europe-4-extras      # Extra elements (parking, campsites, etc.)
simHeaven_X-World_Europe-5-footprints  # MS building footprints
simHeaven_X-World_Europe-6-scenery     # Main OSM buildings + library.txt
simHeaven_X-World_Europe-7-forests     # Forests (uses XP12 3D vegetation)
simHeaven_X-World_Europe-8-network     # Roads, railways, power lines
```

Key architectural patterns:
- **Layered separation**: Each layer is an independent scenery pack in
  `scenery_packs.ini`, ordered numerically. Layers 1-8 separate concerns
  (VFR landmarks, regions, details, extras, building footprints, main scenery,
  forests, network).
- **Ortho support via library.txt**: Layer 6 includes a `library.txt` that is
  swappable — a separate `library - orthographic.txt` maps ground polygons to
  `blank.pol` so orthoimagery shows through.
- **Overlay redundancy**: X-World DSFs include exclusion zones for default
  scenery objects. When X-World is present above the ortho mesh,
  `yOrtho4XP_Overlays` is redundant in those tiles. **Maintainer confirms**:
  the single monolithic `yOrtho4XP_Overlays` is a legacy convention to be
  replaced in Phase 2.
- **No overlay DSF needed**: X-World does not produce `sim/overlay 1` DSFs
  with mesh base — its DSFs go in overlay/object layers above mesh.
- **Vegetation library as symlink**: The SimHeaven Vegetation Library is a
  symlink to XP12's native `Resources/default scenery/1200 forests/`, enabling
  XP12 3D vegetation with 5 climate zones and automatic seasonal transitions.
- **scenery_packs.ini documentation**: The simHeaven FAQ provides explicit
  ordering guidance, and the package README/PDF manual covers installation
  troubleshooting.

## 5. Project Ownership Boundaries

### 5.1 What Ortho4XP Owns (in scope for v1.0)

| Domain | Ownership | Rationale |
|--------|-----------|-----------|
| Mesh generation | Full ownership | Triangle4XP / triangle meshing pipeline, elevation/bathymetry input, coastline handling |
| Imagery/raster pipeline | Full ownership | Provider download, caching, crop/warp, color filters, mask generation, GeoTIFF export, DDS encoding |
| DSF binary encoding | Full ownership | Hand-coded XPLNEDSF writer, point pools, terrain definitions, patch commands |
| Package generation | Full ownership | Tile directory layout, .ter files, texture staging, DSF placement |
| Bathymetry input | Full ownership | Extraction from Global Scenery; custom provider boundary defined but not implemented |
| DSF metadata bridge | Full ownership | Season/vegetation/sound/friction header splicing from Global Scenery |
| Package validation | Planned ownership | Not yet implemented; ROADMAP.md calls for validation, metadata, and compatibility reporting |
| Generated output quality | Full ownership | Mask quality, texture compression, color fidelity, mesh correctness |

### 5.2 What Ortho4XP Depends On (owned by others)

| Dependency | Source | Boundary |
|------------|--------|----------|
| XP12 Global Scenery rasters | Laminar Research | Ortho4XP reads DEMN/DEMS for bathymetry; reads DSF headers for season/veg/sound/friction |
| Overlay autogen data | Laminar Research / SimHeaven | Ortho4XP copies overlay data from installed scenery; does not generate its own |
| OSM data | OpenStreetMap | Ortho4XP queries for coastline, airport, and water feature data |
| Elevation data | Various providers | Current: viewfinderpanoramas (default); user-configurable |
| Provider imagery | Various (Google, Bing, ArcGIS, etc.) | Ortho4XP downloads orthophoto tiles; provider availability is external |

### 5.3 What Ortho4XP Does NOT Own (explicitly out of scope)

| Domain | Rationale |
|--------|-----------|
| 3D object generation | Ortho4XP is a mesh/imagery compiler, not a 3D asset generator |
| Autogen placement rules | Extracted from existing scenery, not authored |
| Building footprint generation | SimHeaven X-World provides this via MS footprint data |
| Forest/vegetation generation | X-World handles OSM-based forest placement; XP12 native vegetation handles 3D |
| Airport layout/customization | X-Plane Global Airports + custom airport sceneries |
| Object library creation | Out of scope until base compiler architecture is understood |

## 6. Non-Goals (Phase 1)

1. **No copying third-party assets** — This audit studies architectural patterns
   only. No SimHeaven, X-World, or third-party assets are redistributed.
2. **No replacing SimHeaven packages** — X-World's layered overlay architecture
   is complementary to Ortho4XP, not competitive.
3. **No broad object-library generator** — Object/library generation is deferred
   until the base compiler architecture and package format are understood.
4. **No scenery_packs.ini editing** — The current phase audits the gap; a future
   issue will implement validation and optional management.
5. **No naming/layout changes** — The current naming convention is unchanged in
   this document. Phase 2 will propose future naming.
6. **No output format changes** — DSF format, package layout, and texture format
   are unchanged.

*All six non-goals confirmed by maintainer.*

## 7. Concrete Follow-Up Issue Recommendations

The following issues are recommended based on the audit findings. They should be
implemented serially (one at a time, not in parallel) per maintainer preference.

### 7.1 Package Metadata and Validation (Priority: High)

Generate explicit package metadata (name, version, author, description,
compatibility) for each generated package. Add a `package.toml` or `info.json`
to the tile directory. Validate `scenery_packs.ini` ordering against known rules
and report conflicts.

### 7.2 Seasonal and Soundscape Raster Generation (Priority: Must Fix)

Move from "copy from Global Scenery" to "generate or validate required rasters"
for the 8 seasonal boundary rasters (`spr1`-`win2`) and the soundscape raster.
At minimum, validate their presence in the final DSF and report if missing.

### 7.3 Custom Bathymetry Provider Boundary (Priority: Medium)

The current bathymetry input pipeline requires Global Scenery DSFs. Define and
implement a provider interface for custom bathymetry data (e.g., GEBCO, ETOPO1)
to remove the Global Scenery dependency for water tiles.

### 7.4 Per-Tile Overlay Package Option (Priority: Low)

Evaluate splitting `yOrtho4XP_Overlays` into per-tile overlay packages that
can be individually enabled/disabled in `scenery_packs.ini`. This would give
users finer control over which tiles get overlays.

### 7.5 Build Artifact Isolation (Priority: Low)

Move intermediate build artifacts (`.mesh`, `.node`, `.ele`, `.poly`, `.apt`,
`.weight`, `.alt` files) out of the tile directory and into a build-cache
directory, keeping only the runtime DSF/terrain/texture files in the deployable
package.

### 7.6 Symlink and scenery_packs.ini Management (Priority: Medium)

Replace the current manual symlink workflow with optional automated
`scenery_packs.ini` entry management (add/remove/reorder entries). The current
symlink approach works but provides no feedback about ordering, conflicts, or
missing dependencies.

### 7.7 Package Compatibility Diagnostics (Priority: Low)

Add a `validate-job` or `validate-scenery` CLI command that checks:
- All required scenery packages are installed
- `scenery_packs.ini` ordering is correct
- DSF files have required XP12 rasters
- No duplicate or conflicting packages exist

## 8. References

- DSF File Format Specification: developer.x-plane.com/article/dsf-file-format-specification/
- DSF Usage in X-Plane: developer.x-plane.com/article/dsf-usage-in-x-plane/
- Prioritization of Scenery Packs: x-plane.com/kb/prioritization-scenery-packs/
- SimHeaven X-World: simheaven.com
- Ortho4XP source: src/O4_File_Names.py, src/O4_DSF_Utils.py, src/O4_Overlay_Utils.py,
  src/O4_DSF_Header_Bridge.py, src/O4_DSF_Header_Text.py, src/O4_Bathymetry.py,
  src/O4_Cfg_Vars.py
- ROADMAP.md lines 236-249 (scenery strategy), 306-307 (scenery-stack behavior)
- TODO.md lines 702-737 (TODO-027 acceptance criteria)
