# TODO-031 Per-Stage Resampling Policy Design

## Context

TODO-031 follows the GIS/raster/imagery technology map and the Wave 1 GDAL
bindings migration. The current code still hardcodes interpolation choices in
several runtime surfaces:

- Pillow image resizing in texture assembly, provider downsampling,
  combined-provider cropping, mask resizing, alpha mask imprinting, airport
  smoothing masks, and DEM normal-map generation.
- GDAL warp calls in imagery reprojection, GeoTIFF export, and standalone
  geotagging.
- Tests that assert the current hardcoded GDAL warp method.

The TODO requires per-stage defaults with optional config overrides and a full
replacement of hardcoded `BICUBIC` behavior. Because resampling choices affect
generated scenery output, the overrides belong to tile/global-tile
configuration rather than app-only settings.

## Goals

- Add tile/global-tile configuration keys for resampling policy.
- Keep default behavior explicit by stage instead of using one global method.
- Replace every current image/GDAL interpolation call site with a
  config-driven stage lookup.
- Exclude `numpy.resize()` call sites because they grow numeric arrays and are
  not interpolation.
- Validate allowed method names through the existing config registry.
- Add a small policy module that maps config strings to Pillow and GDAL values.
- Add deterministic `unittest` coverage for defaults, validation, mappings,
  runtime selection, and hardcoded-resampling drift.

## Non-Goals

- Do not change generated file names, cache directories, texture dimensions, or
  conversion queue payloads.
- Do not add new runtime dependencies.
- Do not implement the TODO-032 in-memory VRT pipeline.
- Do not add provider-specific resampling overrides.
- Do not change color-correction math beyond allowing a future normalization
  sampling policy to use the same config boundary.

## Configuration

The resampling keys are tile settings and therefore also receive `global_`
counterparts through the existing `cfg_global_tile_vars` generation:

| Key | Default | Allowed values | Purpose |
| --- | --- | --- | --- |
| `texture_resize_resampling` | `lanczos` | `nearest`, `bilinear`, `bicubic`, `lanczos` | Continuous-tone texture resize, downsample, crop, and provider assembly |
| `mask_resize_resampling` | `nearest` | `nearest`, `bilinear`, `bicubic`, `lanczos` | Extent masks, sea masks, and alpha masks |
| `warp_resampling` | `bicubic` | `nearest`, `bilinear`, `bicubic`, `lanczos` | GDAL reprojection and GeoTIFF/geotag warp paths |
| `normalization_resampling` | `bilinear` | `nearest`, `bilinear`, `bicubic`, `lanczos` | Future edge/neighbor sampling resize policy for color normalization |
| `dem_resampling` | `bicubic` | `nearest`, `bilinear`, `bicubic`, `lanczos` | DEM-derived normal-map band resizing |
| `airport_smoothing_resampling` | `bicubic` | `nearest`, `bilinear`, `bicubic`, `lanczos` | Airport smoothing raster downsample |

Each key should include a config hint that names the stage and explains the
default. Invalid values should be rejected by the existing `values` validation
in `O4_Config_Models.coerce_config_value()`. GUI paths already reset invalid
values to defaults; this behavior should remain unchanged.

## Architecture

Create `src/O4_Resampling_Policy.py` as the single translation layer between
config strings and library-specific constants.

The module should own:

- The allowed method tuple: `("nearest", "bilinear", "bicubic", "lanczos")`.
- Pillow mapping:
  - `nearest` -> `Image.Resampling.NEAREST`
  - `bilinear` -> `Image.Resampling.BILINEAR`
  - `bicubic` -> `Image.Resampling.BICUBIC`
  - `lanczos` -> `Image.Resampling.LANCZOS`
- GDAL mapping:
  - `nearest` -> `"near"`
  - `bilinear` -> `"bilinear"`
  - `bicubic` -> `"cubic"`
  - `lanczos` -> `"lanczos"`
- Small helpers for reading stage values from a tile/config object with a
  default fallback:
  - `pillow_resampling(method: str)`
  - `gdal_resampling(method: str)`
  - `tile_pillow_resampling(tile, key: str)`
  - `tile_gdal_resampling(tile, key: str)`

