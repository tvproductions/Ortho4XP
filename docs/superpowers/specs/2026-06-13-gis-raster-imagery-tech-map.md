# GIS, Raster, and Imagery Technology Map

Date: 2026-06-14 (revised; original 2026-06-13)
Issue: TODO-026 / GHI #30

## Tool Selection Decisions (made during TODO-026 review)

| Tool | Decision | Rationale |
|------|----------|-----------|
| **GDAL** | `osgeo.gdal` hard dependency; in-memory VRT pipeline; remove CLI subprocess calls | In-process error handling, VRT graphs, COG export, no temp files; 3.9+ has Py3.13 wheels on all platforms |
| **DDS encoder** | nvcompress (Win/Lin), DDSTool (macOS) | nvcompress `-highest` + Kaiser + alpha dithering is best BC1/BC3 encoder available; NVIDIA ships no NVTT for macOS |
| **Pillow** | Keep for pixel ops (color filters, mask compositing, normalization) | GDAL not suited for per-pixel image processing |
| **NumPy** | Keep for sRGB/linear math, array processing | Already in use, no alternative |
| **OpenCV** | Deferred — evaluate only when histogram matching or feature-based tile alignment is needed | Pillow covers current needs; OpenCV is a 100+ MB dependency with mixed Py3.13 wheel availability |
| **Async downloads** | aiohttp + asyncio replacing requests + ThreadPoolExecutor | Native async, fewer threads, backpressure for hundreds of concurrent tile downloads |
| **Architecture leap** | Stream tiles HTTP → VRT stitch → warp → color → normalize → DDS, zero intermediate files | See §7.9 |

## 1. Purpose & Scope

This document inventories the GIS, raster, and imagery toolchain used by Ortho4XP,
traces the end-to-end data flow from provider download through to DDS/GeoTIFF
output, documents current assumptions about CRS, resampling, compression, and
alpha handling, and recommends concrete follow-up issues.

Scope covers the production pipeline for orthophoto textures, masks, GeoTIFFs,
and the raster data they feed into DSF generation (elevation, bathymetry,
texture references, mask layers). Detailed DSF encoding internals (text format,
patches, properties) are covered by TODO-017; this document focuses on the
raster inputs and format constraints that DSF encoding depends on.

## 2. Active Tools and Libraries

### 2.1 GDAL (osgeo.gdal Python bindings)

**Decision (TODO-026)**: `osgeo.gdal` is adopted as a **hard runtime dependency**.
CLI subprocess calls (`gdal_translate`, `gdalwarp`) are eliminated in favor of
in-process Python bindings. This provides:

- Native Python error handling (exceptions instead of CLI stderr parsing)
- In-memory VRT graphs for stitching, cropping, and reprojection
- COG-compatible export (tiled, overviews, internal masks)
- No temporary files for intermediate GeoTIFF stages
- Uniform cross-platform story: PyInstaller bundles include GDAL DLLs;
  `uv`/pip users get platform wheels from PyPI

**Delivery**:
- PyInstaller release bundles: GDAL shared libraries + `osgeo` bindings staged
  per platform
- Source/`uv` users: `gdal` added to `pyproject.toml` dependencies; modern GDAL
  3.9+ provides `manylinux`/`macosx` wheels for Python 3.13 on all three targets

**Previous CLI invocations** (being replaced):

| Location | Command | Purpose |
|----------|---------|---------|
| `O4_Texture_Conversion_Utils.py:80-126` | `gdal_translate -of Gtiff -co COMPRESS=JPEG -a_ullr <lonmin> <latmax> <lonmax> <latmin> -a_srs epsg:4326 <input> <output>` | Direct GeoTIFF tagging (span < 0.04 deg) |
| `O4_Texture_Conversion_Utils.py:129-146` | `gdal_translate -of Gtiff -co COMPRESS=JPEG -a_ullr <xmin> <ymax> <xmax> <ymin> -a_srs epsg:3857 <input> <tmp>` | Geotag raw image to Web Mercator |
| `O4_Texture_Conversion_Utils.py:149-166` | `gdalwarp -of Gtiff -co COMPRESS=JPEG -s_srs epsg:3857 -t_srs epsg:4326 -ts 4096 4096 -rb <tmp> <output>` | Reproject 3857 to 4326, crop to 4096 |
| `O4_Imagery_Utils.py:2487-2521` | `gdal_translate -of Gtiff -co COMPRESS=JPEG -a_ullr ... -a_srs epsg:4326` | Standalone geotag (legacy path) |
| `O4_Geotag.py:30-65` | `gdal_translate` + `gdalwarp` | Standalone script for batch JGP geotagging |

GDAL is always called as a subprocess (via `subprocess_helper`). No GDAL Python
bindings are used at runtime. `osgeo.gdal` is imported optionally in
`O4_DEM_Utils.py` for DEM raster reading with a fallback path.

### 2.2 Pillow (PIL)

**Used in 16 source files**. Imports range from `Image` and `ImageDraw` to
`ImageEnhance`, `ImageFilter`, `ImageOps`, and `ImageTk`.

Primary roles:
- Provider download assembly: `Image.new()`, `.paste()` for tile mosaics
- Cache read: `Image.open()` for cached JPEG orthophotos
- Mask creation: `ImageDraw.Draw()`, `.polygon()`, `.point()`
- Color transforms: `ImageEnhance.Color()`, `ImageEnhance.Sharpness()`,
  `ImageFilter.GaussianBlur()`, `.point()` for brightness/contrast/levels
- Alpha channel: `.putalpha()` for mask imprinting
- Compositing: `Image.composite()`, `Image.blend()`
- Array bridge: `Image.fromarray(numpy_array)`, `numpy.asarray(pil_image)`
- Format conversion: `.convert("RGB")`, `.convert("L")`, `.convert("RGBA")`

### 2.3 NumPy

**Used in ~18 source files**. Array-based pixel processing for masks,
sRGB/linear conversions, DEM data arrays, bathymetry, DSF encoding, and
provider resolution calculations.

### 2.4 DDS Encoders

**Decision (TODO-026)**: Platform-appropriate encoder selection:

| Platform | Encoder | Path | Rationale |
|----------|---------|------|-----------|
| **Windows** | `nvcompress.exe` + `nvtt30205.dll` | `Utils/win/nvcompress/` | NVIDIA SDK 3.2.5, full `-highest` + CUDA |
| **Linux** | `nvcompress` + `libnvtt.so.30205` | `Utils/lin/nvcompress` | NVIDIA SDK 3.2.5, full `-highest` |
| **macOS** | `DDSTool` | `Utils/mac/DDSTool` | NVIDIA ships no NVTT for macOS; DDSTool is Laminar-maintained and X-Plane-native |

