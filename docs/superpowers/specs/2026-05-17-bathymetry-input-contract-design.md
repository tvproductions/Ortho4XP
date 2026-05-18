# Bathymetry Input Contract Design

## Problem

Ortho4XP now treats XP12 water as the only supported water technology, but the
next XP12 water requirement is not yet explicit: water tiles need valid
bathymetry input before Ortho4XP emits XP12 physical water mesh data. The
current code can reach DSF generation with missing, XP11-era, or malformed
Global Scenery raster data and fail late or accidentally continue with weak
water-depth assumptions.

TODO-014 should make this a hard, testable contract without redesigning the
whole mesh pipeline or pretending mask-derived blend data is true bathymetry.

## Source Basis

The normative source for this design is Laminar's DSF documentation:

- `DSF Usage In X-Plane` documents `sea_level` as bathymetric depth, lists
  XP12 raster layers, states XP12 bathymetry is required, defines XP12 depth as
  a ratio between ground elevation and bathymetry sample, and defines fetch
  ratio as wave scaling from ponds to open ocean.
- `DSF File Format Specification` documents `DEMN` raster definitions and
  `DEMS` raster data, including `DEMI` metadata and `DEMD` payload ordering.

Project source context:

- Ortho4XP 1.40 upstream is described as a compatibility update for XP12 water
  requirements and says new tiles bring seasons, sounds, and related rasters
  from corresponding Global Scenery tiles.
- This repository already extracts Global Scenery raster payloads in
  `src/O4_DSF_Utils.py` and computes mask-derived depth-ratio bounds in
  `src/O4_Bathymetry.py`.

Non-normative background:

- User-visible reports such as Lyndiman's XP12 water-tech notes are useful
  symptom evidence for old ortho tiles missing newer water behavior, but they
  should not define file-format requirements. Terms such as "turbidity" are not
  part of TODO-014's acceptance contract unless backed by Laminar file-format
  documentation.

## Goals

- Define a source-agnostic bathymetry input contract for water tiles.
- Implement XP12 Global Scenery DSF extraction as the only accepted provider for
  TODO-014.
- Fail fast when a tile has water but no valid bathymetry input.
- Keep all-land tiles buildable without requiring bathymetry.
- Preserve `ratio_bathy`, `distance_masks_too`, and mask-derived `node_bathy`
  as blend/control inputs, not true bathymetry sources.
- Add deterministic unit tests that do not require an X-Plane install or full
  tile build.
- Add a `ROADMAP.md` note that future custom bathymetry sources should satisfy
  the same provider contract.

## Non-Goals

- Implement GEBCO, user-supplied raster, or other custom bathymetry providers.
- Validate visual shader results such as turbidity, color, or apparent wave
  variation.
- Rewrite Triangle4XP, Step 2 mesh generation, or the complete DSF writer.
- Change alpha masks, coastline imagery blending, or BC3 mask behavior covered
  by later TODOs.
- Infer undocumented X-Plane 12.1 `WATER_COLOR_MASK` semantics.

## Current Data Flow

Step 2 mesh generation in `src/O4_Mesh_Utils.py` uses the configured DEM and
writes Ortho4XP's mesh file. It does not currently own XP12 bathymetry raster
validation.

Step 4 DSF generation in `src/O4_DSF_Utils.py` reads the generated mesh,
remaps triangle types, recuts water triangles for XP12, computes mask-derived
depth-ratio bounds through `src/O4_Bathymetry.py`, and extracts Global Scenery
raster payloads with `extract_elevation_and_bathymetry_data()`.

That makes DSF build the correct first enforcement point: it has the generated
mesh, can determine whether the tile contains water, and is already responsible
for carrying XP12 raster payloads into the output DSF.

## Proposed Architecture

Introduce a small bathymetry input boundary around the existing Global Scenery
raster extraction path.

The boundary should answer one question:

```text
For this tile and this mesh water state, do we have valid bathymetry input?
```

For TODO-014, the only implemented provider is XP12 Global Scenery DSF raster
extraction through `custom_overlay_src` and `custom_overlay_src_alternate`.
The interface should remain provider-shaped so future work can add custom or
repo-owned bathymetry sources without weakening validation.

