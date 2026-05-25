# sRGB Histogram Color Normalization Design

## Problem

TODO-016 calls for automated sRGB histogram color normalization to reduce the
"patchwork quilt" effect where adjacent orthophoto textures have visibly
different capture exposure, luminance, or channel balance.

The feature should reduce texture seams without turning Ortho4XP into a global
color-grading tool. It should use neighboring texture edges as local evidence,
apply bounded statistical correction, and avoid blending neighbor pixels into
the target image.

## Current Context

Step 3 texture work is split between `src/O4_Tile_Utils.py` and
`src/O4_Imagery_Utils.py`.

`src/O4_Tile_Utils.py` starts `DSF.build_dsf()` to enqueue texture attributes,
then `download_textures()` calls `IMG.build_jpeg_ortho()` for each texture.
Successful downloads are pushed to the conversion queue, where
`IMG.convert_texture()` creates DDS or GeoTIFF output.

`src/O4_Imagery_Utils.py` already has color handling, but it is static and
provider-defined:

- `download_jpeg_ortho()` downloads or assembles the source JPEG and saves it.
- `build_jpeg_ortho()` ensures a JPEG exists for a provider or combined
  provider.
- `combine_textures()` applies combined-provider masks and `color_transform()`
  operations.
- `convert_texture()` applies configured provider `color_filters` and masks
  before DDS conversion when needed.

What Ortho4XP does not do today:

- It does not inspect north/south/east/west neighbor textures before converting
  the current texture.
- It does not compute edge luminance or RGB statistics from neighboring
  textures.
- It does not dynamically correct a texture based on local seam evidence.
- It does not persist or reuse calibration data between texture builds.

This feature therefore deviates from current behavior by adding an optional
neighbor-aware preprocessing step. Existing static provider color filters remain
unchanged and keep their current meaning.

## Goals

- Add an opt-in texture color normalization setting, disabled by default.
- Use Pillow and NumPy only; do not add OpenCV for the first implementation.
- Compute edge-pixel luminance and RGB statistics from neighboring validated
  textures.
- Apply a conservative sRGB-aware correction before compressor handoff.
- Preserve current behavior exactly when normalization is disabled or no valid
  neighbor evidence exists.
- Add deterministic `unittest` coverage for the normalization math and pipeline
  decision logic.

## Non-Goals

- Do not spatially blend neighbor pixels into the target image.
- Do not create persistent provider or tile calibration caches in this task.
- Do not globally recolor full tiles independent of neighbor evidence.
- Do not require network, X-Plane installs, GDAL command-line tools, or real
  imagery provider data in tests.
- Do not rewrite the texture download scheduler or DDS encoder backend in this
  task; TODO-018 owns encoder parallelism.

## Design

Add a focused normalization module, `src/O4_Color_Normalization.py`, with pure
helpers that can be tested without a tile build:

```python
@dataclass(frozen=True)
class EdgeStats:
    mean_rgb: tuple[float, float, float]
    mean_luminance: float
    pixel_count: int


@dataclass(frozen=True)
class ColorCorrection:
    exposure_scale: float
    channel_scales: tuple[float, float, float]
    strength: float
```

The module should provide:

- Edge extraction for `north`, `south`, `east`, and `west`.
- sRGB-to-linear and linear-to-sRGB conversion helpers for math.
- Edge statistics from a configurable narrow edge band.
- Correction derivation from one or more valid neighbor edge pairs.
- Correction application to a Pillow RGB image using NumPy arrays.

The correction should be bounded. Initial practical limits:

- Edge band width: 32 pixels.
- Maximum exposure scale: `0.85..1.18`.
- Maximum per-channel scale: `0.88..1.14`.
- Default correction strength: `0.65`.

These values are deliberately conservative. They are requirements for the first
implementation, not final color-science claims.

The feature should be configured through `src/O4_Cfg_Vars.py`, exposed through
the existing config registry:

```python
"normalize_texture_colors": {
    "module": "IMG",
    "type": bool,
    "default": False,
    "hint": "When enabled, applies conservative neighbor-edge color normalization to orthophotos before DDS conversion. The correction uses local texture edge statistics only and does not blend neighbor pixels into the image.",
}
```

`src/O4_Imagery_Utils.py` should hold the runtime setting so existing config
assignment machinery can set it on the imagery module.

## Data Flow

When `normalize_texture_colors` is false, the current flow remains unchanged.

When it is true:

1. `build_jpeg_ortho()` or `download_jpeg_ortho()` obtains the target 4096px
   image exactly as today.
2. Before saving or converting the target image, Ortho4XP looks for existing
   JPEG neighbors at the same zoom level and provider code.
3. For each available neighbor:
   - The target edge and the opposite neighbor edge are sampled.
   - Edge stats are computed in linear-light space from sRGB input.
   - The neighbor is ignored if its file is missing, unreadable, wrong-sized,
     or not RGB-compatible.
4. Valid neighbor pairs are combined into one bounded correction.
5. The correction is applied to the target image.
6. Existing provider `color_filters`, mask imprinting, and DDS conversion
   continue through the current `convert_texture()` path.

The first implementation should write the corrected JPEG to the same cache path
only for newly built textures. Existing cached JPEGs should not be silently
rewritten merely because the setting changes; converting an existing cached JPEG
can use a corrected temporary image in the conversion path. This preserves cache
predictability and keeps retouch workflows viable.

## Error Handling

Normalization must be fail-open for ordinary image evidence problems. If a
neighbor file is missing, unreadable, wrong-sized, or has an unsupported mode,
the feature should skip that neighbor and continue.

If all neighbors are skipped, the target image is returned unchanged.

Unexpected programming errors in the pure normalization helpers should not be
swallowed by broad exception handling in tests. Runtime image-loading errors at
the pipeline edge should be caught as `OSError`, `ValueError`, or Pillow image
errors and logged at debug verbosity.

## Testing

Add focused `unittest` coverage with synthetic Pillow images.

Tests should cover:

- sRGB conversion round-trips for representative values.
- Edge extraction returns the correct opposite bands for each direction.
- Edge statistics distinguish luminance and channel-balance differences.
- Correction derivation moves a warm/dark target edge toward a cooler/brighter
  neighbor edge while respecting exposure and channel clamps.
- Correction application changes the target image predictably and preserves
  RGB mode and image size.
- Missing or invalid neighbors produce no correction and no hard failure.
- Pipeline decision tests show normalization is bypassed when
  `normalize_texture_colors` is false.

Tests should import real production code and avoid network, external tools,
full tile builds, and real provider downloads.

## Documentation

Update user-facing development or README documentation that describes texture
build behavior and configuration settings.

The docs should state that normalization is experimental and opt-in, uses local
neighbor edge statistics, and does not blend neighbor pixels into the target
orthophoto.

## Acceptance Criteria

- `normalize_texture_colors` exists in the config registry and defaults to
  `False`.
- The imagery pipeline applies normalization only when the setting is enabled.
- Neighbor edge statistics use Pillow/NumPy and linear-light math from sRGB
  image data.
- Correction is bounded by explicit exposure and channel clamps.
- Missing, invalid, or absent neighbors leave the target image unchanged.
- Existing provider `color_filters`, mask imprinting, and DDS conversion remain
  compatible.
- Deterministic `unittest` coverage verifies the normalization helpers and
  pipeline decisions.
- Relevant focused tests and repository quality checks pass before closing
  TODO-016.
