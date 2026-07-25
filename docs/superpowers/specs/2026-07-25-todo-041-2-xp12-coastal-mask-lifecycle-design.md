# TODO-041-2 XP12 Coastal Mask and Texture Lifecycle Design

## Purpose

`TODO-041-2` adopts a narrow set of X-Plane 12 coastal reliability behaviors
identified during the `Ypsos/ORTHO4XP_V3` audit. The sister project is evidence
for the failure cases, not an implementation source. This repository will
reimplement the useful behavior through its existing DSF, `TextureSource`,
provider-failover, and texture-conversion contracts.

The change remains X-Plane 12 only. It does not restore `XP11+bathy`, import the
sister project's `O4_Sea_Texture` or `O4_Coastal_Manager` subsystems, or add a
parallel sea-texture architecture.

## Evidence and XP12 Constraints

The audited sister project demonstrates these intended behaviors:

- verify a coastal mask exists before writing `BORDER_TEX`;
- omit the land decal for both inland-water and ocean triangles;
- reject a sand-mask blur kernel that cannot fit the working mask image;
- prefer an explicit provider extent to inferred coastal fill;
- use the active provider in generated texture names.

Its implementation is not adopted directly:

- missing-mask fallback is selected inside `.ter` writing, after the DSF has
  already selected overlay coordinate semantics;
- imprinted mask files are removed immediately after being copied into an image,
  before the external DDS encoder succeeds;
- extent precedence is duplicated across sea-texture paths, and one
  `_find_sea_mask` implementation is not connected to the active conversion
  path;
- provider naming assumes the sister project's provider and JPG-patch model,
  while this repository has an explicit in-memory `TextureSource` and real
  provider failover.

Official X-Plane documentation adds an important ordering constraint.
`WATER_COLOR_MASK` terrain expects four post-normal coordinates interpreted as
fetch ratio, bathymetry ratio, and water-texture S/T. A terrain with
`BORDER_TEX` instead consumes a separate S/T pair for the border alpha mask.
Therefore a missing `BORDER_TEX` resource cannot be handled safely by changing
only the final `.ter` directive. Mask disposition must be known before DSF pool
and vertex-coordinate selection.

References:

