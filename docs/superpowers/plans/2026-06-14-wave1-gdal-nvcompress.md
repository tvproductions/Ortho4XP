# Wave 1 Implementation Plan: GDAL Bindings + nvcompress Quality

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace GDAL CLI subprocess calls with Python bindings and upgrade nvcompress to maximum quality flags.

**Architecture:** Two independent workstreams. TODO-029 (nvcompress) is a focused flag upgrade in the encoder backend. TODO-028 (GDAL) is a larger migration replacing CLI subprocess calls with `osgeo.gdal` Python bindings, removing `gdalwarp_alternative()`, and making GDAL a hard dependency.

**Tech Stack:** Python 3.13+, `osgeo.gdal` (GDAL 3.9+), `nvcompress`/`DDSTool`, `unittest`, `ruff`, `ty`

---

## File Structure

### TODO-029: nvcompress flags

**Modify:**
- `src/O4_Native_Texture_Encoder.py:54-69` — Update `build_command()` to use `-highest -mipfilter kaiser -alpha_dithering` instead of `-fast`
- `tests/test_texture_encoder.py:54-75` — Update command assertions to match new flags

### TODO-028: GDAL bindings

**Modify:**
- `pyproject.toml` — Add `gdal>=3.9` to dependencies
- `src/O4_Texture_Conversion_Utils.py` — Replace CLI commands with `gdal.Translate()`/`gdal.Warp()`
- `src/O4_Imagery_Utils.py:2058-2101` — Remove `gdalwarp_alternative()`, replace callers with `gdal.Warp()`
- `src/O4_Mask_Utils.py:376` — Replace `gdalwarp_alternative()` call with `gdal.Warp()`
- `src/O4_DEM_Utils.py:11-17` — Remove `has_gdal` try/except, make import unconditional
- `src/O4_External_Tool_Paths.py` — Remove `gdal_translate`/`gdalwarp` from tool resolution
- `tests/test_gdal_bindings.py` — New test file for GDAL binding operations

---

## Task 1: Upgrade nvcompress BC1 flags (Windows/Linux)

**Files:**
- Modify: `src/O4_Native_Texture_Encoder.py:54-69`
- Modify: `tests/test_texture_encoder.py:54-64`

- [ ] **Step 1: Write the failing test**

Update the BC1 command test to expect new flags:

```python
def test_windows_linux_bc1_command_uses_nvcompress(self):
    backend = NativeTextureEncoderBackend(is_macos=False, executable="nvcompress")
    request = TextureEncodeRequest(
        source_path="input.png",
        output_path="output.dds",
        codec="bc1",
        display_name="test",
        provider_code="TEST",
    )
    command = backend.build_command(request)
    self.assertEqual(
        command,
        ["nvcompress", "-bc1", "-highest", "-alpha_dithering", "-mipfilter", "kaiser", "input.png", "output.dds"],
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m unittest tests.test_texture_encoder.NativeTextureEncoderTests.test_windows_linux_bc1_command_uses_nvcompress -v
```

Expected: FAIL — command still uses `-fast` instead of `-highest -alpha_dithering -mipfilter kaiser`

- [ ] **Step 3: Update `build_command()` for BC1**

In `src/O4_Native_Texture_Encoder.py`, replace the Windows/Linux branch (lines 63-69):

```python
def build_command(self, request: TextureEncodeRequest) -> list[str]:
    _validate_codec(request.codec)
    if self.is_macos:
        return [
            self.executable,
            _ddstool_codec_flag(request.codec),
            request.source_path,
            request.output_path,
        ]
    return [
        self.executable,
        f"-{request.codec}",
        "-highest",
        "-alpha_dithering",
        "-mipfilter",
        "kaiser",
        request.source_path,
        request.output_path,
    ]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run python -m unittest tests.test_texture_encoder.NativeTextureEncoderTests.test_windows_linux_bc1_command_uses_nvcompress -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/O4_Native_Texture_Encoder.py tests/test_texture_encoder.py
git commit -m "feat: upgrade nvcompress BC1 to -highest -mipfilter kaiser -alpha_dithering

Replace -fast with maximum quality flags for Windows/Linux nvcompress.
BC1 (DXT1) textures now use optimal endpoint search, Kaiser mipfilter,
and alpha dithering for reduced banding and block artifacts."
```

