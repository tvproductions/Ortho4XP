# TODO-032 In-Memory VRT Pipeline Design

## Context

TODO-032 follows the GDAL Python bindings migration, the nvcompress flag
upgrade, async tile downloads, and the per-stage resampling policy. The active
texture build path still uses a two-stage cache contract:

1. `O4_Texture_Download_Scheduler.async_download_textures()` calls
   `O4_Imagery_Utils.async_build_jpeg_ortho()`.
2. `build_jpeg_ortho()` and `download_jpeg_ortho()` assemble a complete
   orthophoto and write it as a cached JPEG under `Orthophotos/...`.
3. The conversion queue stores only `(tile, til_x_left, til_y_top, zoomlevel,
   provider_code)`.
4. `O4_Imagery_Utils.convert_texture()` reopens the cached JPEG, optionally
   applies normalization, provider color filters, and alpha-mask imprinting,
   writes a temporary PNG when needed, then hands a file path to the DDS or
   GeoTIFF converter.

That cache boundary makes the pipeline easy to inspect and supports manual
retouch workflows, previews, combined providers, and GeoTIFF export. It also
means the normal active DDS build writes and rereads a full 4096px texture
before conversion. TODO-032 removes that avoidable intermediate file from the
active DDS path without breaking workflows that intentionally depend on cached
JPEGs.

The local development environment was checked before writing this design:
`uv run python -c "from osgeo import gdal; print(gdal.VersionInfo('--version'))"`
reported GDAL 3.12.2, and a minimal `gdal.BuildVRT('/vsimem/test_vrt.vrt',
[mem_dataset])` probe succeeded. The implementation can therefore use GDAL's
`/vsimem/` filesystem for VRT XML datasets while keeping source rasters in
`MEM` datasets.

## Goals

- Add an active DDS texture path that carries completed imagery in memory from
  download/build into conversion.
- Use GDAL `MEM` datasets and `/vsimem/` VRTs for source fragment assembly when
  a texture source is represented as georeferenced fragments.
- Keep final encoder handoff file-based because `nvcompress` and `DDSTool`
  consume file paths.
- Preserve the existing cached JPEG path for previews, manual retouch,
  combined-provider layer assembly, explicit cache rebuilds, and GeoTIFF export.
- Preserve retry, incomplete-texture, failure-summary, normalization,
  color-filter, alpha-mask, and conversion-scheduler behavior.
- Add deterministic `unittest` coverage for in-memory source artifacts, VRT
  assembly, queue handoff, conversion without a cached JPEG, and legacy fallback.

## Non-Goals

- Do not remove `Orthophotos/` or the user-visible cached JPEG workflow.
- Do not change generated DDS, TER, DSF, mask, or GeoTIFF filenames.
- Do not require real network access, imagery providers, X-Plane installs, or
  external DDS encoders in tests.
- Do not rewrite combined-provider compositing in the first implementation
  slice; combined providers continue to use the cached layer files they already
  depend on.
- Do not make COG export, DDS quality metrics, sharpening, provider scoring, or
  failover part of this TODO.
- Do not add a new runtime dependency.

## Scope Boundary

The first implementation targets the active Step 3 DDS texture flow for normal
providers in `providers_dict`. It should be used when the scheduler builds a
texture solely to convert it in the same run.

The existing cached path remains the source of truth when:

- A caller invokes `build_jpeg_ortho()` or `download_jpeg_ortho()` directly.
- `skip_converts` or manual retouch behavior requires JPEGs to remain on disk.
- A provider is a local combined provider and its layers are resolved from
  cached source orthophotos.
- `convert_texture(..., type="tif")` is exporting GeoTIFFs.
- A conversion queue item is in the legacy tuple format.

This boundary removes the avoidable cache write from the main DDS build while
keeping user workflows and existing public helper functions stable.

## Architecture

Create `src/O4_Texture_Source.py` as the explicit handoff contract between
texture building and texture conversion. It should define immutable data
objects rather than passing loosely shaped tuples through queues.

Core objects:

- `TextureSource`: successful in-memory source for one texture. It stores
  `tile`, texture attributes, provider code, a `PIL.Image.Image`, an optional
  cache path used only for legacy neighbor lookup, and a `wrote_cache` flag.
- `TextureBuildResult`: success/failure wrapper returned by streaming build
  helpers. It stores the texture attributes, optional `TextureSource`,
  incomplete/failure metadata, and a compatibility `ok` property.

Create `src/O4_GDAL_Texture_Pipeline.py` for GDAL memory/VRT helpers. This
module should stay small and own only GDAL dataset construction, VRT cleanup,
and conversion back to Pillow/NumPy-compatible images.

Core helpers:

- `memory_dataset_from_image(image, bbox, epsg)`: convert a Pillow image to a
  GDAL `MEM` dataset with geotransform and projection.
- `build_vsimem_vrt(sources, *, vrt_name=None)`: build a VRT at
  `/vsimem/ortho4xp/...` from source datasets and return a context object that
  cleans up with `gdal.Unlink()`.
- `warp_vrt_to_image(vrt_dataset, target_bbox, target_epsg, target_size,
  resampling)`: call `gdal.Warp(format="MEM")` and return a Pillow image.

`O4_Imagery_Utils` should extract the current complete-image assembly logic
behind a shared helper:

- `build_ortho_image(tile, til_x_left, til_y_top, zoomlevel, provider_code,
  *, super_resol_factor=1) -> TextureBuildResult`

`download_jpeg_ortho()` should keep its current public behavior by calling the
shared helper and saving the returned image. The new streaming scheduler path
should call:

- `build_texture_source(tile, til_x_left, til_y_top, zoomlevel, provider_code,
  *, persist_cache=False) -> TextureBuildResult`

When `persist_cache=False`, the helper must not write the full orthophoto JPEG.
When `persist_cache=True`, it may save the image through the same path as the
legacy cache workflow. The default active DDS scheduler path uses
`persist_cache=False`.

## Data Flow

Normal active DDS flow after TODO-032:

1. DSF generation enqueues texture attributes as it does today.
2. The download scheduler calls `async_build_texture_source()` instead of
   `async_build_jpeg_ortho()` for active DDS work.
3. The build helper downloads provider fragments, assembles or warps the
   complete 4096px image in memory, and returns `TextureBuildResult`.
4. On success, the download scheduler enqueues `(tile, texture_source)` for
   conversion.
5. The conversion scheduler accepts both `(tile, texture_source)` and the
   legacy `(tile, x, y, zl, provider)` tuple.
6. `convert_texture(..., texture_source=source)` uses `source.image` directly,
   applies normalization/color filters/masks as needed, writes the required
   temporary PNG for the DDS encoder, and deletes that temporary PNG after the
   encoder returns.

Legacy flow remains valid:

1. `build_jpeg_ortho()` writes the cached JPEG.
2. A legacy conversion queue item or direct `convert_texture()` call reopens
   the cached JPEG path.
3. GeoTIFF export and combined-provider workflows continue through their
   current cache-based paths.

## GDAL VRT Behavior

The implementation should not force every existing Pillow paste operation
through GDAL at once. It should introduce GDAL VRT helpers and route the
georeferenced fragment path through those helpers where the provider path
already computes source bounding boxes and target bounds.

`/vsimem/` VRTs must be treated as managed temporary resources:

- Use unique names under `/vsimem/ortho4xp/`.
- Close dataset handles before unlinking.
- Always call `gdal.Unlink(vrt_path)` in a `finally` block or context manager.
- Tests should prove cleanup is attempted even when warp fails.

The existing `warp_image_with_gdal()` helper can remain for call sites that
already have a single Pillow image. VRT assembly should be introduced as a
separate helper so future work can migrate more provider request types without
destabilizing the active DDS conversion change.

## Normalization and Cache Compatibility

Color normalization currently discovers neighboring textures by looking in the
provider cache directory. Streaming should not remove that capability. A
streaming `TextureSource` may carry the provider cache directory as
`neighbor_cache_dir` even when the current texture was not written there.

When normalization is enabled:

- The current streaming image is normalized in memory.
- Neighbor lookup uses existing cache files if present.
- Missing neighbors are skipped exactly as today.
- The current texture does not need to be written to cache merely to normalize
  itself.

Combined-only providers without a concrete provider cache directory should keep
the current skip log behavior.

## Error Handling

The new streaming build helper should preserve current failure semantics:

- `UI.red_flag` returns an interrupted/failed result without queuing
  conversion.
- Partial imagery failure still records an incomplete texture through the
  existing imagery failure registry.
- Download retry behavior remains owned by
  `O4_Texture_Download_Scheduler`.
- Conversion failures return the existing `TextureConversionResult` shape.
- GDAL VRT or warp failure should produce a clear `RuntimeError` message at the
  helper boundary and be converted into the same failed texture summary path as
  other build failures.

Queue consumers must remain backward compatible. If a conversion queue item has
the legacy five-field shape, conversion must use the cached JPEG path. If it
has `(tile, TextureSource)`, conversion must use the streaming image.

## Testing

Tests must use `unittest` only.

Add focused tests for:

- `TextureSource` and `TextureBuildResult` validation and compatibility
  properties.
- `O4_GDAL_Texture_Pipeline.memory_dataset_from_image()` preserving image mode,
  geotransform, projection, band count, and pixel values.
- `/vsimem/` VRT construction from one or more `MEM` datasets and cleanup with
  `gdal.Unlink()`.
- `build_texture_source(..., persist_cache=False)` returning an in-memory image
  and not saving a cached JPEG.
- `download_jpeg_ortho()` still saving a cached JPEG through the shared helper.
- `async_download_textures()` enqueueing `(tile, TextureSource)` for DDS work
  and preserving retry/failure summaries.
- `TextureConversionJob.from_queue_item()` accepting both streaming and legacy
  queue items.
- `convert_texture(..., texture_source=source)` converting from the in-memory
  image when the cached JPEG is missing.
- Streaming conversion applying normalization before color filters and applying
  alpha masks before DDS encoding.
- GeoTIFF export and direct legacy conversion continuing to use cached input.

Verification commands:

- `uv run python -m unittest tests.test_texture_source tests.test_gdal_texture_pipeline tests.test_texture_async_downloads tests.test_texture_conversion_scheduler tests.test_imagery_convert_color_normalization -q`
- `uv run python -m unittest discover -s tests`
- `uv run ruff check Ortho4XP.py src tests`
- `uv run ruff format --check .`
- `uv run ty check src/O4_Texture_Source.py src/O4_GDAL_Texture_Pipeline.py src/O4_Imagery_Utils.py src/O4_Texture_Download_Scheduler.py src/O4_Texture_Conversion_Scheduler.py src/O4_Texture_Conversion_Runner.py`
- `uv run python .codex/skills/quality-check/scripts/quality_check.py --skip-native`

## Tracking

TODO-032 is tracked by GitHub Issue #35. Implementation should post evidence
when acceptance criteria pass and close the issue only after the repository
quality gate has passed or an explicitly tracked blocker is recorded.
