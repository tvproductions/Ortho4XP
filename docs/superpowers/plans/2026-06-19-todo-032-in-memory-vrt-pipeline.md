# TODO-032 In-Memory VRT Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-memory texture source path for active DDS generation so normal texture builds no longer write and reread full cached JPEGs before conversion.

**Architecture:** Introduce explicit texture source/result dataclasses, add GDAL `MEM` and `/vsimem/` VRT helpers, extract current orthophoto assembly into a shared in-memory helper, pass streaming texture sources through the download and conversion queues, and keep legacy cached JPEG behavior for cache-dependent workflows.

**Tech Stack:** Python 3.13, `unittest`, Pillow, NumPy, GDAL Python bindings, `asyncio`, `uv`, Ruff, ty.

## Global Constraints

- Use `unittest` only.
- Do not add a new runtime dependency.
- Preserve cached JPEG workflows for previews, manual retouch, combined providers, and GeoTIFF export.
- Keep final DDS encoder input file-based because `nvcompress` and `DDSTool` consume file paths.
- Use GDAL `/vsimem/` for VRT XML datasets; do not write VRT files to the normal filesystem.
- Keep generated DDS, TER, DSF, mask, GeoTIFF, and cached JPEG filename formats unchanged.
- Work on `master` by default for this fork.

---

## File Structure

- Create `src/O4_Texture_Source.py`: owns `TextureSource`, `TextureBuildResult`, and helpers for queue/result compatibility.
- Create `src/O4_GDAL_Texture_Pipeline.py`: owns GDAL `MEM` dataset creation, `/vsimem/` VRT lifecycle, VRT warp, and Pillow conversion helpers.
- Modify `src/O4_Imagery_Utils.py`: extract in-memory orthophoto build helpers, preserve `download_jpeg_ortho()` and `build_jpeg_ortho()`, add `build_texture_source()` and `async_build_texture_source()`, and let `convert_texture()` consume an optional streaming source.
- Modify `src/O4_Texture_Download_Scheduler.py`: enqueue streaming texture sources for successful active DDS downloads.
- Modify `src/O4_Texture_Conversion_Scheduler.py`: parse both legacy tuple jobs and streaming source jobs.
- Modify `src/O4_Texture_Conversion_Runner.py`: pass streaming source objects into `convert_texture()`.
- Modify `src/O4_Tile_Texture_Conversion.py`: keep scheduler wiring compatible with the updated conversion callable signature.
- Create `tests/test_texture_source.py`: source/result dataclass tests.
- Create `tests/test_gdal_texture_pipeline.py`: GDAL memory/VRT tests.
- Modify `tests/test_texture_async_downloads.py`: streaming queue handoff tests.
- Modify `tests/test_texture_conversion_scheduler.py`: job parsing tests for streaming and legacy items.
- Modify `tests/test_imagery_convert_color_normalization.py`: conversion tests for in-memory sources.
- Modify `TODO.md`: add GitHub issue link and completion evidence when implementation is verified.

---

### Task 1: Add Texture Source Contract

**Files:**
- Create: `src/O4_Texture_Source.py`
- Create: `tests/test_texture_source.py`

**Interfaces:**
- Produces: `TextureAttributes = tuple[int, int, int, str]`
- Produces: `TextureSource(tile: object, attrs: TextureAttributes, image: Image.Image, cache_path: str | None = None, wrote_cache: bool = False)`
- Produces: `TextureBuildResult.success(source: TextureSource, incomplete: bool = False) -> TextureBuildResult`
- Produces: `TextureBuildResult.failure(attrs: TextureAttributes, provider_code: str, error_summary: str, incomplete: bool = False) -> TextureBuildResult`

- [ ] **Step 1: Write failing dataclass tests**

Create `tests/test_texture_source.py`:

```python
import unittest

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Texture_Source import TextureBuildResult, TextureSource


class TextureSourceTests(unittest.TestCase):
    def test_source_exposes_texture_attributes(self):
        tile = object()
        image = Image.new("RGB", (4, 4), (10, 20, 30))
        source = TextureSource(tile, (32, 48, 16, "BI"), image, "cache.jpg", False)

        self.assertIs(source.tile, tile)
        self.assertEqual(source.til_x_left, 32)
        self.assertEqual(source.til_y_top, 48)
        self.assertEqual(source.zoomlevel, 16)
        self.assertEqual(source.provider_code, "BI")
        self.assertEqual(source.cache_path, "cache.jpg")
        self.assertFalse(source.wrote_cache)

    def test_success_result_has_legacy_ok_value(self):
        source = TextureSource(object(), (32, 48, 16, "BI"), Image.new("RGB", (4, 4)))

        result = TextureBuildResult.success(source, incomplete=True)

        self.assertEqual(result.ok, 1)
        self.assertIs(result.source, source)
        self.assertTrue(result.incomplete)
        self.assertIsNone(result.error_summary)

    def test_failure_result_has_attributes_without_source(self):
        result = TextureBuildResult.failure(
            (32, 48, 16, "BI"),
            "BI",
            "GDAL warp failed",
            incomplete=True,
        )

        self.assertEqual(result.ok, 0)
        self.assertIsNone(result.source)
        self.assertEqual(result.attrs, (32, 48, 16, "BI"))
        self.assertEqual(result.provider_code, "BI")
        self.assertEqual(result.error_summary, "GDAL warp failed")
        self.assertTrue(result.incomplete)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```powershell