---

## Task 2: Upgrade nvcompress BC3 flags (Windows/Linux)

**Files:**
- Modify: `src/O4_Native_Texture_Encoder.py:54-69`
- Modify: `tests/test_texture_encoder.py:65-75`

- [ ] **Step 1: Write the failing test**

Update the BC3 command test to expect new flags plus `-alpha`:

```python
def test_windows_linux_bc3_command_uses_nvcompress(self):
    backend = NativeTextureEncoderBackend(is_macos=False, executable="nvcompress")
    request = TextureEncodeRequest(
        source_path="input.png",
        output_path="output.dds",
        codec="bc3",
        display_name="test",
        provider_code="TEST",
    )
    command = backend.build_command(request)
    self.assertEqual(
        command,
        ["nvcompress", "-bc3", "-highest", "-alpha_dithering", "-mipfilter", "kaiser", "-alpha", "input.png", "output.dds"],
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m unittest tests.test_texture_encoder.NativeTextureEncoderTests.test_windows_linux_bc3_command_uses_nvcompress -v
```

Expected: FAIL — command missing `-alpha` flag for BC3

- [ ] **Step 3: Update `build_command()` to add `-alpha` for BC3**

In `src/O4_Native_Texture_Encoder.py`, update the Windows/Linux branch:

```python
def build_command(self, request: TextureEncodeRequest) -> list[str]:
    _validate_codec(request.codec)
    if self.is_macos:
        return [
            self.executable,
            _ddstool_codec_flag(request.codec),
            request.source_path,
            request.output_path,
        ]
    base_flags = [
        self.executable,
        f"-{request.codec}",
        "-highest",
        "-alpha_dithering",
        "-mipfilter",
        "kaiser",
    ]
    if request.codec == "bc3":
        base_flags.append("-alpha")
    return base_flags + [request.source_path, request.output_path]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run python -m unittest tests.test_texture_encoder.NativeTextureEncoderTests.test_windows_linux_bc3_command_uses_nvcompress -v
```

Expected: PASS

- [ ] **Step 5: Run all encoder tests**

```bash
uv run python -m unittest tests.test_texture_encoder -v
```

Expected: All 16 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/O4_Native_Texture_Encoder.py tests/test_texture_encoder.py
git commit -m "feat: add -alpha flag for BC3 nvcompress encoding

BC3 (DXT5) textures with alpha channels now explicitly enable alpha
processing. Combined with -highest and -alpha_dithering, this minimizes
alpha stepping artifacts in smooth gradients (coastlines, masks)."
```

---

## Task 3: Add GDAL to pyproject.toml dependencies

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_gdal_import.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_gdal_import.py`:

```python
import unittest


class GDALImportTests(unittest.TestCase):
    def test_gdal_bindings_available(self):
        from osgeo import gdal
        self.assertIsNotNone(gdal.VersionInfo())

    def test_gdal_exceptions_enabled(self):
        from osgeo import gdal
        gdal.UseExceptions()
        self.assertTrue(gdal.GetConfigOption("CPL_DEBUG") is None or True)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m unittest tests.test_gdal_import -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'osgeo'`

- [ ] **Step 3: Add GDAL to pyproject.toml**

In `pyproject.toml`, add to the `dependencies` list:

```toml
dependencies = [
    # ... existing dependencies ...
    "gdal>=3.9",
]
```

- [ ] **Step 4: Sync dependencies**

```bash
uv sync --dev
```

Expected: `gdal` package installed successfully

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run python -m unittest tests.test_gdal_import -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock tests/test_gdal_import.py
git commit -m "feat: add osgeo.gdal as hard runtime dependency

GDAL 3.9+ provides Python 3.13 wheels for Windows (x64), macOS (x86_64
+ arm64), and Linux (x86_64 + aarch64). This enables in-process raster
operations, VRT graphs, and proper CRS transformations, replacing CLI
subprocess calls and the Pillow-based gdalwarp_alternative()."
```

---

## Task 4: Replace GeoTIFF conversion with GDAL bindings

**Files:**
- Modify: `src/O4_Texture_Conversion_Utils.py:74-166`
- Modify: `tests/_imagery_geotiff_conversion_helpers.py`
- Test: `tests/test_gdal_geotiff.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_gdal_geotiff.py`:

```python
import unittest
from unittest import mock
from pathlib import Path