**Rationale**: X-Plane 12 supports BC1/DXT1 and BC3/DXT5 only (no BC7).
Within those constraints, nvcompress delivers maximum quality:
- `-highest` preset: optimal endpoint search minimizes banding and block artifacts
- `-mipfilter kaiser`: preserves high-frequency detail at distance (superior to
  box or triangle filters)
- `-alpha_dithering`: reduces alpha stepping artifacts in BC3 smooth gradients
- CUDA acceleration available via `-cuda` for faster encoding

**Commands** (updated):
- No alpha: `nvcompress -bc1 -highest -alpha_dithering -mipfilter kaiser <input.png> <output.dds>`
- With alpha: `nvcompress -bc3 -highest -alpha_dithering -mipfilter kaiser -alpha <input.png> <output.dds>`

Retry policy: up to 10 attempts with 1-second sleep between failures.
Valid codecs: `"bc1"` (DXT1/BC1, no alpha), `"bc3"` (DXT5/BC3, with alpha).

### 2.5 Other Dependencies

| Library | File | Role |
|---------|------|------|
| `skfmm` (scikit-fmm) | `O4_Mask_Utils.py:9,197` | Fast marching distance transform for signed-distance mask fields |
| `pyproj` | `O4_Geo_Utils.py:2,48-84` | CRS definitions, coordinate transforms (4326 ↔ 3857) |
| `requests` | `O4_Imagery_Utils.py:17` | HTTP download of WMTS/TMS imagery tiles |
| `io.BytesIO` | `O4_Imagery_Utils.py:1026` | In-memory JPEG decode of HTTP responses |
| `concurrent.futures` | `O4_Imagery_Utils.py` (download), `O4_Tile_Utils.py` (texture encode) | ThreadPoolExecutor for parallel downloads (up to 16 threads) and parallel DDS encoding |

No ImageMagick (`convert`) usage is present in any Python source.

## 3. Imagery and Raster Data Flow

### 3.1 End-to-End Pipeline

```
STEP 1: Download → Cache JPEGs
    │
    ├── build_jpeg_ortho()          [O4_Imagery_Utils.py:1643]
    │   ├── download_jpeg_ortho()   [O4_Imagery_Utils.py:1553]
    │   │   └── build_texture_from_tilbox() or build_texture_from_bbox_and_size()
    │   │       ├── Downloads 256×256 WMTS/TMS tiles in parallel (16 threads)
    │   │       ├── Assembles into 4096×4096 RGB Image via .paste()
    │   │       └── Optionally warps via gdalwarp_alternative() if CRS differs
    │   └── combine_textures()      (for combined/mask providers)
    │       └── Composite RGBA layers with mask priority
    │
    v
STEP 2: Convert → DDS or GeoTIFF
    │
    ├── convert_texture()            [O4_Imagery_Utils.py:2307]
    │   ├── color_transform()        [O4_Imagery_Utils.py:2108]
    │   │   └── Per-provider filter: brightness/contrast, saturation,
    │   │       sharpness, blur, levels
    │   ├── normalize_texture_image_if_enabled()  [O4_Texture_Color_Normalization.py]
    │   │   └── sRGB edge statistics, neighbor comparison
    │   ├── putalpha(mask)           (if imprint_masks_to_dds)
    │   │
    │   ├── DDS path → convert_dds_texture()
    │   │   └── NativeTextureEncoderBackend.encode()
    │   │       └── nvcompress or DDSTool subprocess
    │   │
    │   └── GeoTIFF path → convert_geotiff_texture()
    │       └── gdal_translate ± gdalwarp subprocess
    │
    v
STEP 3: DSF build references .dds files on disk

STEP 2.5 (parallel): Mask Generation
    │
    └── build_masks()               [O4_Mask_Utils.py:71]
        ├── build_dem_pre_mask()    [O4_Mask_Utils.py:357]
        │   └── gdalwarp_alternative() (Pillow-based, DEM 4326→3857)
        ├── build_custom_pre_mask() [O4_Mask_Utils.py:396]
        │   └── OSM extent masks
        ├── Combine water-tri + DEM + custom masks → 6144×6144 array
        ├── skfmm.distance()        (signed-distance field)
        └── Write 4096×4096 grayscale PNG masks
```

### 3.2 GDAL vs. Pillow Decision Points

| Operation | GDAL Path (post-TODO-026) | Pillow Path | Decision |
|-----------|---------------------------|-------------|----------|
| DEM reading | `gdal.Open()` (hard dependency) | ViewFinderPanoramas directory walk (legacy fallback) | GDAL primary; remove no-GDAL path |
| Raster reprojection | `gdal.Warp()` via Python bindings | `gdalwarp_alternative()` (legacy) | GDAL only; remove Pillow reprojection |
| GeoTIFF export | In-memory `gdal.Warp()` + `gdal.Translate()` | N/A | GDAL only (was already GDAL) |
| COG export | `gdal.Translate(co=TILED=YES,...)` + overviews | N/A | New capability, GDAL |
| VRT stitching | `gdal.BuildVRT()` | N/A | New capability, GDAL |
| Mask reprojection (DEM→3857) | `gdal.Warp()` to array | `gdalwarp_alternative()` (legacy) | GDAL primary; remove Pillow path |
| Provider tile assembly | N/A | Pillow `.paste()` | Always Pillow |
| Color manipulation | N/A | Pillow `ImageEnhance`, `.point()` | Always Pillow |
| sRGB normalization | N/A | NumPy + Pillow | Always NumPy/Pillow |
| DDS encoding | N/A | nvcompress (Win/Lin) or DDSTool (macOS) external | External process with `-highest` / native SDK tool |

**`gdalwarp_alternative()`** (`O4_Imagery_Utils.py:2058-2101`):
Takes `(s_bbox, s_epsg, s_im, t_bbox, t_epsg, t_size)`. Uses
`pyproj.Transformer` (inverse) to map target pixels to source. Splits into 8x8
grid of quads, computes 4 corner positions per quad, calls
`Image.transform(Image.Transform.MESH, ..., BICUBIC)`.

### 3.3 Provider Download Details

- Tile size: 256×256 pixels (WMTS/TMS standard)
- Output texture size: 4096×4096 pixels
- Parallelism: `ThreadPoolExecutor` with up to 16 workers
- Cache format: JPEG, stored in `Orthophotos/<lat>_<lon>/<code>_<zl>/`
- Failed tiles: filled with white (`Image.new("RGB", ..., "white")`)
- Incomplete textures tracked via `record_incomplete_texture()`

### 3.4 Raster Data Consumed by DSF Generation

The DSF encoding layer (`O4_DSF_Utils.py`) consumes several raster types that
the imagery and mesh pipelines produce. These types constrain texture and mask
format decisions:

| Raster | Source | Format in DSF | Pipeline relevance |
|--------|--------|---------------|-------------------|
| **Elevation DEM** | `O4_Mesh_Utils.py` / `O4_DEM_Utils.py` | 16-bit signed integer grid (elevation in meters) | GDAL reads; bathymetry validation depends on sea_level raster; nodata handling must match DSF expectations |
| **Bathymetry DEMS** | `O4_Bathymetry.py` | 16-bit signed integer grid (water depth in meters, negative values) | Required for XP12 3D water; `water_tech = "XP12"` enforced in §7.4 GDAL migration must keep array precision |
| **Texture references** | DSF header from `build_jpeg_ortho` output paths | Relative path to `.dds` in generated package | Determines DDS naming convention; mask overlay vs. alpha-in-DDS choice affects DSF texture layer encoding |
| **Overlay mask** | `O4_Mask_Utils.py` | Either separate `.dds` overlay terrain (no alpha in main texture) or alpha channel in main texture DDS (BC3) | The `imprint_masks_to_dds` flag routes between these two; DSF encoding reads it to decide texture layer layout |
| **Landclass / seasons** | Spliced from default XP12 DSF header (TODO-017) | Inherited header properties | Not a raster output; DSFTool bridge splices these without changing the imagery pipeline |

**Key constraint**: The DSF elevation grid uses 16-bit signed integers with
either a hardcoded `-32768` nodata sentinel or GDAL-read nodata values. The
bathymetry raster must use negative values that are valid 16-bit signed
integers. The texture DDS format (BC1 vs BC3) must match what the DSF texture
layer expects — DSF does not remap texture formats at load time.

## 4. CRS and Projection Model

### 4.1 Active Coordinate Systems

| EPSG | Name | Usage |
|------|------|-------|
| 4326 | WGS84 (geographic) | Tile bounding boxes, DEM data, final GeoTIFF output, DSF coordinates |
| 3857 | Web Mercator | Tile download grid, intermediate GeoTIFF staging, mask reprojection target |

Pre-cached `pyproj.CRS` objects in `O4_Geo_Utils.py:48-50`:

```python
epsg = {4326: CRS.from_epsg(4326), 3857: CRS.from_epsg(3857)}
```

### 4.2 Provider CRS

Providers declare CRS via `"epsg_code"` in `.lay.json`. Common values:
- `3857` — Google/Bing/OSM Web Mercator
- `4326` — WMS/WMTS geographic
- `2154` — France Lambert-93
- `3003` — Italy Gauss-Boaga
- `3912` — Slovenia

Web Mercator grid providers (`"grid_type": "webmercator"`) auto-assign `3857`.

### 4.3 Transformers

- `transformer(s_epsg, t_epsg)` — general CRS-to-CRS via `pyproj.Transformer.from_crs(always_xy=True)`
- `transform(s_epsg, t_epsg, s_x, s_y)` — single-point transform
- `geo_to_webm(lon, lat)` — 4326→3857 shortcut

Always use easting/northing order (`always_xy=True`).

### 4.4 Known Gaps

- No explicit CRS validation on provider definitions beyond EPSG code lookup
- Pillow-based `gdalwarp_alternative()` uses simple inverse-mapping MESH transform;
  no rigorous geolocation error bounds are computed or logged
- No WKT/WKT2 export capability for generated GeoTIFFs (always EPSG:4326)

## 5. Resampling, Nodata, Alpha, Mask, and Compression

### 5.1 Resampling

**BICUBIC is the only resampling method used.** 14 confirmed occurrences:
mask resizing, texture resize, color normalization mask resize,
`gdalwarp_alternative()` mesh transform, `combine_textures()` crop+resize.

**No configuration surface** for selecting between NEAREST, BILINEAR, BICUBIC,
LANCZOS, or other methods. This is a gap: different stages (mask downsampling
vs. texture reprojection) may benefit from different resamplers.

### 5.2 Nodata Handling

| Context | Sentinel | Treatment |
|---------|----------|-----------|
| DEM (default) | `-32768` | `fill_nodata=True`: nearest-neighbor inpainting (iterative, up to 10000 px); `fill_nodata="to zero"`: replace with 0; `fill_nodata=False`: leave as-is |
| DEM (no-GDAL fallback) | `-32768` | No fallback to GDAL's `GetNoDataValue()` |
| Imagery download failure | N/A | White tile fill; tracked via `record_incomplete_texture()` |

**Known gaps**:
- GDAL nodata values are read from raster bands but the no-GDAL fallback
  hardcodes `-32768` without validation
- No nodata handling for GeoTIFF output: imagery GeoTIFFs are opaque RGB,
  missing data is not explicitly flagged

### 5.3 Alpha Channel

| Mode | Codec | Condition |
|------|-------|-----------|
| No alpha (DSF overlay) | BC1/DXT1 | Default (`dxt5=False`) |
| Alpha in DDS (mask imprint) | BC3/DXT5 | `imprint_masks_to_dds=True` |

- When active: mask is resized via BICUBIC to 4096×4096, then
  `big_image.putalpha(mask_im)`
- Progressive log alpha blend: `O4_Mask_Alpha.py` provides
  `progressive_log_alpha_ratio()` for smooth sea-land transitions
- DSF reads `tile.imprint_masks_to_dds` to decide overlay vs. alpha path

### 5.4 Mask Format

- Grayscale PNG (8-bit, "L" mode)
- Stored in `Masks/<lat>_<lon>/`
- Naming: `<y>_<x>_ZL<zoomlevel>.png` (and legacy `<y>_<x>.png`)
- Water transition: `water_transition.png` in `Utils/` (sea-level lookup table)
- Internal size during generation: 6144×6144; final output: 4096×4096
- Distance field via `skfmm.distance()` after combining water-tri, DEM, custom masks

### 5.5 Compression

| Output Type | Compression | Details |
|-------------|-------------|---------|
| GeoTIFF | JPEG | `-co COMPRESS=JPEG` (GDAL default JPEG quality, ~75) |
| DDS (no alpha) | BC1/DXT1 | `-bc1 -highest -alpha_dithering -mipfilter kaiser` |
| DDS (with alpha) | BC3/DXT5 | `-bc3 -highest -alpha_dithering -mipfilter kaiser -alpha` |
| JPEG cache | Standard JPEG | No explicit quality in `save()` (Pillow default ~75) |

**Known gaps**:
- No DDS compression validation or visual quality comparison between presets
- JPEG quality in `save()` is left at Pillow default; line 2417 has a
  commented-out `quality=70` indicating prior awareness
- No compression-aware image QA (e.g., PSNR/SSIM comparison between source PNG
  and compressed DDS)