uv run python -m unittest tests.test_texture_source -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'O4_Texture_Source'`.

- [ ] **Step 3: Implement the source contract**

Create `src/O4_Texture_Source.py`:

```python
"""In-memory texture source contracts for the imagery conversion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from PIL import Image

TextureAttributes: TypeAlias = tuple[int, int, int, str]


@dataclass(frozen=True)
class TextureSource:
    tile: object
    attrs: TextureAttributes
    image: Image.Image
    cache_path: str | None = None
    wrote_cache: bool = False

    @property
    def til_x_left(self) -> int:
        return self.attrs[0]

    @property
    def til_y_top(self) -> int:
        return self.attrs[1]

    @property
    def zoomlevel(self) -> int:
        return self.attrs[2]

    @property
    def provider_code(self) -> str:
        return self.attrs[3]


@dataclass(frozen=True)
class TextureBuildResult:
    attrs: TextureAttributes
    provider_code: str
    source: TextureSource | None = None
    error_summary: str | None = None
    incomplete: bool = False
    interrupted: bool = False

    @classmethod
    def success(
        cls,
        source: TextureSource,
        *,
        incomplete: bool = False,
    ) -> TextureBuildResult:
        return cls(
            attrs=source.attrs,
            provider_code=source.provider_code,
            source=source,
            incomplete=incomplete,
        )

    @classmethod
    def failure(
        cls,
        attrs: TextureAttributes,
        provider_code: str,
        error_summary: str,
        *,
        incomplete: bool = False,
        interrupted: bool = False,
    ) -> TextureBuildResult:
        return cls(
            attrs=attrs,
            provider_code=provider_code,
            error_summary=error_summary,
            incomplete=incomplete,
            interrupted=interrupted,
        )

    @property
    def ok(self) -> int:
        return 1 if self.source is not None and not self.interrupted else 0
```

- [ ] **Step 4: Run the tests to verify GREEN**

Run:

```powershell
uv run python -m unittest tests.test_texture_source -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/O4_Texture_Source.py tests/test_texture_source.py
git commit -m "feat: add texture source contract"
```

Expected: commit succeeds with only the new contract and tests.

---

### Task 2: Add GDAL Memory and VRT Helpers

**Files:**
- Create: `src/O4_GDAL_Texture_Pipeline.py`
- Create: `tests/test_gdal_texture_pipeline.py`

**Interfaces:**
- Consumes: Pillow `Image.Image`
- Produces: `memory_dataset_from_image(image, bbox, epsg)`
- Produces: `vsimem_vrt_from_sources(sources, vrt_name=None)` context manager
- Produces: `image_from_dataset(dataset, mode)`
- Produces: `warp_dataset_to_image(dataset, target_bbox, target_epsg, target_size, resampling, mode)`

- [ ] **Step 1: Write failing GDAL helper tests**

Create `tests/test_gdal_texture_pipeline.py`:

```python
import unittest
from unittest import mock

import numpy
from PIL import Image
from osgeo import gdal

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_GDAL_Texture_Pipeline as GTP


class GDALTexturePipelineTests(unittest.TestCase):
    def test_memory_dataset_from_rgb_image_preserves_pixels_and_georef(self):
        image = Image.new("RGB", (2, 2), (10, 20, 30))

        dataset = GTP.memory_dataset_from_image(image, (0, 2, 2, 0), 4326)

        self.assertEqual(dataset.RasterXSize, 2)
        self.assertEqual(dataset.RasterYSize, 2)
        self.assertEqual(dataset.RasterCount, 3)
        self.assertEqual(dataset.GetProjection(), "EPSG:4326")
        self.assertEqual(dataset.GetGeoTransform(), (0.0, 1.0, 0.0, 2.0, 0.0, -1.0))
        self.assertEqual(dataset.GetRasterBand(1).ReadAsArray()[0, 0], 10)
        self.assertEqual(dataset.GetRasterBand(2).ReadAsArray()[0, 0], 20)
        self.assertEqual(dataset.GetRasterBand(3).ReadAsArray()[0, 0], 30)

    def test_vsimem_vrt_from_sources_builds_and_unlinks_vrt(self):
        image = Image.new("RGB", (2, 2), (10, 20, 30))
        dataset = GTP.memory_dataset_from_image(image, (0, 2, 2, 0), 4326)
        unlinked = []

        with mock.patch.object(GTP.gdal, "Unlink", side_effect=unlinked.append):
            with GTP.vsimem_vrt_from_sources([dataset], vrt_name="unit-test") as vrt:
                self.assertEqual(vrt.dataset.RasterXSize, 2)
                self.assertEqual(vrt.dataset.RasterYSize, 2)
                self.assertEqual(vrt.path, "/vsimem/ortho4xp/unit-test.vrt")

        self.assertEqual(unlinked, ["/vsimem/ortho4xp/unit-test.vrt"])

    def test_warp_dataset_to_image_returns_requested_size(self):
        source = Image.new("RGB", (4, 4), (200, 10, 20))
        dataset = GTP.memory_dataset_from_image(source, (0, 1, 1, 0), 4326)

        result = GTP.warp_dataset_to_image(
            dataset,
            (0, 1, 1, 0),
            4326,
            (8, 6),
            "near",
            "RGB",
        )

        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, (8, 6))
        self.assertGreater(numpy.array(result)[2, 2, 0], 150)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```powershell
uv run python -m unittest tests.test_gdal_texture_pipeline -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'O4_GDAL_Texture_Pipeline'`.

- [ ] **Step 3: Implement GDAL memory/VRT helpers**

Create `src/O4_GDAL_Texture_Pipeline.py`:

```python
"""GDAL memory dataset and /vsimem/ VRT helpers for texture assembly."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Iterator