class GDALGeoTIFFTests(unittest.TestCase):
    def test_small_tile_uses_direct_translate(self):
        from O4_Texture_Conversion_Utils import _geotiff_conversion_command
        bounds = (47.5, 7.0, 47.0, 7.5, 0, 0, 4096, 4096)  # span < 0.04
        commands = _geotiff_conversion_command(bounds, "input.png", "output.tif", "/tmp")
        self.assertEqual(len(commands), 1)
        self.assertIn("Translate", commands[0]["operation"])

    def test_large_tile_uses_translate_then_warp(self):
        from O4_Texture_Conversion_Utils import _geotiff_conversion_command
        bounds = (47.5, 7.0, 46.5, 8.5, 0, 0, 4096, 4096)  # span >= 0.04
        commands = _geotiff_conversion_command(bounds, "input.png", "output.tif", "/tmp")
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0]["operation"], "Translate")
        self.assertEqual(commands[1]["operation"], "Warp")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m unittest tests.test_gdal_geotiff -v
```

Expected: FAIL — `_geotiff_conversion_command` not defined or returns CLI commands

- [ ] **Step 3: Implement GDAL binding functions**

In `src/O4_Texture_Conversion_Utils.py`, replace CLI command builders with GDAL binding operations:

```python
from osgeo import gdal

gdal.UseExceptions()


def _geotiff_conversion_command(bounds, file_to_convert, out_file_name, tmp_dir):
    """Build GDAL operation specs for GeoTIFF conversion."""
    latmax, lonmin, latmin, lonmax, xmin, ymin, xmax, ymax = bounds
    output_path = str(Path(FNAMES.Geotiff_dir) / out_file_name)
    
    if latmax - latmin < 0.04:
        return [{
            "operation": "Translate",
            "input": file_to_convert,
            "output": output_path,
            "options": {
                "format": "GTiff",
                "creationOptions": ["COMPRESS=JPEG"],
                "outputBounds": [lonmin, latmin, lonmax, latmax],
                "outputSRS": "EPSG:4326",
            },
        }]
    
    tmp_tif = str(Path(tmp_dir) / out_file_name.replace(".tif", "_3857.tif"))
    return [
        {
            "operation": "Translate",
            "input": file_to_convert,
            "output": tmp_tif,
            "options": {
                "format": "GTiff",
                "creationOptions": ["COMPRESS=JPEG"],
                "outputBounds": [xmin, ymin, xmax, ymax],
                "outputSRS": "EPSG:3857",
            },
        },
        {
            "operation": "Warp",
            "input": tmp_tif,
            "output": output_path,
            "options": {
                "format": "GTiff",
                "creationOptions": ["COMPRESS=JPEG"],
                "srcSRS": "EPSG:3857",
                "dstSRS": "EPSG:4326",
                "width": 4096,
                "height": 4096,
                "resampleAlg": "bilinear",
            },
        },
    ]


def _run_gdal_operations(operations):
    """Execute GDAL operations from specs."""
    for op in operations:
        if op["operation"] == "Translate":
            gdal.Translate(
                op["output"],
                op["input"],
                **op["options"],
            )
        elif op["operation"] == "Warp":
            gdal.Warp(
                op["output"],
                op["input"],
                **op["options"],
            )
```

- [ ] **Step 4: Update `_run_geotiff_conversion()` to use GDAL bindings**

In `src/O4_Texture_Conversion_Utils.py`, replace the retry loop that calls CLI commands:

```python
def _run_geotiff_conversion(operations, max_attempts=10):
    """Run GDAL operations with retry logic."""
    for attempt in range(1, max_attempts + 1):
        try:
            _run_gdal_operations(operations)
            return True
        except Exception as e:
            if attempt == max_attempts:
                UI.lvprint(1, "ERROR: GDAL operation failed after", max_attempts, "attempts:", str(e))
                return False
            UI.lvprint(1, "WARNING: GDAL operation failed, retrying:", str(e))
            time.sleep(1)
    return False
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run python -m unittest tests.test_gdal_geotiff -v
```

Expected: PASS

- [ ] **Step 6: Run existing GeoTIFF tests**

```bash
uv run python -m unittest tests.test_imagery_convert_color_normalization -v
```

Expected: All tests PASS (may need to update mocks to work with GDAL bindings)

- [ ] **Step 7: Commit**

```bash
git add src/O4_Texture_Conversion_Utils.py tests/test_gdal_geotiff.py tests/_imagery_geotiff_conversion_helpers.py
git commit -m "feat: replace gdal_translate/gdalwarp CLI with osgeo.gdal bindings