The provider returns validated raster payloads for DSF generation. `build_dsf()`
should only receive `bDEMN` and `bDEMS` after validation passes.

## Bathymetry Contract

Bathymetry is required only when the generated mesh contains water triangles
after the existing triangle-type remap.

For a water tile, valid bathymetry input means:

- an XP12 Global Scenery DSF exists for the tile in `custom_overlay_src` or the
  alternate overlay source;
- compressed DSFs can be unpacked and parsed;
- the DSF contains raster definitions and raster payloads;
- the raster definitions include elevation and bathymetry data, with bathymetry
  identified as `sea_level`;
- the raster data includes non-empty payloads for the required layers;
- bathymetry and elevation raster metadata are compatible enough for Ortho4XP's
  current DSF output path;
- malformed atoms, missing atoms, empty payloads, and shape mismatches raise a
  domain-specific bathymetry input error.

For an all-land tile, bathymetry validation is skipped.

Mask-derived `node_bathy` remains a per-node depth-ratio control. It may refine
how strongly a water vertex uses the bathymetry sample, but it must never
satisfy the bathymetry source contract by itself.

## Error Handling

Failures should be hard and actionable. A water tile with invalid bathymetry
input should not proceed to DSF encoding.

Errors should name:

- the tile coordinates;
- the source path or config key being used, especially `custom_overlay_src` or
  `custom_overlay_src_alternate`;
- the failed requirement, such as missing XP12 Global Scenery DSF, missing
  `sea_level` raster, empty raster payload, malformed raster atom, or raster
  shape mismatch;
- the fix: point the overlay source at XP12 Global Scenery or, in future work,
  configure a valid custom bathymetry provider.

Low-level exceptions from file IO, 7z extraction, atom parsing, or NumPy should
be caught at the bathymetry boundary and converted to this domain error, while
preserving enough detail for debug logging.

## Testing Strategy

Tests should use standard-library `unittest` and deterministic fixtures or
in-memory DSF atom builders. They must not require X-Plane, GDAL command-line
tools, imagery providers, or a full tile build.

Coverage should include:

- no-water mesh state skips bathymetry validation;
- water mesh state requires bathymetry validation;
- missing Global Scenery DSF raises a clear bathymetry input error;
- DSF without `sea_level` is rejected;
- empty or malformed `DEMN` or `DEMS` data is rejected;
- bathymetry/elevation metadata mismatch is rejected;
- valid XP12-style raster definitions and payloads are accepted;
- mask-derived `node_bathy`, `ratio_bathy`, and `distance_masks_too` are not
  accepted as bathymetry substitutes;
- no active runtime path restores legacy `XP11 + bathy` behavior or silently
  falls back for water tiles.

Implementation verification should include focused unit tests, Ruff, ty on
changed Python files, and the full repository quality check before closing the
TODO-backed GitHub issue.

## Roadmap Update

`ROADMAP.md` should record that TODO-014 establishes the bathymetry provider
contract and validates XP12 Global Scenery as the first provider. Future work
may add custom or repo-owned bathymetry sources, but those sources must satisfy
the same contract rather than bypassing it with mask heuristics.

## Risks And Tradeoffs

- Strict validation may break tiles that previously limped through with XP11 or
  incomplete Global Scenery data. This is intentional for XP12Max correctness,
  but the error must be clear.
- Parsing real DSF raster atoms enough to validate metadata is more work than
  checking for non-empty bytes, but it prevents false positives from malformed
  or incompatible inputs.
- Defining a provider-shaped boundary adds a small abstraction now. That cost is
  justified because custom bathymetry sources are expected future work and must
  not re-open silent fallback behavior.
- All-land tiles skip bathymetry validation, so tests must make the water/no
  water gate explicit.

## Acceptance Criteria

- A source-agnostic bathymetry input boundary exists.
- XP12 Global Scenery extraction is the only implemented provider.
- Water tiles fail before DSF encoding when bathymetry input is missing or
  invalid.
- All-land tiles do not require bathymetry input.
- Unit tests cover valid and invalid raster input cases without external data.
- `ROADMAP.md` documents the future custom bathymetry-provider direction.
- TODO-014 and GitHub Issue #9 are updated only after implementation and full
  verification pass.