The helpers should raise `ValueError` for unsupported strings if called
directly. Config validation should prevent normal runtime access to invalid
values, but direct failure keeps tests and future call sites honest.

## Call-Site Mapping

The implementation should classify all current interpolation sites:

| File | Current surface | Policy key |
| --- | --- | --- |
| `src/O4_Imagery_Utils.py` | Texture downsample, WMTS subtile resize, final texture resize, preview texture resize, combined-provider layer crop resize | `texture_resize_resampling` |
| `src/O4_Imagery_Utils.py` | Extent masks, sea masks, and alpha mask imprinting | `mask_resize_resampling` |
| `src/O4_Imagery_Utils.py` | `warp_image_with_gdal()` | `warp_resampling` |
| `src/O4_Texture_Conversion_Utils.py` | GeoTIFF `gdal.Warp()` | `warp_resampling` |
| `src/O4_Geotag.py` | Standalone JPEG geotag `gdal.Warp()` | `warp_resampling` |
| `src/O4_DEM_Utils.py` | Normal-map band resize | `dem_resampling` |
| `src/O4_Airport_Geometry.py` | Airport smoothing mask resize | `airport_smoothing_resampling` |

`normalization_resampling` is added with the other policy keys even though the
current normalization implementation samples same-sized 4096px neighbors
without resizing. That keeps the documented TODO-031 config surface complete
and gives future normalization sampling changes a validated boundary.

`numpy.resize()` in bathymetry and water recut utilities remains unchanged and
should be documented in tests as excluded from the resampling audit because it
is array capacity management, not image/GDAL interpolation.

## Error Handling

Config-file values should be handled by the existing coercion path:

- Valid strings load as-is.
- Invalid strings fail `values` validation.
- GUI apply/load paths reset bad values to defaults and report the variable
  name, matching existing config behavior.

Policy helper calls should fail closed with `ValueError` when a method name is
not mapped. This catches direct misuse and prevents silent library fallback.

GDAL call sites should pass the mapped string returned by `gdal_resampling()`.
The policy uses `bicubic` at the config layer and translates it to GDAL's
accepted `"cubic"` value.

## Testing

Tests should be written with `unittest` only.

Add focused tests for:

- Config registry validity and defaults for the six new keys.
- Coercion accepting each allowed method and rejecting invalid strings.
- Pillow mapping returning the exact `Image.Resampling` constants.
- GDAL mapping returning the exact GDAL algorithm strings.
- Representative call sites using tile-provided values instead of hardcoded
  literals:
  - `warp_image_with_gdal()` passes the mapped `warp_resampling`.
  - GeoTIFF conversion passes the mapped `warp_resampling`.
  - At least one texture resize call accepts `texture_resize_resampling`.
  - Alpha mask imprinting accepts `mask_resize_resampling`.
- Source audit preventing new hardcoded interpolation drift:
  - No `Image.Resampling.BICUBIC`, `Image.Resampling.BILINEAR`,
    `Image.Resampling.NEAREST`, or `Image.Resampling.LANCZOS` outside
    `O4_Resampling_Policy.py` and tests.
  - No raw `resampleAlg="..."` outside `O4_Resampling_Policy.py` and tests.
  - `numpy.resize()` is explicitly allowed.

Verification commands:

- `uv run python -m unittest tests.test_config_models tests.test_resampling_policy tests.test_gdal_warp tests.test_gdal_geotiff tests.test_geotag -q`
- `uv run python -m unittest discover -s tests`
- `uv run ruff check Ortho4XP.py src tests`
- `uv run ruff format --check .`
- `uv run ty check src/O4_Resampling_Policy.py src/O4_Cfg_Vars.py src/O4_Config_Models.py src/O4_Imagery_Utils.py src/O4_Texture_Conversion_Utils.py src/O4_Geotag.py src/O4_DEM_Utils.py src/O4_Airport_Geometry.py`
- `uv run python .codex/skills/quality-check/scripts/quality_check.py --skip-native`

## Tracking

TODO-031 currently has no GitHub issue link in `TODO.md`. Implementation must
create a GitHub issue for TODO-031 and add the issue number to `TODO.md` before
marking the item complete.