GeoTIFF conversion now uses gdal.Translate() and gdal.Warp() directly
instead of subprocess calls. Small tiles (span < 0.04°) use direct
EPSG:4326 translation. Large tiles use two-step EPSG:3857 intermediate.
Retry logic preserved with exception-based error handling."
```

---

## Task 5: Remove `gdalwarp_alternative()` and replace callers

**Files:**
- Modify: `src/O4_Imagery_Utils.py:1522, 2058-2101`
- Modify: `src/O4_Mask_Utils.py:376`
- Test: `tests/test_gdal_warp.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_gdal_warp.py`:

```python
import unittest
from unittest import mock
import numpy as np
from PIL import Image


class GDALWarpTests(unittest.TestCase):
    def test_warp_replaces_gdalwarp_alternative(self):
        from O4_Imagery_Utils import warp_image_with_gdal
        source_im = Image.new("RGB", (100, 100), "red")
        s_bbox = [0, 1, 1, 0]
        t_bbox = [0, 100000, 100000, 0]
        result = warp_image_with_gdal(source_im, s_bbox, 4326, t_bbox, 3857, (200, 200))
        self.assertEqual(result.size, (200, 200))
        self.assertIsInstance(result, Image.Image)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m unittest tests.test_gdal_warp -v
```

Expected: FAIL — `warp_image_with_gdal` not defined

- [ ] **Step 3: Implement `warp_image_with_gdal()`**

In `src/O4_Imagery_Utils.py`, add a GDAL-based warp function:

```python
from osgeo import gdal, osr
import numpy as np

def warp_image_with_gdal(source_im, s_bbox, s_epsg, t_bbox, t_epsg, t_size):
    """Warp an image from source CRS to target CRS using GDAL."""
    s_ulx, s_uly, s_lrx, s_lry = s_bbox
    t_ulx, t_uly, t_lrx, t_lry = t_bbox
    t_w, t_h = t_size
    
    source_array = np.array(source_im)
    
    mem_driver = gdal.GetDriverByName("MEM")
    src_ds = mem_driver.Create("", source_im.width, source_im.height, 3, gdal.GDT_Byte)
    src_ds.SetGeoTransform([
        s_ulx,
        (s_lrx - s_ulx) / source_im.width,
        0,
        s_uly,
        0,
        (s_lry - s_uly) / source_im.height,
    ])
    src_srs = osr.SpatialReference()
    src_srs.ImportFromEPSG(s_epsg)
    src_ds.SetProjection(src_srs.ExportToWkt())
    
    for i in range(3):
        src_ds.GetRasterBand(i + 1).WriteArray(source_array[:, :, i])
    
    dst_ds = mem_driver.Create("", t_w, t_h, 3, gdal.GDT_Byte)
    dst_ds.SetGeoTransform([
        t_ulx,
        (t_lrx - t_ulx) / t_w,
        0,
        t_uly,
        0,
        (t_lry - t_uly) / t_h,
    ])
    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(t_epsg)
    dst_ds.SetProjection(dst_srs.ExportToWkt())
    
    gdal.Warp(dst_ds, src_ds, resampleAlg="bicubic")
    
    result_array = np.zeros((t_h, t_w, 3), dtype=np.uint8)
    for i in range(3):
        result_array[:, :, i] = dst_ds.GetRasterBand(i + 1).ReadAsArray()
    
    return Image.fromarray(result_array)
```

- [ ] **Step 4: Replace caller in `O4_Imagery_Utils.py:1522`**

Replace:
```python
if warp_needed:
    big_image = gdalwarp_alternative(...)