import numpy
from PIL import Image
from osgeo import gdal


@dataclass(frozen=True)
class VsimemVRT:
    path: str
    dataset: object


def memory_dataset_from_image(image: Image.Image, bbox, epsg) -> object:
    supported = image if image.mode in ("L", "RGB", "RGBA") else image.convert("RGB")
    array = numpy.asarray(supported)
    bands = 1 if supported.mode == "L" else len(supported.getbands())
    dataset = gdal.GetDriverByName("MEM").Create(
        "",
        supported.width,
        supported.height,
        bands,
        gdal.GDT_Byte,
    )
    ulx, uly, lrx, lry = bbox
    dataset.SetGeoTransform(
        (
            ulx,
            (lrx - ulx) / supported.width,
            0,
            uly,
            0,
            (lry - uly) / supported.height,
        )
    )
    dataset.SetProjection(f"EPSG:{epsg}")
    if bands == 1:
        dataset.GetRasterBand(1).WriteArray(array)
    else:
        for band_index in range(bands):
            dataset.GetRasterBand(band_index + 1).WriteArray(array[:, :, band_index])
    return dataset


@contextmanager
def vsimem_vrt_from_sources(sources, vrt_name: str | None = None) -> Iterator[VsimemVRT]:
    name = vrt_name or uuid.uuid4().hex
    path = f"/vsimem/ortho4xp/{name}.vrt"
    dataset = gdal.BuildVRT(path, list(sources))
    if dataset is None:
        raise RuntimeError("GDAL BuildVRT failed")
    try:
        yield VsimemVRT(path, dataset)
    finally:
        dataset = None
        gdal.Unlink(path)


def image_from_dataset(dataset, mode: str) -> Image.Image:
    if mode == "L":
        return Image.fromarray(dataset.GetRasterBand(1).ReadAsArray(), "L")
    bands = [
        dataset.GetRasterBand(index + 1).ReadAsArray()
        for index in range(len(mode))
    ]
    return Image.fromarray(numpy.dstack(bands), mode)


def warp_dataset_to_image(
    dataset,
    target_bbox,
    target_epsg,
    target_size,
    resampling,
    mode,
) -> Image.Image:
    ulx, uly, lrx, lry = target_bbox
    width, height = target_size
    warped = gdal.Warp(
        "",
        dataset,
        format="MEM",
        dstSRS=f"EPSG:{target_epsg}",
        outputBounds=[ulx, lry, lrx, uly],
        width=width,
        height=height,
        resampleAlg=resampling,
    )
    if warped is None:
        raise RuntimeError("GDAL warp failed")
    return image_from_dataset(warped, mode)
```

- [ ] **Step 4: Run the tests to verify GREEN**

Run:

```powershell
uv run python -m unittest tests.test_gdal_texture_pipeline -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/O4_GDAL_Texture_Pipeline.py tests/test_gdal_texture_pipeline.py
git commit -m "feat: add GDAL texture VRT helpers"
```

Expected: commit succeeds with only GDAL helper files.

---

### Task 3: Extract In-Memory Orthophoto Build Helper

**Files:**
- Modify: `src/O4_Imagery_Utils.py`
- Modify: `tests/test_imagery_download_color_normalization.py`
- Create or modify: `tests/test_imagery_texture_source.py`

**Interfaces:**
- Consumes: `TextureSource`, `TextureBuildResult`
- Produces: `build_texture_source(tile, til_x_left, til_y_top, zoomlevel, provider_code, *, persist_cache=False) -> TextureBuildResult`
- Produces: `async_build_texture_source(tile, *attrs, persist_cache=False) -> TextureBuildResult`
- Preserves: `download_jpeg_ortho(...) -> 1 | 0`
- Preserves: `build_jpeg_ortho(...) -> 1 | 0`

- [ ] **Step 1: Write failing tests for no-cache source build and legacy cache save**

Create `tests/test_imagery_texture_source.py`:

```python
import os
import tempfile
import unittest
from unittest import mock

from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Imagery_Utils as IMG
from O4_Texture_Source import TextureBuildResult


class ImageryTextureSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.provider = {
            "grid_type": "webmercator",
            "tile_size": 256,
            "request_type": "tms",
            "color_filters": "none",
        }
        self.original_providers = IMG.providers_dict.copy()
        self.addCleanup(self._restore_providers)
        IMG.providers_dict.clear()
        IMG.providers_dict["BI"] = self.provider

    def _restore_providers(self):
        IMG.providers_dict.clear()
        IMG.providers_dict.update(self.original_providers)

    def test_build_texture_source_returns_image_without_writing_cache(self):
        tile = type("Tile", (), {"lat": 1, "lon": 2})()
        cache_dir = os.path.join(self.temp_dir.name, "cache")
        cache_path = os.path.join(cache_dir, "32_48_BI16.jpg")
        image = Image.new("RGB", (4096, 4096), (1, 2, 3))

        with (
            mock.patch.object(IMG.FNAMES, "jpeg_file_name_from_attributes", return_value="32_48_BI16.jpg"),
            mock.patch.object(IMG.FNAMES, "jpeg_file_dir_from_attributes", return_value=cache_dir),
            mock.patch.object(IMG, "build_texture_from_tilbox", return_value=(1, image)),
        ):
            result = IMG.build_texture_source(tile, 32, 48, 16, "BI", persist_cache=False)

        self.assertIsInstance(result, TextureBuildResult)
        self.assertEqual(result.ok, 1)
        self.assertEqual(result.source.image.size, (4096, 4096))
        self.assertEqual(result.source.cache_path, cache_path)
        self.assertFalse(result.source.wrote_cache)
        self.assertFalse(os.path.exists(cache_path))

    def test_download_jpeg_ortho_still_writes_cache(self):
        file_dir = os.path.join(self.temp_dir.name, "cache")
        image = Image.new("RGB", (4096, 4096), (1, 2, 3))

        with mock.patch.object(IMG, "_assemble_ortho_image", return_value=(1, image, False)):
            ok = IMG.download_jpeg_ortho(file_dir, "32_48_BI16.jpg", 32, 48, 16, "BI")

        self.assertEqual(ok, 1)
        self.assertTrue(os.path.isfile(os.path.join(file_dir, "32_48_BI16.jpg")))
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```powershell
uv run python -m unittest tests.test_imagery_texture_source -q
```