- [DSF Usage In X-Plane](https://developer.x-plane.com/version/x-plane-11/page/2/)
- [Terrain Type File Format Specification](https://developer.x-plane.com/article/terrain-type-ter-file-format-specification/)
- [Standard Shading Options for X-Plane Scenery](https://developer.x-plane.com/article/standard-shading-options-for-x-plane-10-scenery/)
- [Finishing 12.1.0 Features](https://developer.x-plane.com/2024/03/finishing-12-1-0-features/)

## Failure Family

The current implementation distributes one artifact decision across
`O4_DSF_Utils`, `O4_Mask_Utils`, `O4_Imagery_Utils`, and
`O4_Texture_Conversion_Utils`. Each module sees only part of the state:

- DSF generation decides whether geometry is native XP12 water, an external
  border-mask overlay, or DDS-imprinted water.
- Mask code finds and crops coastal alpha but does not declare ownership.
- Imagery preparation applies alpha and currently deletes the source mask.
- Texture conversion knows whether encoding succeeded but does not know which
  non-temporary artifact may then be removed.
- Provider failover can replace the requested provider after DSF terrain names
  have already been produced.

The result is temporal coupling: correctness depends on functions running in an
unstated order and on files continuing to exist between those calls.

## Considered Approaches

### Inline Conditional Fixes

Patch `create_terrain_file`, `blur_mask`, and `convert_texture` independently.
This is the smallest diff and resembles the sister project's implementation.
It is rejected because it retains the late fallback, implicit file ownership,
and requested-versus-resolved provider ambiguity.

### Port the Sister Coastal Subsystem

Import or adapt `O4_Coastal_Manager`, `O4_Sea_Texture`, and their JPG-patch
workflow. This is rejected because it replaces local architecture, includes
unrelated behavior, and would reintroduce XP11-oriented branches.

### Explicit Coastal Artifact Policy

Represent the coastal decision before DSF geometry is emitted, carry mask
ownership into conversion, and preserve requested and resolved texture
identities separately. This is the selected approach. It fixes the class of
ordering failure while remaining a focused XP12 refactor.

## Coastal Mask Decision

A small immutable decision contract records:

- disposition: `native_water`, `external_border`, `imprinted_alpha`, or
  `unmasked_land`;
- selected mask path or image, if any;
- mask ownership: retained scenery resource or removable conversion input;
- provider/extent basis used to make the decision;
- diagnostic reason for fallback or suppression.

The contract is computed once per terrain/texture requirement before
`is_overlay`, DSF pool selection, `.ter` directives, or conversion cleanup are
chosen.

Decision order:

1. Determine whether the triangle is land, inland water, or ocean.
2. Resolve whether the selected provider has an explicit non-global coverage
   extent.
3. If an explicit provider extent governs coverage, do not synthesize an
   additional coastal-fill decision that can override it.
4. Otherwise locate and validate the coastal mask.
5. If no usable mask exists, select native XP12 water before pool allocation.
6. If a mask exists and `imprint_masks_to_dds` is false, select
   `external_border` and retain the PNG as scenery.
7. If a mask exists and `imprint_masks_to_dds` is true, select
   `imprinted_alpha` and retain it until conversion success.

An external-border terrain may be emitted only when its referenced PNG exists.
The `.ter` writer asserts the already-made decision; it does not invent a
fallback with different coordinate semantics.

## Provider Extent Precedence

Provider extents and coastal masks answer different questions:

- the provider extent declares where source imagery is authoritative;
- the coastal mask infers where an orthophoto should blend with XP12 water.

An explicit non-global provider extent is the stronger source of coverage
authority. Inferred coastal fill must not expand, replace, or contradict that
extent. This rule applies equally to external-border and imprinted-alpha modes
so toggling `imprint_masks_to_dds` cannot change provider coverage.

Extent lookup uses the resolved texture provider/layer inventory already loaded
by `O4_Imagery_Utils`; it does not depend on the sister project's ZonePhoto
global state.

## Mask Ownership and Conversion

Mask files have two distinct lifetimes:

- `external_border`: a packaged scenery dependency referenced by `BORDER_TEX`;
  never conversion cleanup;
- `imprinted_alpha`: a build input that may be removed only after the DDS
  encoder returns a successful result.

Imagery preparation may load and apply an imprinted mask, but it must not remove
the mask. It passes a typed post-success cleanup request to DDS conversion.
`convert_dds_texture` performs that cleanup only when the encode result is
successful. A returned failure result, raised exception, interruption, or
missing output leaves the mask available for retry and diagnosis.

Ordinary temporary PNG/TIFF cleanup remains independent and continues on both
success and failure where safe. A cleanup request must identify its artifact
kind so a retained `BORDER_TEX` mask cannot be mistaken for a temporary file.

## Requested and Resolved Provider Identity

Provider failover creates two valid identities:

- requested texture attributes: the stable terrain requirement produced by DSF
  planning;
- resolved source attributes: the provider that actually supplied imagery.

`TextureSource` preserves both. Generated DDS and provider-derived texture names
use the resolved source provider, never `tile.default_website`. Terrain
resources retain their stable requested identity while the Step 3 finalization
phase records and applies the resolved DDS reference before activating the
temporary DSF.

Conversion success returns a texture-resolution record containing requested
attributes and the resolved DDS name. After the DSF producer, downloader, and
converter have joined, but before `.dsf.tmp` activation, one deterministic
finalizer updates the affected `.ter` `BASE_TEX_NOWRAP` references. Failed or
missing conversions do not activate a terrain reference to a nonexistent DDS.
This avoids filename aliases, duplicate DDS files, and races between conversion
workers and terrain-file creation.

The same resolved-provider naming helper governs any provider-derived patch-like
texture artifact. The design does not add the sister project's JPG-patch
generator.

## Terrain Material Policy

Land decals are emitted only for land triangles (`tri_type == 0`). Inland-water
and ocean triangles receive no vegetation-oriented land decal.

`WET` remains the terrain physics declaration and is not inferred from visual
alpha. The change does not alter the established XP12 bathymetry, fetch, or
water-coordinate calculations.

## Sand-Mask Validation

Sand-mask validation occurs before old masks are deleted or convolution begins.
It verifies:

- sand mode receives one finite, non-negative numeric width rather than the
  three-value `3steps` shape;
- the input mask is a non-empty two-dimensional array;
- the meter-to-pixel conversion is finite;
- the resulting hat kernel is non-empty and does not exceed the working image
  dimensions.

Invalid configuration fails the mask step with a clear message and preserves
existing masks. Validation is a pure helper so boundary values and malformed
shapes can be tested without building scenery.

## Error Handling

- Missing or unreadable inferred masks select native XP12 water before DSF pool
  creation and produce a useful diagnostic.
- A mask that disappears after the decision but before `.ter` writing is a
  consistency failure; generation stops rather than emitting a broken resource.
- DDS failure retains imprinted masks and reports the existing provider-aware
  conversion failure.
- Finalization rejects duplicate or conflicting resolutions for one requested
  terrain requirement.
- A resolved DDS reference is applied atomically to its terrain files before
  DSF activation.
- Existing scenery is not activated when required texture finalization fails.

## Testing

All tests use standard-library `unittest`, temporary directories, in-memory
images, and mocked encoder results. They require no network, X-Plane install,
imagery provider, or external DDS/GDAL executable.

Coverage includes:

- external mask present: `BORDER_TEX` is emitted and its file is retained;
- external mask absent: native XP12 water and its coordinate layout are chosen;
- mask disappearance after decision: terrain generation fails safely;
- imprinted DDS success: mask is removed after confirmed success;
- returned DDS failure and raised encoder exception: mask remains;
- external-border masks are never submitted as cleanup candidates;
- explicit non-global extent suppresses inferred coastal fill in both modes;
- global/no explicit extent permits normal coastal-mask selection;
- ocean and inland-water terrains contain no land decal;
- land terrain retains the configured decal;
- valid, zero-width, oversized, non-numeric, non-finite, and wrong-shape sand
  configurations;
- provider failover preserves requested identity while resolved DDS naming uses
  `TextureSource.provider_code`;
- terrain finalization rewrites resolved DDS references before activation and
  rejects failed or conflicting mappings;
- no `XP11+bathy` branch or fixture is introduced.

Tests assert semantic outcomes: selected disposition, coordinate contract,
resource lifetime, provider identity, and generated terrain directives. They do
not merely copy incidental strings from a first run.

## Documentation and Tracking

`TODO-041-2` remains linked to GitHub Issue #39. Implementation evidence will
record:

- focused unit-test results;
- changed-file Ruff and `ty` results;
- full repository quality-check results;
- representative generated `.ter` contents for native-water,
  external-border, and imprinted-alpha cases;
- confirmation that no XP11 path or sister sea-texture subsystem was added.

The issue receives an implementation/evidence comment and closes only after all
acceptance criteria and repository quality checks pass.

## Completion Criteria

The work is complete when one early coastal decision governs DSF layout,
terrain directives, extent precedence, mask lifetime, and conversion cleanup;
resolved provider identity reaches generated texture references safely; every
accepted failure mode has deterministic tests; and the repository remains
strictly X-Plane 12.