## 6. Custom Color Processing

### 6.1 Per-Provider Color Filters (`.flt.json`)

Located in `Filters/`. Seven files define filter chains:

| File | Operations |
|------|-----------|
| `GeoPunt2012.flt.json` | `levels` (per-channel gamma), `brightness-contrast` (-25, +10) |
| `SEA.flt.json` | `brightness-contrast` (-30, +10) |
| `SP_2015.flt.json` | `levels` (per-channel in/out clipping) |
| `Itris.flt.json` | `brightness-contrast` (-40, +15), `saturation` (+30) |
| `PCN06.flt.json` | `levels` (per-channel), `saturation` (-30) |
| `PCN06_N46E011.flt.json` | `levels` (per-channel gamma), `brightness-contrast` (-20, +20) |
| `AltoAdige1415.flt.json` | `brightness-contrast` (-20, 0) |

**Supported operations** (in `O4_Color_Filters.py`, reached through
`O4_Imagery_Utils.color_transform()`):
- `brightness-contrast`: GIMP-style tangent curve, params `[brightness, contrast]`
- `saturation`: `ImageEnhance.Color().enhance(1 + sat/100)`
- `sharpness`: `ImageEnhance.Sharpness().enhance(value)`
- `sharpen`: `ImageFilter.UnsharpMask(radius, percent, threshold)`, params
  `[radius, amount, threshold]`
- `blur`: `ImageFilter.GaussianBlur(radius)`
- `levels`: Per-channel `[in_min, gamma, in_max, out_min, out_max]` via `.point()`

### 6.2 sRGB Color Normalization (TODO-016)

**Modules**:
- `O4_Srgb_Color.py`: `srgb_to_linear_array()` / `linear_to_srgb_array()`
  (standard sRGB transfer function via NumPy)
- `O4_Color_Correction.py`: `derive_color_correction()` from edge-pair
  statistics; `apply_color_correction()` with 65% blend strength
- `O4_Color_Normalization.py`: `normalize_image_with_neighbors()` — samples
  32-pixel edge bands, derives exposure + per-channel scale
- `O4_Texture_Color_Normalization.py`: Texture-cache integration, discovers
  neighbor cached JPEGs, skips missing/incomplete/known-failure tiles

**Enabled via**: `normalize_texture_colors` flag (`O4_Imagery_Utils.py:73`)

**Invocation points in `convert_texture()`**:
1. Combined providers → `normalize_combined_texture_image()`
2. Plain with color filter or mask → `normalize_texture_image_if_enabled()`
3. Plain with no other processing → `normalized_conversion_input_path()`

### 6.3 Sea Texture Blur

Config variable `sea_texture_blur` (`O4_Cfg_Vars.py:301`): when set for a
mask-priority layer, applies `GaussianBlur(radius * 2**(true_zl - 17))` before
compositing.

## 7. Staged Opportunities

Each opportunity is rated by expected impact (High/Medium/Low) and estimated
effort (Small/Medium/Large).

### 7.1 GDAL VRT Usage (Medium impact, Medium effort)

**Observation**: GDAL is used only via direct CLI invocations on individual
files. Virtual Raster (VRT) format is never used.

**Opportunity**: Use VRT as an intermediate stitching/cropping layer before
final GeoTIFF export. Benefits:
- Avoid copying raster data during assembly
- Enable on-demand reprojection without intermediate files
- Support overviews for debug/QA exports

**Risk**: Adds GDAL VRT dependency that may not be stable across GDAL versions.

### 7.2 Explicit Resampling Policy (Medium impact, Small effort)

**Decision**: Per-stage defaults with optional config overrides.

| Stage | Default | Rationale |
|-------|---------|-----------|
| Texture downscale (provider → 4096) | LANCZOS | Sharper than BICUBIC for downscaling continuous-tone imagery |
| Mask resize (6144 → 4096) | NEAREST | Preserves hard water/land boundaries |
| Reprojection warp (`gdal.Warp()`) | BICUBIC | Standard for continuous-tone raster reprojection |
| Normalization edge sampling (32px bands) | BILINEAR | Acceptable smoothness for mean/luminance statistics |

Exposed per-stage via config with safe defaults.

### 7.3 Cloud-Optimized GeoTIFF (COG) Exports (Low impact, Small effort)

**Decision**: Add optional COG mode via config flag. When enabled:
`gdal.Translate(co=TILED=YES, BLOCKXSIZE=512, BLOCKYSIZE=512)` + internal
masks + `gdal.AddOverview()`. Trivial with `osgeo.gdal` hard dependency.

### 7.4 GDAL Python Bindings — Hard Dependency (Committed, Large effort)

**Decision**: `osgeo.gdal` replaces all GDAL CLI subprocess calls and the
optional import pattern. The Pillow-based `gdalwarp_alternative()` in both
`O4_Imagery_Utils.py` and `O4_Mask_Utils.py` is removed in favor of
`gdal.Warp()`.

**Scope of work**:
1. Make `osgeo.gdal` a hard `pyproject.toml` dependency
2. Replace `gdal_translate`/`gdalwarp` subprocess calls in
   `O4_Texture_Conversion_Utils.py` with direct binding calls
3. Replace `gdalwarp_alternative()` in `O4_Imagery_Utils.py` with `gdal.Warp()`
4. Replace `gdalwarp_alternative()` in `O4_Mask_Utils.py` with `gdal.Warp()`
   to array
5. Make `osgeo.gdal` import unconditional in `O4_DEM_Utils.py`
6. Add VRT-based assembly for provider tile stitching (no intermediate JPEGs)
7. Add COG export capability with tiling and overviews
8. Add GDAL to PyInstaller packaging for all three platforms
9. Remove `resolve_tool("gdal_translate")` and `resolve_tool("gdalwarp")` from
   `O4_External_Tool_Paths.py`
10. Update tests

**Risk mitigation**: GDAL 3.9+ publishes Python 3.13 wheels for Windows (x64),
macOS (x86_64 + arm64), and Linux (x86_64 + aarch64). PyInstaller bundles
stage the shared libraries. No risk of missing wheels at this point.

### 7.5 OpenCV Integration (Deferred — Low impact now, Large effort)

**Observation**: All pixel processing uses Pillow + NumPy. No OpenCV usage.

**Decision (TODO-026)**: OpenCV adoption is **deferred**. Pillow + NumPy covers
all current pixel-processing needs:
- Brightness/contrast/saturation/levels — Pillow `ImageEnhance` / `.point()`
- Gaussian blur — Pillow `ImageFilter.GaussianBlur()`
- Unsharp mask — Pillow `ImageFilter.UnsharpMask()`
- sRGB normalization — NumPy array math