Expected: FAIL with `AttributeError: module 'O4_Imagery_Utils' has no attribute 'build_texture_source'`.

- [ ] **Step 3: Add imports**

In `src/O4_Imagery_Utils.py`, add:

```python
from O4_Texture_Source import TextureBuildResult, TextureSource
```

- [ ] **Step 4: Extract the shared image assembly helper**

Move the image-building part of `download_jpeg_ortho()` into a helper above
`download_jpeg_ortho()`:

```python
def _assemble_ortho_image(
    til_x_left,
    til_y_top,
    zoomlevel,
    provider_code,
    file_name,
    super_resol_factor=1,
):
    provider = providers_dict[provider_code]
    if ("super_resol_factor" in provider) and (super_resol_factor == 1):
        super_resol_factor = int(provider["super_resol_factor"])
    if "max_zl" in provider:
        max_zl = int(provider["max_zl"])
        if zoomlevel > max_zl:
            super_resol_factor = 2 ** (max_zl - zoomlevel)
    width = height = int(4096 * super_resol_factor)
    texture_context = {
        "texture_filename": file_name,
        "tile_x": til_x_left,
        "tile_y": til_y_top,
        "zoomlevel": zoomlevel,
    }
    provider = IFAIL.provider_with_texture_context(provider, texture_context)
    if "grid_type" in provider and provider["grid_type"] == "webmercator":
        tilbox = [til_x_left, til_y_top, til_x_left + 16, til_y_top + 16]
        tilbox_mod = [int(round(p * super_resol_factor)) for p in tilbox]
        zoom_shift = round(log(super_resol_factor) / log(2))
        success, big_image = build_texture_from_tilbox(
            tilbox_mod,
            zoomlevel + zoom_shift,
            provider,
        )
    else:
        latmax, lonmin = GEO.gtile_to_wgs84(til_x_left, til_y_top, zoomlevel)
        latmin, lonmax = GEO.gtile_to_wgs84(til_x_left + 16, til_y_top + 16, zoomlevel)
        xmin, ymax = GEO.geo_to_webm(lonmin, latmax)
        xmax, ymin = GEO.geo_to_webm(lonmax, latmin)
        success, big_image = build_texture_from_bbox_and_size(
            [xmin, ymax, xmax, ymin],
            "3857",
            (width, height),
            provider,
        )
    if super_resol_factor == 1:
        output_image = big_image.convert("RGB")
    else:
        output_image = RP.resize_image(
            texture_resize_resampling,
            big_image,
            (int(width / super_resol_factor), int(height / super_resol_factor)),
        ).convert("RGB")
    return success, output_image, not success
```

- [ ] **Step 5: Update `download_jpeg_ortho()` to use the helper**

Replace the duplicated build logic inside `download_jpeg_ortho()` with:

```python
    texture_attrs = (til_x_left, til_y_top, zoomlevel, provider_code)
    success, output_image, incomplete = _assemble_ortho_image(
        til_x_left,
        til_y_top,
        zoomlevel,
        provider_code,
        file_name,
        super_resol_factor,
    )
    if UI.red_flag:
        return 0
    if incomplete:
        UI.lvprint(
            1,
            "Part of image",
            file_name,
            "could not be obtained ",
            "(even at lower ZL), it was filled with white there.",
        )
        record_incomplete_texture(file_dir, file_name, texture_attrs)
    if not os.path.exists(file_dir):
        os.makedirs(file_dir)
    try:
        output_image.save(os.path.join(file_dir, file_name))
    except Exception as e:
        UI.lvprint(
            0,
            "OS Error : could not save orthophoto on disk, ",
            "received message :",
            e,
        )
        return 0
    return 1
```

- [ ] **Step 6: Add streaming source helpers**

Add after `download_jpeg_ortho()`:

```python
def build_texture_source(
    tile,
    til_x_left,
    til_y_top,
    zoomlevel,
    provider_code,
    *,
    persist_cache=False,
):
    attrs = (til_x_left, til_y_top, zoomlevel, provider_code)
    if provider_code not in providers_dict or provider_code in local_combined_providers_dict:
        return TextureBuildResult.failure(
            attrs,
            provider_code,
            "Streaming texture source is only available for concrete providers",
        )
    file_name = FNAMES.jpeg_file_name_from_attributes(*attrs)
    file_dir = FNAMES.jpeg_file_dir_from_attributes(
        tile.lat,
        tile.lon,
        zoomlevel,
        providers_dict[provider_code],
    )
    cache_path = os.path.join(file_dir, file_name)
    try:
        success, output_image, incomplete = _assemble_ortho_image(
            til_x_left,
            til_y_top,
            zoomlevel,
            provider_code,
            file_name,
        )
    except Exception as exc:
        UI.vprint(2, f"Texture source build failed: {exc}")
        return TextureBuildResult.failure(attrs, provider_code, str(exc))
    if UI.red_flag:
        return TextureBuildResult.failure(
            attrs,
            provider_code,
            "Texture source build interrupted",
            interrupted=True,
        )
    if incomplete:
        UI.lvprint(
            1,
            "Part of image",
            file_name,
            "could not be obtained ",
            "(even at lower ZL), it was filled with white there.",
        )
        record_incomplete_texture(file_dir, file_name, attrs)
    wrote_cache = False
    if persist_cache:
        if not os.path.exists(file_dir):
            os.makedirs(file_dir)
        output_image.save(cache_path)
        wrote_cache = True
    source = TextureSource(tile, attrs, output_image, cache_path, wrote_cache)
    return TextureBuildResult.success(source, incomplete=incomplete and not success)


async def async_build_texture_source(tile, *attrs, persist_cache=False):
    return await asyncio.to_thread(
        build_texture_source,
        tile,
        *attrs,
        persist_cache=persist_cache,
    )
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
uv run python -m unittest tests.test_imagery_texture_source tests.test_imagery_download_color_normalization -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add src/O4_Imagery_Utils.py tests/test_imagery_texture_source.py tests/test_imagery_download_color_normalization.py
git commit -m "feat: build in-memory texture sources"
```

Expected: commit succeeds with the extraction and streaming helper tests.

---

### Task 4: Pass Streaming Sources Through Download Scheduler

**Files:**
- Modify: `src/O4_Texture_Download_Scheduler.py`
- Modify: `tests/test_texture_async_downloads.py`

**Interfaces:**
- Consumes: `IMG.async_build_texture_source(tile, *attrs) -> TextureBuildResult`
- Produces: conversion queue item `(tile, TextureSource)` on streaming success.
- Preserves: retry and failure summary semantics.

- [ ] **Step 1: Update the async download tests**

In `tests/test_texture_async_downloads.py`, add imports:

```python
from PIL import Image
from O4_Texture_Source import TextureBuildResult, TextureSource
```

Update successful build fakes to return `TextureBuildResult.success(...)`:

```python
async def build(tile, *attrs):
    source = TextureSource(tile, tuple(attrs), Image.new("RGB", (4, 4)))
    return TextureBuildResult.success(source)
```

Add an assertion after the successful scheduler run:

```python
queued_tile, queued_source = convert_queue.get_nowait()
self.assertIs(queued_tile, tile)
self.assertIsInstance(queued_source, TextureSource)
self.assertEqual(queued_source.attrs, (1, 2, 16, "BI"))
```

Update failing build fakes to return:

```python
return TextureBuildResult.failure(tuple(attrs), attrs[3], "download failed")
```

- [ ] **Step 2: Run scheduler tests to verify RED**

Run:

```powershell
uv run python -m unittest tests.test_texture_async_downloads -q
```

Expected: FAIL because the scheduler still calls `async_build_jpeg_ortho()` and enqueues legacy tuples.

- [ ] **Step 3: Update build dispatch**

In `src/O4_Texture_Download_Scheduler.py`, add this import:

```python
from O4_Texture_Source import TextureBuildResult
```

Then replace `_build_texture()` with:

```python
async def _build_texture(runtime, attrs):
    try:
        return await IMG.async_build_texture_source(runtime.tile, *attrs)
    except Exception as err:
        UI.vprint(2, f"Download failed: {err}")
        return TextureBuildResult.failure(tuple(attrs), attrs[3], str(err))
```

- [ ] **Step 4: Update result handling**

Change `_download_task()` so `ok` uses the build result:

```python
        result = await _build_texture(runtime, attrs)
        ok = result.ok
        should_retry = await _record_download_result(runtime, attrs, ok)
        await _queue_download_result(runtime, attrs, result, should_retry)
```

Change `_queue_download_result()` to:

```python
async def _queue_download_result(runtime, attrs, result, should_retry):
    if result.ok and result.source is not None:
        runtime.convert_queue.put((runtime.tile, result.source))
    elif should_retry:
        runtime.download_queue.put(attrs)
        async with runtime.state.progress_lock:
            _update_progress(runtime)
```

- [ ] **Step 5: Run scheduler tests**

Run:

```powershell
uv run python -m unittest tests.test_texture_async_downloads -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/O4_Texture_Download_Scheduler.py tests/test_texture_async_downloads.py
git commit -m "feat: enqueue streaming texture sources"
```

Expected: commit succeeds with scheduler streaming handoff.

---

### Task 5: Accept Streaming Conversion Jobs

**Files:**
- Modify: `src/O4_Texture_Conversion_Scheduler.py`
- Modify: `src/O4_Texture_Conversion_Runner.py`
- Modify: `tests/test_texture_conversion_scheduler.py`
- Modify: `tests/test_texture_conversion_scheduler_live.py`

**Interfaces:**
- Consumes: queue item `(tile, TextureSource)`
- Preserves: queue item `(tile, til_x_left, til_y_top, zoomlevel, provider_code)`
- Produces: `TextureConversionJob.source: TextureSource | None`
- Produces: runner call `convert_texture(tile, x, y, zl, provider, texture_source=source)` for streaming jobs.

- [ ] **Step 1: Write failing scheduler job tests**

In `tests/test_texture_conversion_scheduler.py`, add:

```python
from PIL import Image
from O4_Texture_Source import TextureSource
```

Add tests:

```python
def test_conversion_job_from_streaming_source_item(self):
    tile = object()
    source = TextureSource(tile, (32, 48, 16, "BI"), Image.new("RGB", (4, 4)))

    job = TCS.TextureConversionJob.from_queue_item((tile, source))

    self.assertIs(job.tile, tile)
    self.assertIs(job.source, source)
    self.assertEqual(job.til_x_left, 32)
    self.assertEqual(job.til_y_top, 48)
    self.assertEqual(job.zoomlevel, 16)
    self.assertEqual(job.provider_code, "BI")


def test_conversion_job_from_legacy_tuple_has_no_source(self):
    tile = object()

    job = TCS.TextureConversionJob.from_queue_item((tile, 32, 48, 16, "BI"))

    self.assertIsNone(job.source)
    self.assertEqual(job.provider_code, "BI")
```

In `tests/test_texture_conversion_scheduler_live.py`, update the fake converter to accept the keyword:

```python
def convert_texture(self, *args, texture_source=None):
    self.calls.append((args, texture_source))
    provider_code = texture_source.provider_code if texture_source else args[4]
    return TEX.TextureConversionResult.success(f"{provider_code}.dds", provider_code)
```

- [ ] **Step 2: Run scheduler tests to verify RED**

Run:

```powershell
uv run python -m unittest tests.test_texture_conversion_scheduler tests.test_texture_conversion_scheduler_live -q
```

Expected: FAIL because `TextureConversionJob` has no `source` field and the runner does not pass the keyword.

- [ ] **Step 3: Update conversion job model**

In `src/O4_Texture_Conversion_Scheduler.py`, add:

```python
from O4_Texture_Source import TextureSource
```

Change `ConvertTexture` to:

```python
ConvertTexture = Callable[[object, int, int, int, str], object]
```

The callable type remains permissive enough for keyword use.

Update `TextureConversionJob`:

```python
@dataclass(frozen=True)
class TextureConversionJob:
    tile: object
    til_x_left: int
    til_y_top: int
    zoomlevel: int
    provider_code: str
    source: TextureSource | None = None

    @classmethod
    def from_queue_item(cls, item):
        if len(item) == 2 and isinstance(item[1], TextureSource):
            tile, source = item
            til_x_left, til_y_top, zoomlevel, provider_code = source.attrs
            return cls(
                tile,
                til_x_left,
                til_y_top,
                zoomlevel,
                provider_code,
                source,
            )
        tile, til_x_left, til_y_top, zoomlevel, provider_code = item
        return cls(tile, til_x_left, til_y_top, zoomlevel, provider_code)
```

- [ ] **Step 4: Pass the source from the runner**

In `src/O4_Texture_Conversion_Runner.py`, update `_run_job()`:

```python
def _run_job(job: TCS.TextureConversionJob, convert_texture: TCS.ConvertTexture):
    try:
        if job.source is not None:
            return convert_texture(
                job.tile,
                job.til_x_left,
                job.til_y_top,
                job.zoomlevel,
                job.provider_code,
                texture_source=job.source,
            )
        return convert_texture(
            job.tile,
            job.til_x_left,
            job.til_y_top,
            job.zoomlevel,
            job.provider_code,
        )
    except Exception as exc:
        return TEX.TextureConversionResult.failure(
            job.display_name,
            job.provider_code,
            str(exc),
        )
```

Keep surrounding imports and existing failure result module names consistent
with the current file.

- [ ] **Step 5: Run scheduler tests**

Run:

```powershell
uv run python -m unittest tests.test_texture_conversion_scheduler tests.test_texture_conversion_scheduler_live -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/O4_Texture_Conversion_Scheduler.py src/O4_Texture_Conversion_Runner.py tests/test_texture_conversion_scheduler.py tests/test_texture_conversion_scheduler_live.py
git commit -m "feat: accept streaming conversion jobs"
```

Expected: commit succeeds with conversion queue compatibility.

---

### Task 6: Convert DDS from In-Memory Sources

**Files:**
- Modify: `src/O4_Imagery_Utils.py`
- Modify: `tests/test_imagery_convert_color_normalization.py`
- Modify: `tests/_imagery_color_normalization_helpers.py`

**Interfaces:**
- Consumes: `convert_texture(..., texture_source: TextureSource | None = None)`
- Preserves: direct legacy `convert_texture(tile, x, y, zl, provider, type="dds")`
- Produces: temp PNG encoder input for streaming DDS conversions.

- [ ] **Step 1: Add streaming conversion tests**

In `tests/test_imagery_convert_color_normalization.py`, add:

```python
from O4_Texture_Source import TextureSource
```

Add tests:

```python
def test_convert_texture_uses_streaming_image_when_cached_jpeg_is_missing(self):
    tile = self._tile_for_conversion()
    source = TextureSource(
        tile,
        (32, 48, 16, "STREAM"),
        Image.new("RGB", (16, 16), (1, 2, 3)),
        cache_path=None,
    )

    with self._convert_texture_patches("STREAM") as conversion:
        result = IMG.convert_texture(
            tile,
            32,
            48,
            16,
            "STREAM",
            texture_source=source,
        )

    self.assertTrue(result.ok)
    self.assertTrue(conversion.encode_request.source_path.endswith(".png"))
    self.assertFalse(os.path.exists(conversion.encode_request.source_path))


def test_streaming_conversion_normalizes_before_color_filter(self):
    tile = self._tile_for_conversion()
    source = TextureSource(
        tile,
        (32, 48, 16, "STREAMFILTER"),
        Image.new("RGB", (16, 16), (10, 10, 10)),
        cache_path=os.path.join(self.temp_dir.name, "32_48_STREAMFILTER16.jpg"),
    )
    call_order = []
    normalized = Image.new("RGB", (16, 16), (120, 120, 120))

    def normalize(image, *args):
        call_order.append("normalize")
        return normalized

    def color_transform(image, color_code):
        call_order.append("color_transform")
        self.assertEqual(color_code, "FILTER")
        self.assertEqual(image.getpixel((0, 0)), (120, 120, 120))
        return Image.new("RGB", image.size, (130, 130, 130))

    with self._convert_texture_patches(
        "STREAMFILTER",
        color_filters="FILTER",
    ) as conversion:
        conversion.normalize.side_effect = normalize
        conversion.color_transform.side_effect = color_transform
        IMG.normalize_texture_colors = True

        IMG.convert_texture(
            tile,
            32,
            48,
            16,
            "STREAMFILTER",
            texture_source=source,
        )

    self.assertEqual(call_order, ["normalize", "color_transform"])
```

- [ ] **Step 2: Run conversion tests to verify RED**

Run:

```powershell
uv run python -m unittest tests.test_imagery_convert_color_normalization -q
```

Expected: FAIL with `TypeError: convert_texture() got an unexpected keyword argument 'texture_source'`.

- [ ] **Step 3: Update the function signature**

In `src/O4_Imagery_Utils.py`, change:

```python
def convert_texture(tile, til_x_left, til_y_top, zoomlevel, provider_code, type="dds"):
```

to:

```python
def convert_texture(
    tile,
    til_x_left,
    til_y_top,
    zoomlevel,
    provider_code,
    type="dds",
    *,
    texture_source=None,
):
```

- [ ] **Step 4: Add helper to prepare a streaming image**

Inside `convert_texture()`, after `color_context` is built, define the source
image branch:

```python
    streaming_image = None
    if texture_source is not None:
        streaming_image = texture_source.image.convert("RGB")
```

Change the plain provider preprocessing branch from:

```python
    elif (providers_dict[provider_code]["color_filters"] != "none") or masked_texture:
        big_image = Image.open(cached_texture_path, "r").convert("RGB")
```

to:

```python
    elif (
        streaming_image is not None
        or providers_dict[provider_code]["color_filters"] != "none"
        or masked_texture
    ):
        big_image = streaming_image or Image.open(cached_texture_path, "r").convert("RGB")
```

Leave the existing normalization, color filter, mask imprint, temp PNG save,
and cleanup logic in that branch.

- [ ] **Step 5: Preserve direct-path legacy conversion**

Change the final direct input branch from:

```python
    else:
        file_to_convert, erase_tmp_png = TCN.normalized_conversion_input_path(
            cached_texture_path,
            png_file_name,
            color_context,
        )
```

to:

```python
    else:
        file_to_convert, erase_tmp_png = TCN.normalized_conversion_input_path(
            cached_texture_path,
            png_file_name,
            color_context,
        )
```

No logic change is needed in the direct branch because streaming images always
enter the preprocessing branch and produce a temporary PNG for encoder handoff.

- [ ] **Step 6: Run conversion tests**

Run:

```powershell
uv run python -m unittest tests.test_imagery_convert_color_normalization tests.test_texture_encoder -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/O4_Imagery_Utils.py tests/test_imagery_convert_color_normalization.py tests/_imagery_color_normalization_helpers.py
git commit -m "feat: convert textures from memory sources"
```

Expected: commit succeeds with streaming conversion support.

---

### Task 7: Integrate VRT Helper into Georeferenced Texture Assembly

**Files:**
- Modify: `src/O4_Imagery_Utils.py`
- Modify: `tests/test_gdal_texture_pipeline.py`
- Modify: `tests/test_gdal_warp.py`

**Interfaces:**
- Consumes: `O4_GDAL_Texture_Pipeline.memory_dataset_from_image`
- Consumes: `O4_GDAL_Texture_Pipeline.vsimem_vrt_from_sources`
- Consumes: `O4_GDAL_Texture_Pipeline.warp_dataset_to_image`
- Preserves: `warp_image_with_gdal(source_im, s_bbox, s_epsg, t_bbox, t_epsg, t_size)`

- [ ] **Step 1: Add a representative VRT assembly test**

In `tests/test_gdal_texture_pipeline.py`, add:

```python
def test_vrt_combines_adjacent_memory_sources(self):
    left = GTP.memory_dataset_from_image(Image.new("RGB", (2, 2), (255, 0, 0)), (0, 2, 2, 0), 4326)
    right = GTP.memory_dataset_from_image(Image.new("RGB", (2, 2), (0, 255, 0)), (2, 2, 4, 0), 4326)

    with GTP.vsimem_vrt_from_sources([left, right], vrt_name="adjacent") as vrt:
        image = GTP.warp_dataset_to_image(
            vrt.dataset,
            (0, 2, 4, 0),
            4326,
            (4, 2),
            "near",
            "RGB",
        )

    arr = numpy.array(image)
    self.assertGreater(arr[0, 0, 0], 200)
    self.assertGreater(arr[0, 3, 1], 200)
```

- [ ] **Step 2: Run VRT tests**

Run:

```powershell
uv run python -m unittest tests.test_gdal_texture_pipeline -q
```

Expected: PASS after Task 2, or FAIL if the helper needs extent handling adjustments.

- [ ] **Step 3: Route `warp_image_with_gdal()` through the helper**

In `src/O4_Imagery_Utils.py`, add:

```python
import O4_GDAL_Texture_Pipeline as GTP
```

Replace the internals of `warp_image_with_gdal()` with:

```python
def warp_image_with_gdal(source_im, s_bbox, s_epsg, t_bbox, t_epsg, t_size):
    source_im = _gdal_warp_supported_image(source_im)
    source_ds = GTP.memory_dataset_from_image(source_im, s_bbox, s_epsg)
    return GTP.warp_dataset_to_image(
        source_ds,
        t_bbox,
        t_epsg,
        t_size,
        RP.gdal_resampling(warp_resampling),
        source_im.mode,
    )
```

Keep `_gdal_warp_supported_image()` if other tests still cover mode conversion.
Remove now-unused `_memory_raster_from_image()` and `_image_from_memory_raster()`
only after `rg "_memory_raster_from_image|_image_from_memory_raster"` confirms
there are no other call sites.

- [ ] **Step 4: Run GDAL warp tests**

Run:

```powershell
uv run python -m unittest tests.test_gdal_warp tests.test_gdal_texture_pipeline -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/O4_Imagery_Utils.py tests/test_gdal_texture_pipeline.py tests/test_gdal_warp.py
git commit -m "refactor: route imagery warp through GDAL texture helpers"
```

Expected: commit succeeds with helper integration.

---

### Task 8: Update Tracking State

**Files:**
- Modify: `TODO.md`

**Interfaces:**
- Consumes: GitHub Issue #35.
- Produces: TODO-032 tracking state recorded in `TODO.md`.

- [ ] **Step 1: Update TODO.md before final verification**

Edit the TODO-032 block:

```markdown
### TODO-032: In-Memory VRT Pipeline

Status: In Progress

GitHub Issue: #35
```

- [ ] **Step 2: Commit tracking update**

Run:

```powershell
git add TODO.md
git commit -m "docs: track TODO-032 issue"
```

Expected: commit succeeds with only `TODO.md`.

---

### Task 9: Final Verification and Closeout

**Files:**
- All changed files

**Interfaces:**
- Consumes: all previous task outputs.
- Produces: final evidence for TODO-032.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
uv run python -m unittest tests.test_texture_source tests.test_gdal_texture_pipeline tests.test_imagery_texture_source tests.test_texture_async_downloads tests.test_texture_conversion_scheduler tests.test_texture_conversion_scheduler_live tests.test_imagery_convert_color_normalization -q
```

Expected: PASS.

- [ ] **Step 2: Run full unittest discovery**

Run:

```powershell
uv run python -m unittest discover -s tests
```

Expected: PASS.

- [ ] **Step 3: Run Ruff check**

Run:

```powershell
uv run ruff check Ortho4XP.py src tests
```

Expected: PASS.

- [ ] **Step 4: Run Ruff format check**

Run:

```powershell
uv run ruff format --check .
```

Expected: PASS.

- [ ] **Step 5: Run ty on changed Python files**

Run:

```powershell
uv run ty check src/O4_Texture_Source.py src/O4_GDAL_Texture_Pipeline.py src/O4_Imagery_Utils.py src/O4_Texture_Download_Scheduler.py src/O4_Texture_Conversion_Scheduler.py src/O4_Texture_Conversion_Runner.py src/O4_Tile_Texture_Conversion.py tests/test_texture_source.py tests/test_gdal_texture_pipeline.py tests/test_imagery_texture_source.py tests/test_texture_async_downloads.py tests/test_texture_conversion_scheduler.py tests/test_texture_conversion_scheduler_live.py tests/test_imagery_convert_color_normalization.py
```

Expected: PASS.

- [ ] **Step 6: Run Python quality gate**

Run:

```powershell
uv run python .codex/skills/quality-check/scripts/quality_check.py --skip-native
```

Expected: PASS.

- [ ] **Step 7: Run full quality gate when practical**

Run:

```powershell
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected: PASS, including native checks. If native tooling is unavailable, record the exact failure in the GitHub issue and in the final handoff.

- [ ] **Step 8: Update TODO completion evidence**

After all required verification passes, update TODO-032:

```markdown
Status: Done

GitHub Issue: #35

Completion note: implemented by adding explicit in-memory texture source
artifacts, GDAL MEM and /vsimem/ VRT helpers, streaming download-to-conversion
queue handoff for active DDS generation, and legacy cache fallback for
cache-dependent workflows. Focused tests, full unittest discovery, Ruff, Ruff
format, ty, and quality-check verification passed.
```

- [ ] **Step 9: Add GitHub evidence comment**

Run:

```powershell
gh issue comment 35 --repo tvproductions/Ortho4XP --body "Implemented TODO-032 with in-memory texture source artifacts, GDAL MEM and /vsimem/ VRT helpers, streaming DDS queue handoff, and cache-compatible legacy fallback. Verification passed: focused texture/VRT/conversion tests, full unittest discovery, Ruff, format check, ty on changed files, and quality-check."
```

Expected: exit 0.

- [ ] **Step 10: Close the GitHub issue**

Run:

```powershell
gh issue close 35 --repo tvproductions/Ortho4XP --comment "TODO-032 acceptance criteria are complete and repository verification passed."
```

Expected: issue closes successfully.

- [ ] **Step 11: Commit closeout**

Run:

```powershell
git add TODO.md
git commit -m "docs: complete TODO-032"
```

Expected: commit succeeds with TODO completion evidence.

- [ ] **Step 12: Inspect final state**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; workspace contains only intentional uncommitted changes, or is clean if all implementation commits were made.