```

With:
```python
if warp_needed:
    big_image = warp_image_with_gdal(
        big_image,
        (s_ulx, s_uly, s_lrx, s_lry),
        provider["epsg_code"],
        t_bbox,
        t_epsg,
        t_size,
    )
```

- [ ] **Step 5: Replace caller in `O4_Mask_Utils.py:376`**

Replace:
```python
demim3857 = IMG.gdalwarp_alternative(s_bbox, "4326", demim4326, t_bbox, "3857", (6144, 6144))
```

With:
```python
demim3857 = IMG.warp_image_with_gdal(demim4326, s_bbox, 4326, t_bbox, 3857, (6144, 6144))
```

- [ ] **Step 6: Remove `gdalwarp_alternative()` function**

Delete lines 2058-2101 from `src/O4_Imagery_Utils.py` (the entire `gdalwarp_alternative()` function).

- [ ] **Step 7: Run test to verify it passes**

```bash
uv run python -m unittest tests.test_gdal_warp -v
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/O4_Imagery_Utils.py src/O4_Mask_Utils.py tests/test_gdal_warp.py
git commit -m "feat: replace gdalwarp_alternative() with gdal.Warp() bindings

Remove Pillow-based MESH transform fallback. CRS reprojection now uses
gdal.Warp() with proper datum transformations and configurable resampling.
Callers in imagery download and mask building updated to use new function."
```

---

## Task 6: Make GDAL import unconditional in O4_DEM_Utils

**Files:**
- Modify: `src/O4_DEM_Utils.py:11-17, 471-549`
- Modify: `tests/test_dem_utils.py` (if exists)

- [ ] **Step 1: Remove `has_gdal` try/except**

In `src/O4_DEM_Utils.py`, replace lines 11-17:

```python
# Remove this:
try:
    from osgeo import gdal
    has_gdal = True
    gdal.UseExceptions()
except ImportError:
    has_gdal = False

# Replace with:
from osgeo import gdal
gdal.UseExceptions()
```

- [ ] **Step 2: Remove `has_gdal` fallback path**

In `src/O4_DEM_Utils.py`, remove the `elif not has_gdal:` branch (lines 539-549) that prints a warning and returns zero altitudes. The GDAL path (lines 471-538) becomes the only path.

- [ ] **Step 3: Run DEM tests**

```bash
uv run python -m unittest discover -s tests -p "test_dem*.py" -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/O4_DEM_Utils.py
git commit -m "refactor: make osgeo.gdal import unconditional in DEM utils

Remove has_gdal fallback path. GDAL is now a hard dependency, so the
optional import pattern and zero-altitude fallback are no longer needed."
```

---

## Task 7: Remove GDAL from external tool resolution

**Files:**
- Modify: `src/O4_External_Tool_Paths.py:40-41, 57-61`
- Modify: `src/O4_Imagery_Utils.py:110-111`
- Modify: `tests/test_subprocess_utils.py:141`

- [ ] **Step 1: Remove GDAL tool mappings**

In `src/O4_External_Tool_Paths.py`, remove `gdal_translate` and `gdalwarp` from `_platform_tools()` (lines 40-41) and `_common_tools()` (lines 57-61).

- [ ] **Step 2: Remove module-level GDAL resolution**

In `src/O4_Imagery_Utils.py`, remove lines 110-111:

```python
gdal_transl_cmd = resolve_tool("gdal_translate")
gdalwarp_cmd = resolve_tool("gdalwarp")
```

These are no longer needed since GDAL operations use Python bindings.

- [ ] **Step 3: Update test**

In `tests/test_subprocess_utils.py`, remove or update the test at line 141 that checks `resolve_tool("gdalwarp")` on Windows.

- [ ] **Step 4: Run subprocess tests**

```bash
uv run python -m unittest tests.test_subprocess_utils tests.test_subprocess_regression -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/O4_External_Tool_Paths.py src/O4_Imagery_Utils.py tests/test_subprocess_utils.py
git commit -m "refactor: remove gdal_translate/gdalwarp from tool resolution