**Gate for adding**: OpenCV is adopted when one of:
1. Edge-statistic color normalization proves insufficient and per-channel
   histogram matching is required
2. Multi-provider tile stitching with feature detection (SIFT/ORB) is added
3. Per-tile processing becomes a CPU bottleneck AND CUDA is available

**Risk on add**: 100+ MB dependency, mixed Py3.13 wheel availability (especially
macOS ARM), CUDA runtime requirement for GPU backend.

### 7.6 Compression-Aware Image QA (Medium impact, Medium effort)

**Decision**: Add optional QA step (disabled by default, toggled via config):
1. Decode compressed DDS to PNG
2. Compare with source PNG using PSNR, SSIM, or MSE
3. Warn if quality drops below configurable threshold

### 7.7 Sharpening / Post-Processing Pipeline (Medium impact, Medium effort)

**Decision**: `"sharpen"` is supported in the color filter pipeline
(`O4_Color_Filters.py`, through `O4_Imagery_Utils.py:color_transform()`).
Parameters `[radius, amount, threshold]` map to Pillow
`ImageFilter.UnsharpMask(radius, percent, threshold)`.

### 7.8 Overview and Pyramided Output (Low impact, Medium effort)

**Observation**: Single-resolution 4096×4096 output only. No overviews in
GeoTIFF output.

**Opportunity**: For GeoTIFF export, generate pyramids via `gdal.AddOverview()`
(part of §7.4 GDAL migration). DDS mipmaps are already handled by nvcompress
(`-mipfilter kaiser` by default).

### 7.9 Async Download Pipeline (Medium impact, Medium effort)

**Decision**: Adopt `aiohttp` + `asyncio` to replace `requests` +
`ThreadPoolExecutor` for tile downloads. Provides native async I/O (no
thread-per-request), connection pooling, backpressure via semaphore, and
easier cancellation. CPU-bound JPEG decoding dispatched via
`asyncio.to_thread()`.

### 7.10 Parallelism Model (Decided)

**Decision**: The async pipeline drives all tile processing as coroutines.
`asyncio.gather()` runs multiple tiles concurrently, each as a single coroutine:

```
process_tile() coroutine:
  1. await tile downloads (aiohttp, async I/O)
  2. await asyncio.to_thread(gdal_warp)   # offload CPU-bound GDAL
  3. color processing inline (NumPy/Pillow, fast enough for main thread)
  4. await asyncio.create_subprocess_exec(nvcompress, ...)  # async subprocess
```

`ThreadPoolExecutor` is retained only as a fallback for nvcompress on platforms
where `create_subprocess_exec` has edge cases. GDAL operates on per-dataset
handles — independent tile warps are safe from multiple coroutines without a
global lock.

### 7.11 Architecture Leap: In-Memory Streaming Pipeline (High impact, Large effort)

**Current flow** (each arrow writes and re-reads from disk):
```
HTTP tiles → JPEG cache → Pillow mosaic → (temp PNG) → GDAL warp
→ GeoTIFF → (temp) → nvcompress → DDS
```

**Target flow** (zero intermediate files):
```
HTTP tiles (aiohttp)
  → asyncio.Stream (BytesIO per tile)
  → GDAL VRT stitch (in-memory)
  → GDAL VRT warp/reproject (in-memory)
  → NumPy array (color filter + normalization)
  → Pillow (mask imprint)
  → nvcompress (temp PNG → DDS)

  ─ OR (GeoTIFF path) ─

  → gdal.Translate in-memory → GeoTIFF
```

**Benefits**:
- Eliminates all intermediate JPEG/PNG/GeoTIFF writes (saves hours per large tile)
- VRT avoids copying raster data during stitching/warping
- Async pipeline begins color processing while tiles still arriving
- Disk I/O drops from GB-scale per tile to near zero

**Implementation path**:
1. Replace `requests` + `ThreadPoolExecutor` with `aiohttp` + `asyncio`
2. Build VRT in-memory from tile BytesIOs via `gdal.BuildVRT()`
3. Replace `color_transform()` with Pillow-on-array from VRT-warped NumPy array
4. Stream to nvcompress from temp PNG or investigate stdin support
5. Remove intermediate cache-write paths from `O4_File_Names.py`

## 8. Implementation Roadmap (9 Waves)

The full implementation plan spans 9 waves, ordered by dependency. Each wave
builds on the previous. Within a wave, TODOs can be parallelized where
dependencies allow.

### Wave 1: Foundation

| TODO | Title | Source | Priority | Effort |
|------|-------|--------|----------|--------|
| 028 | GDAL Python bindings migration | §7.4 | Critical | Large |
| 029 | nvcompress `-highest -mipfilter kaiser -alpha_dithering` flags | §2.4 | High | Small |

### Wave 2: Async + Config

| TODO | Title | Source | Priority | Effort |
|------|-------|--------|----------|--------|
| 030 | aiohttp + asyncio tile downloads | §7.9 | High | Medium |
| 031 | Per-stage resampling policy with config overrides | §7.2 | Medium | Small |

### Wave 3: Streaming Pipeline

| TODO | Title | Source | Priority | Effort |
|------|-------|--------|----------|--------|
| 032 | In-memory VRT pipeline (zero intermediate files) | §7.11 | Critical | Large |
| 033 | COG-style GeoTIFF export with overviews | §7.3 | Low | Small |

### Wave 4: Quality

| TODO | Title | Source | Priority | Effort |
|------|-------|--------|----------|--------|
| 034 | DDS compression QA (PSNR/SSIM thresholds) | §7.6 | Medium | Medium |
| 035 | Unsharp mask sharpening in post-processing | §7.7 | Medium | Medium |

### Wave 5: Architecture

| TODO | Title | Source | Priority | Effort |
|------|-------|--------|----------|--------|
| 036 | Event Bus (TILE_START/PROGRESS/COMPLETE/ERROR/PIPELINE_STEP/CACHE_HIT) | V3 `O4_EventBus` | High | Medium |
| 037 | Pipeline Orchestrator (named steps, timing, status, clean failure) | V3 `O4_Pipeline` | High | Medium |
| 038 | Smart Cache (SHA256 tile params, skip-rebuild if unchanged) | V3 `O4_Dependency` | Medium | Small |

### Wave 6: Intelligence

| TODO | Title | Source | Priority | Effort |
|------|-------|--------|----------|--------|
| 039 | Provider Scoring (noise, compression, clouds, color drift, seam risk) | V3 `O4_Provider_Score` | High | Medium |
| 040 | Provider Failover + blacklist (auto-switch on consecutive failures) | V3 `O4_Provider_Abstraction` | High | Medium |
| 041 | AI Cloud/Seam Detection (3-criteria cloud, 4-edge seam analysis) | V3 `O4_Provider_Score` enhanced | Medium | Medium |

