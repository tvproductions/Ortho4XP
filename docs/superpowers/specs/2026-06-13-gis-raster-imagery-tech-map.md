# GIS, Raster, and Imagery Technology Map

Date: 2026-06-13
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

Scope is limited to the production pipeline that generates orthophoto textures,
masks, and GeoTIFFs. DEM/elevation raster handling is covered only where it
interacts with the imagery pipeline (mask reprojection, bathymetry). The DSF
encoding layer is out of scope except where it reads texture or mask output.

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

**Supported operations** (in `color_transform()`, `O4_Imagery_Utils.py:2108-2163`):
- `brightness-contrast`: GIMP-style tangent curve, params `[brightness, contrast]`
- `saturation`: `ImageEnhance.Color().enhance(1 + sat/100)`
- `sharpness`: `ImageEnhance.Sharpness().enhance(value)`
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

**Observation**: BICUBIC is used uniformly across all resize/reproject
operations, but the choice is hardcoded with no configuration surface.

**Opportunity**: Define per-stage resampling defaults:
- Texture resize: LANCZOS (sharper downscale)
- Mask resize: NEAREST (preserve hard edges) or BILINEAR (smooth transition)
- Reprojection warp: BICUBIC (current, reasonable for continuous tone)
- Normalization edge comparison: BILINEAR (acceptable for statistics)

Expose as optional config overrides with safe defaults.

### 7.3 Cloud-Optimized GeoTIFF (COG) Exports (Low impact, Small effort)

**Observation**: GeoTIFF export uses `-co COMPRESS=JPEG` only, no overviews or
tiling.

**Opportunity**: With `osgeo.gdal` in-process, add optional
`gdal.Translate(co=TILED=YES, BLOCKXSIZE=512, BLOCKYSIZE=512)` + internal
masks + `gdal.AddOverview()` for COG-compatible debug exports.

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

**Deferred triggers**: OpenCV becomes worth evaluating when:
- **Histogram matching / color transfer**: If the current edge-statistic
  normalization is insufficient and we need per-channel histogram matching
- **Feature-based tile alignment**: If multi-provider stitching is added (SIFT/ORB
  feature detection)
- **GPU acceleration demand**: If per-tile processing time becomes a bottleneck
  and CUDA is available

**Risk on add**: 100+ MB dependency, mixed Py3.13 wheel availability (especially
macOS ARM), CUDA runtime requirement for GPU backend.

### 7.6 Compression-Aware Image QA (Medium impact, Medium effort)

**Observation**: No post-compression quality validation. DDS is generated with
`-highest` preset (post-decision), but there is still no QA step.

**Opportunity**: Add optional QA step:
1. Decode compressed DDS to PNG
2. Compare with source PNG using PSNR, SSIM, or MSE
3. Log or warn if quality drops below configurable threshold
4. Optionally fall back to a different pipeline (e.g., uncompressed RGBA DDS)

### 7.7 Sharpening / Post-Processing Pipeline (Medium impact, Medium effort)

**Observation**: No sharpening is applied to downloaded orthophotos. Some
providers produce soft imagery from JPEG compression or resampling.

**Opportunity**: Add configurable sharpening as a filter operation in the
`convert_texture()` pipeline:
- Unsharp mask (Pillow `ImageFilter.UnsharpMask`)
- Configurable radius / amount / threshold per provider
- Applied after color filter, before normalization

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

### 7.10 Architecture Leap: In-Memory Streaming Pipeline (High impact, Large effort)

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

## 8. Recommended Follow-Up Issues

| # | Title | Priority | Effort | Reference |
|---|-------|----------|--------|-----------|
| 1 | **Replace GDAL CLI with osgeo.gdal hard dependency** | **Critical** | **Large** | §7.4 |
| 2 | **Implement in-memory VRT streaming pipeline** | **Critical** | **Large** | §7.10 |
| 3 | Upgrade nvcompress to `-highest -mipfilter kaiser -alpha_dithering` flags (Win/Lin) | High | Small | §2.4 |
| 4 | Replace requests with aiohttp + asyncio for tile downloads | High | Medium | §7.9 |
| 5 | Create tool-updating skill for keeping bundled tools current | High | Medium | §9 |
| 6 | Define explicit per-stage resampling policy with config overrides | Medium | Small | §7.2 |
| 7 | Add COG-style GeoTIFF export with overviews | Low | Small | §7.3 |
| 8 | Add compression-aware DDS QA with PSNR/SSIM thresholds | Medium | Medium | §7.6 |
| 9 | Add configurable unsharp-mask sharpening to post-processing pipeline | Medium | Medium | §7.7 |
| 10 | Evaluate OpenCV for histogram matching / feature alignment | Low | Large | §7.5 |

Issues are ordered by recommended execution priority (highest value per effort
first), not by section order.

## 9. Tool Update Management

**Observation**: Bundled tools (nvcompress, DDSTool, DSFTool, Triangle4XP, 7z,
moulinette) have no automated update mechanism. Versions drift as upstream
releases land. The repo has no manifest tracking what version each tool is at
or how to check for updates.

**Decision**: Create a `updating-bundled-tools` superpowers skill that codifies
the update process for every bundled tool. The skill defines per-tool source
URLs, version detection commands, staging procedures, and verification steps,
so any agent can audit and refresh the bundled tooling on demand.