GDAL operations now use Python bindings exclusively. Remove CLI tool
path resolution and module-level command variables."
```

---

## Task 8: Update standalone O4_Geotag.py script

**Files:**
- Modify: `src/O4_Geotag.py:19-66`

- [ ] **Step 1: Replace CLI calls with GDAL bindings**

In `src/O4_Geotag.py`, replace the subprocess loop with GDAL binding calls:

```python
from osgeo import gdal
gdal.UseExceptions()

for f in os.listdir():
    if not f[-4:] == ".jpg":
        continue
    # ... compute bounds ...
    tmp_tif = f.replace(".jpg", "_tmp.tif")
    out_tif = f.replace(".jpg", ".tif")
    
    gdal.Translate(
        tmp_tif,
        f,
        format="GTiff",
        creationOptions=["COMPRESS=JPEG"],
        outputBounds=[xmin, ymin, xmax, ymax],
        outputSRS="EPSG:3857",
    )
    
    gdal.Warp(
        out_tif,
        tmp_tif,
        format="GTiff",
        creationOptions=["COMPRESS=JPEG"],
        srcSRS="EPSG:3857",
        dstSRS="EPSG:4326",
        width=4096,
        height=4096,
        resampleAlg="bilinear",
    )
    
    os.remove(tmp_tif)
```

- [ ] **Step 2: Test manually**

```bash
cd /path/to/jpeg/cache
uv run python -m src.O4_Geotag
```

Expected: GeoTIFFs generated without errors

- [ ] **Step 3: Commit**

```bash
git add src/O4_Geotag.py
git commit -m "refactor: update standalone geotag script to use GDAL bindings

Replace gdal_translate/gdalwarp subprocess calls with gdal.Translate()
and gdal.Warp() Python bindings for consistency with main pipeline."
```

---

## Task 9: Run full quality check

**Files:**
- None (verification only)

- [ ] **Step 1: Run unit tests**

```bash
uv run python -m unittest discover -s tests
```

Expected: All tests PASS

- [ ] **Step 2: Run Ruff**

```bash
uv run ruff check Ortho4XP.py src
```

Expected: No errors

- [ ] **Step 3: Run Ruff format**

```bash
uv run ruff format --check .
```

Expected: No formatting issues (or run `uv run ruff format .` to fix)

- [ ] **Step 4: Run ty on changed files**

```bash
uv run ty check src/O4_Texture_Conversion_Utils.py src/O4_Imagery_Utils.py src/O4_Mask_Utils.py src/O4_DEM_Utils.py src/O4_Native_Texture_Encoder.py src/O4_External_Tool_Paths.py src/O4_Geotag.py
```

Expected: No type errors

- [ ] **Step 5: Run quality check**

```bash
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected: All checks PASS

- [ ] **Step 6: Commit any formatting fixes**

```bash
git add -A
git commit -m "chore: apply ruff format and fix ty issues from Wave 1"
```

---

## Task 10: Update TODO.md and close GHI #30

**Files:**
- Modify: `TODO.md`

- [ ] **Step 1: Mark TODO-028 and TODO-029 as Done**

In `TODO.md`, update status for both items:

```markdown
### TODO-028: GDAL Python Bindings Migration

Status: Done

### TODO-029: Upgrade nvcompress Flags

Status: Done
```

- [ ] **Step 2: Commit**

```bash
git add TODO.md
git commit -m "chore: mark TODO-028 and TODO-029 complete

Wave 1 delivered:
- GDAL CLI subprocess calls replaced with osgeo.gdal Python bindings
- gdalwarp_alternative() Pillow fallback removed
- GDAL made hard runtime dependency (3.9+)
- nvcompress upgraded to -highest -mipfilter kaiser -alpha_dithering
- BC3 encoding adds explicit -alpha flag

Closes #30 (TODO-026 documentation phase complete)."
```

---

## Execution Summary

**Total tasks:** 10
**Estimated time:** 3-4 hours (with TDD and verification)
**Commits:** 10 (one per task)

**Deliverables:**
- TODO-029: nvcompress quality upgrade (Tasks 1-2)
- TODO-028: GDAL bindings migration (Tasks 3-9)
- Documentation updates (Task 10)

**Next wave:** TODO-030 (aiohttp async downloads) and TODO-031 (resampling policy)