### Wave 7: XP12 Native Features

| TODO | Title | Source | Priority | Effort |
|------|-------|--------|----------|--------|
| 042 | XP12 Materials (auto WET/ROUGHNESS/SPECULAR from imagery analysis) | V3 `O4_XP12_Materials` | High | Medium |
| 043 | Night Continuity (emissive mask from OSM roads/landuse/places) | XP-Ortho-NC | Medium | Large |

### Wave 8: GPU Backend

| TODO | Title | Source | Priority | Effort |
|------|-------|--------|----------|--------|
| 044 | GPU Backend (CUDA via CuPy/PyTorch, silent CPU fallback) | V3 `O4_GPU_Backend` + TODO-018 | High | Large |

### Wave 9: Developer Experience

| TODO | Title | Source | Priority | Effort |
|------|-------|--------|----------|--------|
| 045 | Automatic Backups + Rollback (timestamped, 1-click restore) | V3 `O4_Backup_Manager` | Low | Small |
| 046 | RAM Protection (psutil monitoring, auto-cleanup, cache limits) | V3 `O4_Memory_Manager` | Low | Small |
| 047 | Debug Visualizations (seam risk maps, color compare, blur maps) | V3 `O4_Benchmark` | Low | Medium |
| 048 | Theme Manager (5 themes + customization, cross-platform) | V3 `O4_Theme_Manager` | Low | Small |

### Deferred

| Item | Source | Gate for adoption |
|------|--------|-------------------|
| OpenCV integration | §7.5 | Histogram matching or feature alignment needed, or CUDA GPU backend |
| V3 installer/launcher | V3 | Out of scope — PyInstaller onedir + `uv` toolchain cover distribution |

### Reference Projects

| Project | URL | License | Strategic value |
|---------|-----|---------|----------------|
| ORTHO4XP_V3 (Ypsos/Roland) | `tvproductions/ORTHO4XP_V3` | GPL v3 | Event bus, pipeline orchestrator, smart cache, provider scoring/failover, XP12 materials, GPU backend, backups, RAM protection, debug viz, themes |
| XP-Ortho-NC | `tvproductions/XP-Ortho-NC` | GPL v3 (inherits) | Night Continuity emissive mask pipeline from OSM semantic data |

Both are GPL v3 — license-compatible with this project. Features are onboarded
when the foundation work (GDAL bindings, async pipeline) they depend on is in
place. Where our implementation is superior, we keep ours; where they are ahead,
we borrow and adapt to our architecture.

## 9. Dependency Management

### 9.1 Two Tracks

| Track | Managing | Update mechanism | Examples |
|-------|----------|-----------------|---------|
| **Python packages** | `pyproject.toml` + `uv.lock` | `uv sync --upgrade-package <name>` | skfmm, gdal, aiohttp, pyproj, Pillow, NumPy |
| **Bundled CLI tools** | `Utils/<platform>/` | `updating-bundled-tools` skill | nvcompress, DSFTool, DDSTool, Triangle4XP, 7z, moulinette |

Both tracks must be kept current. Stale Python packages are tracked by
renovate/dependabot policy; stale CLI tools require manual checks via the skill.

### 9.2 Tool Update Management

**Observation**: Bundled tools (nvcompress, DDSTool, DSFTool, Triangle4XP, 7z,
moulinette) have no automated update mechanism. Versions drift as upstream
releases land. The repo has no manifest tracking what version each tool is at
or how to check for updates.

**Decision**: Create a `updating-bundled-tools` superpowers skill that codifies
the update process for every bundled tool. The skill defines per-tool source
URLs, version detection commands, staging procedures, and verification steps,
so any agent can audit and refresh the bundled tooling on demand.

## 10. DEM Processing Pipeline

### 10.1 Sources

| Source | Format | Resolution | Download | Notes |
|--------|--------|------------|----------|-------|
| ViewFinderPanoramas (J. de Ferranti) | `.hgt` (big-endian int16) | 1" or 3" per region | Auto | Mostly worldwide coverage |
| SRTMv3 (OpenTopography) | `.hgt` | 1" (3601×3601) | Manual only | Requires user download |
| ALOS 3W30 (OpenTopography) | `.tif` (GeoTIFF) | ~1" (3600×3600) | Manual only | Requires user download |
| NED 1" (USGS) | `.tif` (GeoTIFF) | 1" | Auto | USA, Canada, Mexico |
| NED 1/3" (USGS) | `.tif` (GeoTIFF) | 1/3" | Auto | USA only |
| Custom DEM | User-provided file | Varies | N/A | Path or `;`-separated composite |

Composite DEMs: Source strings containing `;` create composite DEMs. The first
source is the base (`alt_nostrict`, clamps to boundary); subsequent sources are
sub-DEMs overlaid in reverse order (`alt_strict`, returns nodata outside extent).

### 10.2 Grid

Standard grid: **3601×3601** (1 arc-second SRTM: 3600 intervals + 1 shared
endpoint per axis). 3" SRTM data (1201×1201) is bilinearly upsampled to
3601×3601 for uniform processing. ALOS uses 3600×3600.

Extended raster: 36-pixel padding on each side (3673×3673 for View/SRTM,
3672×3672 for ALOS) from 3×3 tile neighborhood stitching. Coordinate range:
`x0=-0.01, x1=1.01, y0=-0.01, y1=1.01` (fractional degrees relative to tile
corner). Data type: `numpy.float32`. Nodata sentinel: `-32768`.

### 10.3 Reading

| Format | Method | Details |
|--------|--------|---------|
| `.hgt` | `numpy.fromfile(dtype=">i2")` | Big-endian signed 16-bit; size determines resolution |
| `.raw` | `array.array("h")` + row reversal | Legacy format |
| GeoTIFF/other | `gdal.Open().ReadAsArray()` | Requires GDAL; reads EPSG from projection, GeoTransform for coordinates |

GDAL coordinate handling assumes AREA_OR_POINT = area. Only EPSG 4326 and 4269
are explicitly supported; other CRS codes produce a warning. Nodata values from
any source are normalized to `-32768` for uniform downstream processing.

### 10.4 Nodata Fill

Controlled by `fill_nodata` config:
- `True` (default): Iterative nearest-neighbor dilation via `numpy.roll`
  (4 cardinal neighbors, 20 iterations max, bails out at ≥10,000 nodata cells,
  remaining nodata forced to 0)
- `"to zero"`: Replace all nodata with 0
- `False`: No fill applied

### 10.5 Interpolation

| Method | Usage | Behavior |
|--------|-------|----------|
| `alt_nostrict(node)` | Mesh vertex assignment | Bilinear interpolation; clamps to `[x0, x1]`, `[y0, y1]` |
| `alt_strict(node)` | Sub-DEM overlays | Nearest-neighbor; returns nodata if outside bounds |
| `alt_composite(node)` | Composite DEMs | Iterates sub-DEMs reverse-order via `alt_strict`; falls back to base `alt_nostrict` |
| Vector variants | Batch processing | Same algorithms on numpy coordinate arrays |

### 10.6 Airport DEM Smoothing

`O4_Airport_Geometry.smooth_raster_over_airports()`: Triangular-kernel
convolution (`DEM.smoothen()`) over airport polygons (boundary + runways +
hangars + taxiways + aprons) with boundary preservation blending. Saves boundary
strips before smoothing, blends smoothed edges back with original boundary using
linear ramp. Writes smoothed DEM to `.alt` file for Triangle4XP.

### 10.7 Water Smoothing

**Inland water**: 10-pass iterative Laplacian mean. Each pass sets all 3 vertex
altitudes of every water triangle to their mean. Controlled by
`tile.water_smoothing` (default: 10).

**Sea water** (`sea_smoothing_mode`):
- `"zero"` (default): All sea triangle vertices set to altitude 0
- `"mean"`: Triangle vertices leveled to their mean altitude
- `"none"`: Only negative altitudes clamped to 0, positive kept

### 10.8 Triangle4XP Integration

Triangle4XP is a project-owned C utility (`Utils/src/Triangle4XP.c`) — a modified
Shewchuk Triangle with terrain-specific curvature refinement. Built via CMake as
a native executable, invoked as a subprocess.

**Input**: `.alt` float32 binary (written by `DEM.write_to_file()`), `.poly`
constrained Delaunay input, weight map, curvature tolerance.

**Per-vertex processing**:
- `altitude(x, y)`: Bilinear interpolation from DEM grid; returns nodata if any
  of 4 surrounding cells is nodata
- `set_normal(x, y)`: Gradient-based normal from finite differences on altitude
  grid; uses upper/lower triangle for directional gradient
- Curvature precomputation: Hessian matrix eigenvalues at each interior grid
  point, weighted by geographic weight map (airports/coastline curvature
  tolerance overrides)

**Refinement**: `testriangle()` tests each triangle against curvature threshold
(`maxedge² × scalx² × maxcurv² / curv_tol² > 1`) and minimum angle. Adds more
triangles where ground curves sharply, fewer where flat.

### 10.9 DSF Elevation Encoding

Adaptive 16-bit unsigned quantization per quadtree pool:

| Altitude Range | `scale_z` | `inv_stp` | Precision |
|---------------|-----------|-----------|-----------|
| < 770m | 771 | 85 | ~0.012m |
| < 1284m | 1285 | 51 | ~0.020m |
| < 4368m | 4369 | 15 | ~0.067m |
| ≥ 4368m | 13107 | 5 | ~0.200m |

Each altitude stored as: `round((altitude - altmin) * inv_stp)`.

## 11. Combined Provider Compositing

### 11.1 Overview

Combined providers composite multiple imagery layers into a single 4096×4096
texture using priority-based alpha blending. Defined in `.comb.json` files,
validated by Pydantic `CombinedProviderDefinition`. This is shared infrastructure
with no XP-version branching, but all output is XP12 since the entire pipeline
is XP12-only (`water_tech = "XP12"` enforced, `min_xplane_version: "12.0.0"`).

### 11.2 Layer Priority

| Priority | Compositing Behavior | `mask_weight_below` Effect |
|----------|---------------------|---------------------------|
| `low` | Blends softly beneath higher layers; mask normalized against combined weight | Not increased |
| `medium` | Proportional blending; mask normalized as `255 * mask / mask_weight_below` | Increased by mask |
| `high` | Full overprint where extent is opaque; raw mask used directly | Increased by mask |
| `mask` | Same as high, plus sea-mask multiplication and optional Gaussian blur | Increased by mask |

### 11.3 Compositing Algorithm (`combine_textures()`)

1. Initialize 4096×4096 RGBA canvas and `mask_weight_below` uint16 accumulator
2. Iterate layers in **reverse order** (bottom-first, so higher-priority layers
   composite on top)
3. For each layer:
   - Get extent mask via `has_data(return_mask=True)`
   - Load source JPEG, apply `color_transform()`
   - Apply mask-priority Gaussian blur if `sea_texture_blur` is set
   - White/black pixel suppression: zero mask where source sum ≥735 or ≤35
     (prevents fringe artifacts at extent boundaries)
   - Priority-based mask weighting (see §11.2)
   - `Image.composite(layer, accumulated, mask)` to blend
4. Return final RGBA image

Single-layer fast path: No blending needed; load, transform, return directly.

### 11.4 Extent Codes

| Code | Behavior |
|------|----------|
| Positive (e.g., `"France"`) | Mask active inside extent boundary |
| Negative `!` prefix (e.g., `"!France"`) | Mask inverted — active outside boundary |
| `"global"` | Fully white mask (covers everything) |
| `"default"` | Resolved to provider's own default extent |

LowRes extents generate per-tile auto-masks from OSM data: triangulate OSM
polygons → rasterize → apply buffer (dilate/erode) and feather (smooth edge) →
save to `Extents/Auto/<code>_<latlon>.png`.

### 11.5 Inline Color Codes

Format: `[L|D]<BB>C<CC>[S<SS>]`

| Token | Meaning | Example |
|-------|---------|---------|
| `L`/`D` | Lighten/Darken (brightness sign) | `L` |
| `<BB>` | Brightness magnitude | `20` |
| `C` | Literal separator | `C` |
| `<CC>` | Contrast value | `10` |
| `S<SS>` | Optional saturation | `S30` |

Examples: `L20C10` → brightness +20, contrast 10. `D15C05S30` → brightness -15,
contrast 5, saturation 30. Parsed and registered into `color_filters_dict`.

### 11.6 `has_data()` Function

Tests whether a provider has coverage for a given bbox:

1. Global extent shortcut: returns `True` or white mask immediately
2. Negative extent: strip `!`, set inversion flag
3. Bounding box check: no overlap → return `negative` (False for positive, True for negative)
4. Load extent PNG, crop to query region, optionally invert, resize to `mask_size`
5. Mask-layer path: multiply extent mask with inverted sea mask (land=255, sea=0)
6. Return bool or mask image

## 12. GeoTIFF Export Path

### 12.1 Overview

GeoTIFF export is an alternative output to DDS, controlled by the `build_geotiffs`
config flag. When enabled, textures are written as georeferenced GeoTIFFs instead
of (or in addition to) DDS files.

### 12.2 Target Implementation (post-GDAL bindings migration)

**Small tiles** (longitude span < 0.04°):
Direct `gdal.Translate()` with EPSG:4326 corner coordinates and JPEG compression.
At small spans, the EPSG:4326 approximation error is negligible.

**Large tiles**:
Two-step via in-memory datasets:
1. `gdal.Translate()` to EPSG:3857 with meter-based corners
2. `gdal.Warp()` from EPSG:3857 to EPSG:4326 at 4096×4096, bilinear resampling

Both paths produce `-co COMPRESS=JPEG` output to the `Geotiffs/` directory.

### 12.3 Standalone Script

`O4_Geotag.py` batch-geotags cached JPEGs using the same pipeline. Will be
migrated to use `osgeo.gdal` bindings directly alongside the main migration.

### 12.4 Current Implementation

Currently uses `gdal_translate`/`gdalwarp` CLI subprocess calls via
`O4_Texture_Conversion_Utils.py`. This is what §7.4 replaces with in-process
Python bindings.

## 13. water_transition.png

### 13.1 Overview

A grayscale PNG lookup table at `Utils/water_transition.png` that maps the
`ratio_water` config value (0.0–1.0) to a `sea_level` grey value (0–255).

### 13.2 Usage

Loaded unconditionally in `build_masks()`:

```python
im = Image.open(os.path.join(FNAMES.Utils_dir, "water_transition.png"))
sea_level = im.getpixel((0, 127 * (1 - min(1, 0.1 + tile.ratio_water))))
```

### 13.3 Effect

The `sea_level` value controls inland water transparency in the mask:
- 0 = fully transparent (XP12 water shader shows through completely)
- 255 = fully opaque (orthophoto visible, no water blending)
- Intermediate values = partial blend

### 13.4 DSF Integration

Also copied into generated scenery as a terrain texture reference
(`BORDER_TEX ../textures/water_transition.png`) for constant-transparency
water paths in XP12 `.ter` terrain files.

### 13.5 XP12 Compliance

This is XP12-compliant infrastructure: the mask system feeds XP12's water shader
via BC3/DXT5 alpha channels (when `imprint_masks_to_dds=True`) or overlay
terrain masks (when `imprint_masks_to_dds=False`). The `WATER_COLOR_MASK`
terrain directive and `ratio_water * 65535` pool encoding are XP12 features.

## 14. gdalwarp_alternative() Accuracy

### 14.1 Overview

A Pillow-based CRS reprojection fallback at `O4_Imagery_Utils.py:2058`. Uses
`pyproj.Transformer` (inverse) to map target pixels to source coordinates,
splits into an 8×8 grid of quadrilaterals, computes 4 corner positions per quad,
and calls `Image.transform(Image.Transform.MESH, ..., BICUBIC)`.

### 14.2 Callers

| Location | Context |
|----------|---------|
| `O4_Imagery_Utils.py:1522` | Imagery download when provider EPSG differs from target |
| `O4_Mask_Utils.py:376` | DEM pre-mask reprojection (EPSG 4326 → 3857) |

Both are core imagery/mask processing paths that run regardless of XP version.

### 14.3 Accuracy Limitations

- No geolocation error bounds computed or logged
- Accuracy degrades at high latitudes (Web Mercator distortion increases)
- 8×8 grid is coarse for large tiles or complex projections
- No rigorous datum transformation beyond pyproj's defaults
- BICUBIC resampling is fixed; no per-stage method selection

### 14.4 Replacement Plan

Being replaced by `gdal.Warp()` via Python bindings (§7.4), which handles any
CRS pair with proper datum transformations, configurable resampling methods, and
no intermediate Pillow approximation. The Pillow path will be removed entirely
once the GDAL bindings migration is complete.

## 15. Extent Data

### 15.1 Directory Structure

```
Extents/
├── Austria/          High-res regional (Tirol)
├── Belgium/          High-res regional (Vlanderen, Wallonie)
├── Italy/            High-res regional (AltoAdige, Trentino, Veneto)
├── Switzerland/      High-res regional (Zurich, Valais)
├── LowRes/           27 country-level extents (Andorra through UK)
└── Auto/             Per-tile masks generated at runtime from LowRes OSM data
```

### 15.2 File Triplet

Each extent has three associated files:

| File | Format | Purpose |
|------|--------|---------|
| `<code>.ext.json` | JSON metadata | `mask_bounds`, `buffer_width`, `mask_width`, `epsg_code` |
| `<code>.png` | Grayscale PNG | Mask image (white=inside, black=outside) |
| `<code>.osm.bz2` | Compressed OSM | Source data for auto-mask regeneration |

### 15.3 Extent JSON Schema

Validated by Pydantic `ExtentDefinition`:

| Field | Type | Purpose |
|-------|------|---------|
| `epsg_code` | `int \| null` | EPSG code for mask coordinate system (optional) |
| `mask_bounds` | `[float, float, float, float] \| null` | `[xmin, ymin, xmax, ymax]` bounding box |
| `buffer_width` | `float \| null` | Buffer distance (meters); positive=dilate, negative=erode |
| `mask_width` | `float \| null` | Feather width (meters) for smooth mask edges |
| `blur_width` | `float \| null` | Blur radius for mask (schema-defined, rarely consumed) |

### 15.4 Auto-Extent Mask Generation

For LowRes extents, `initialize_local_combined_providers_dict()` generates
per-tile masks:

1. New extent code: `<name>_<short_latlon>` (e.g., `France_+47+002`)
2. Load OSM data from `Extents/LowRes/<name>.osm.bz2`
3. Convert to MultiPolygon via `OSM.OSM_to_MultiPolygon()`
4. Encode into `Vector_Map`, write `.node`/`.poly`, triangulate with `MESH.triangulate()`
5. Rasterize via `MASK.triangulation_to_image()`
6. Apply `buffer_width` (Gaussian blur + threshold for dilate/erode)
7. Apply `mask_width` (feathered edge via convolution)
8. Save to `Extents/Auto/<new_code>.png` for reuse

### 15.5 CRS and Datum Support

Extent masks are in EPSG:4326 by default. The `epsg_code` field allows
provider-specific CRS but is rarely used in practice.

**Current limitation**: The pipeline only transforms between EPSG:4326 and
EPSG:3857 reliably. Provider-declared EPSG codes outside this pair (e.g.,
EPSG:4269 NAD83, EPSG:3003 Italy Gauss-Boaga, EPSG:2154 France Lambert-93)
go through `gdalwarp_alternative()` which has accuracy limitations (§14).

**Resolution**: The GDAL bindings migration (§7.4) replaces `gdalwarp_alternative()`
with `gdal.Warp()`, which handles any CRS pair natively with proper datum
transformations. This will enable full multi-datum support for extent masks
without additional work.
