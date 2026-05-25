# sRGB Histogram Color Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in neighbor-edge color normalization that reduces orthophoto texture seams before DDS conversion without blending neighbor pixels into the target image.

**Architecture:** Add a pure Pillow/NumPy normalization module, then integrate it through `src/O4_Imagery_Utils.py` behind a new `normalize_texture_colors` config flag. The implementation uses existing JPEG filename and directory helpers, skips missing or invalid neighbors, preserves current behavior when disabled, and keeps provider color filters and mask imprinting on the current conversion path.

**Tech Stack:** Python 3.13, `unittest`, `numpy`, `Pillow`, existing Ortho4XP imagery/config utilities, `uv`, Ruff, ty.

---

## File Structure

- Create `src/O4_Color_Normalization.py`
  - Owns sRGB/linear conversion, edge extraction, edge statistics, bounded correction derivation, and correction application.
- Modify `src/O4_Imagery_Utils.py`
  - Adds `normalize_texture_colors`.
  - Imports `normalize_image_with_neighbors`.
  - Adds neighbor JPEG loading from existing Ortho4XP texture attributes.
  - Calls normalization before saving new complete JPEGs and before DDS conversion of existing cached JPEGs.
- Modify `src/O4_Cfg_Vars.py`
  - Adds `normalize_texture_colors` to app-level config with `module: "IMG"` and default `False`.
- Modify `tests/test_config_models.py`
  - Verifies the config registry exposes the flag and default.
- Create `tests/test_color_normalization.py`
  - Tests pure normalization math and invalid-neighbor behavior with synthetic images.
- Create `tests/test_imagery_color_normalization.py`
  - Tests imagery integration helpers without network, X-Plane, GDAL, or DDS encoders.
- Modify `README.md`
  - Documents the opt-in setting and its conservative neighbor-statistics behavior.
- Modify `TODO.md`
  - Marks TODO-016 done only after implementation and verification pass.

## Task 1: Add Failing Pure Normalization Tests

**Files:**
- Create: `tests/test_color_normalization.py`
- Test: `tests/test_color_normalization.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_color_normalization.py` with this content:

```python
import unittest

import numpy
from PIL import Image

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Color_Normalization as CNORM


class ColorNormalizationTests(unittest.TestCase):
    def test_srgb_linear_round_trip_preserves_representative_values(self):
        source = numpy.array([[[0, 12, 64], [128, 200, 255]]], dtype=numpy.uint8)

        linear = CNORM.srgb_to_linear_array(source)
        restored = CNORM.linear_to_srgb_array(linear)

        self.assertLessEqual(numpy.abs(restored.astype(int) - source.astype(int)).max(), 1)

    def test_edge_extraction_uses_requested_band(self):
        pixels = numpy.arange(4 * 5 * 3, dtype=numpy.uint8).reshape((4, 5, 3))
        image = Image.fromarray(pixels, "RGB")

        north = CNORM.extract_edge_pixels(image, "north", band_width=2)
        south = CNORM.extract_edge_pixels(image, "south", band_width=2)
        west = CNORM.extract_edge_pixels(image, "west", band_width=2)
        east = CNORM.extract_edge_pixels(image, "east", band_width=2)

        numpy.testing.assert_array_equal(north, pixels[:2, :, :])
        numpy.testing.assert_array_equal(south, pixels[-2:, :, :])
        numpy.testing.assert_array_equal(west, pixels[:, :2, :])
        numpy.testing.assert_array_equal(east, pixels[:, -2:, :])

    def test_edge_stats_distinguish_luminance_and_channel_balance(self):
        warm_dark = Image.new("RGB", (16, 16), (120, 80, 40))
        cool_bright = Image.new("RGB", (16, 16), (150, 170, 190))

        warm_stats = CNORM.edge_stats(warm_dark, "east", band_width=4)
        cool_stats = CNORM.edge_stats(cool_bright, "west", band_width=4)

        self.assertGreater(cool_stats.mean_luminance, warm_stats.mean_luminance)
        self.assertGreater(warm_stats.mean_rgb[0], warm_stats.mean_rgb[2])
        self.assertGreater(cool_stats.mean_rgb[2], cool_stats.mean_rgb[0])
        self.assertEqual(warm_stats.pixel_count, 64)

    def test_correction_moves_target_toward_neighbor_with_clamps(self):
        target = CNORM.edge_stats(Image.new("RGB", (32, 32), (80, 60, 40)), "east")
        neighbor = CNORM.edge_stats(Image.new("RGB", (32, 32), (220, 230, 240)), "west")

        correction = CNORM.derive_color_correction([(target, neighbor)])

        self.assertEqual(correction.exposure_scale, CNORM.MAX_EXPOSURE_SCALE)
        for scale in correction.channel_scales:
            self.assertGreaterEqual(scale, CNORM.MIN_CHANNEL_SCALE)
            self.assertLessEqual(scale, CNORM.MAX_CHANNEL_SCALE)
        self.assertEqual(correction.strength, CNORM.DEFAULT_CORRECTION_STRENGTH)

    def test_apply_color_correction_preserves_mode_size_and_changes_pixels(self):
        image = Image.new("RGB", (8, 8), (100, 90, 80))
        correction = CNORM.ColorCorrection(
            exposure_scale=1.1,
            channel_scales=(1.0, 1.05, 1.1),
            strength=1.0,
        )

        result = CNORM.apply_color_correction(image, correction)

        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, image.size)
        self.assertNotEqual(result.getpixel((0, 0)), image.getpixel((0, 0)))

    def test_normalize_image_with_neighbors_returns_unchanged_without_valid_neighbors(self):
        image = Image.new("RGB", (16, 16), (100, 110, 120))

        result = CNORM.normalize_image_with_neighbors(
            image,
            {
                "north": Image.new("RGB", (8, 8), (200, 200, 200)),
                "diagonal": Image.new("RGB", (16, 16), (200, 200, 200)),
            },
            band_width=4,
        )

        self.assertEqual(result.tobytes(), image.tobytes())

    def test_normalize_image_with_neighbors_uses_opposite_neighbor_edge(self):
        target = Image.new("RGB", (16, 16), (90, 70, 50))
        neighbor = Image.new("RGB", (16, 16), (150, 160, 170))

        result = CNORM.normalize_image_with_neighbors(
            target,
            {"east": neighbor},
            band_width=4,
        )

        self.assertNotEqual(result.getpixel((8, 8)), target.getpixel((8, 8)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused tests and verify they fail because the module is missing**

Run:

```powershell
uv run python -m unittest tests.test_color_normalization -q
```

Expected result: import failure for `O4_Color_Normalization`.

## Task 2: Implement the Pure Normalization Module

**Files:**
- Create: `src/O4_Color_Normalization.py`
- Test: `tests/test_color_normalization.py`

- [ ] **Step 1: Add the complete pure helper module**

Create `src/O4_Color_Normalization.py` with this content:

```python
from dataclasses import dataclass
from typing import Literal

import numpy
from PIL import Image


EdgeName = Literal["north", "south", "east", "west"]

EDGE_BAND_PIXELS = 32
MIN_EXPOSURE_SCALE = 0.85
MAX_EXPOSURE_SCALE = 1.18
MIN_CHANNEL_SCALE = 0.88
MAX_CHANNEL_SCALE = 1.14
DEFAULT_CORRECTION_STRENGTH = 0.65
_EPSILON = 1e-8
_LUMINANCE_WEIGHTS = numpy.array([0.2126, 0.7152, 0.0722], dtype=numpy.float64)

OPPOSITE_EDGE: dict[EdgeName, EdgeName] = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}


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

    @classmethod
    def identity(cls) -> "ColorCorrection":
        return cls(
            exposure_scale=1.0,
            channel_scales=(1.0, 1.0, 1.0),
            strength=0.0,
        )

    def is_identity(self) -> bool:
        return (
            self.strength <= 0.0
            or (
                self.exposure_scale == 1.0
                and self.channel_scales == (1.0, 1.0, 1.0)
            )
        )


def srgb_to_linear_array(values):
    srgb = numpy.asarray(values, dtype=numpy.float64) / 255.0
    return numpy.where(
        srgb <= 0.04045,
        srgb / 12.92,
        numpy.power((srgb + 0.055) / 1.055, 2.4),
    )


def linear_to_srgb_array(values):
    linear = numpy.clip(numpy.asarray(values, dtype=numpy.float64), 0.0, 1.0)
    srgb = numpy.where(
        linear <= 0.0031308,
        linear * 12.92,
        1.055 * numpy.power(linear, 1 / 2.4) - 0.055,
    )
    return numpy.clip(numpy.rint(srgb * 255), 0, 255).astype(numpy.uint8)


def extract_edge_pixels(image, edge: EdgeName, band_width=EDGE_BAND_PIXELS):
    if edge not in OPPOSITE_EDGE:
        raise ValueError(f"unsupported edge: {edge}")
    if band_width < 1:
        raise ValueError("band_width must be at least 1")

    rgb = image.convert("RGB")
    pixels = numpy.asarray(rgb, dtype=numpy.uint8)
    height, width = pixels.shape[:2]

    if edge in ("north", "south"):
        band = min(int(band_width), height)
        if edge == "north":
            return pixels[:band, :, :].copy()
        return pixels[-band:, :, :].copy()

    band = min(int(band_width), width)
    if edge == "west":
        return pixels[:, :band, :].copy()
    return pixels[:, -band:, :].copy()


def edge_stats(image, edge: EdgeName, band_width=EDGE_BAND_PIXELS) -> EdgeStats:
    pixels = extract_edge_pixels(image, edge, band_width)
    linear = srgb_to_linear_array(pixels).reshape((-1, 3))
    mean_rgb_array = linear.mean(axis=0)
    mean_luminance = float(mean_rgb_array.dot(_LUMINANCE_WEIGHTS))
    return EdgeStats(
        mean_rgb=tuple(float(value) for value in mean_rgb_array),
        mean_luminance=mean_luminance,
        pixel_count=int(linear.shape[0]),
    )


def derive_color_correction(edge_pairs) -> ColorCorrection:
    pairs = list(edge_pairs)
    if not pairs:
        return ColorCorrection.identity()

    target_rgb, target_luminance = _weighted_means(
        [target for target, _neighbor in pairs]
    )
    neighbor_rgb, neighbor_luminance = _weighted_means(
        [neighbor for _target, neighbor in pairs]
    )

    exposure_scale = _clamp(
        _safe_ratio(neighbor_luminance, target_luminance),
        MIN_EXPOSURE_SCALE,
        MAX_EXPOSURE_SCALE,
    )
    target_chroma = target_rgb / max(target_luminance, _EPSILON)
    neighbor_chroma = neighbor_rgb / max(neighbor_luminance, _EPSILON)
    channel_scales = numpy.clip(
        neighbor_chroma / numpy.maximum(target_chroma, _EPSILON),
        MIN_CHANNEL_SCALE,
        MAX_CHANNEL_SCALE,
    )

    return ColorCorrection(
        exposure_scale=float(exposure_scale),
        channel_scales=tuple(float(value) for value in channel_scales),
        strength=DEFAULT_CORRECTION_STRENGTH,
    )


def apply_color_correction(image, correction: ColorCorrection):
    rgb = image.convert("RGB")
    if correction.is_identity():
        return rgb.copy()

    linear = srgb_to_linear_array(numpy.asarray(rgb, dtype=numpy.uint8))
    scales = correction.exposure_scale * numpy.array(
        correction.channel_scales, dtype=numpy.float64
    )
    corrected = numpy.clip(linear * scales, 0.0, 1.0)
    strength = _clamp(correction.strength, 0.0, 1.0)
    blended = linear * (1 - strength) + corrected * strength
    return Image.fromarray(linear_to_srgb_array(blended), "RGB")


def normalize_image_with_neighbors(image, neighbor_images, band_width=EDGE_BAND_PIXELS):
    target = image.convert("RGB")
    edge_pairs = []
    for edge, neighbor_image in neighbor_images.items():
        if edge not in OPPOSITE_EDGE:
            continue
        try:
            neighbor = neighbor_image.convert("RGB")
        except (AttributeError, OSError, ValueError):
            continue
        if neighbor.size != target.size:
            continue
        edge_pairs.append(
            (
                edge_stats(target, edge, band_width),
                edge_stats(neighbor, OPPOSITE_EDGE[edge], band_width),
            )
        )
    if not edge_pairs:
        return target.copy()
    return apply_color_correction(target, derive_color_correction(edge_pairs))


def _weighted_means(stats_list):
    total_pixels = sum(stats.pixel_count for stats in stats_list)
    if total_pixels <= 0:
        return numpy.ones(3, dtype=numpy.float64), 1.0

    mean_rgb = sum(
        numpy.array(stats.mean_rgb, dtype=numpy.float64) * stats.pixel_count
        for stats in stats_list
    ) / total_pixels
    mean_luminance = sum(
        stats.mean_luminance * stats.pixel_count for stats in stats_list
    ) / total_pixels
    return mean_rgb, float(mean_luminance)


def _safe_ratio(numerator, denominator):
    if denominator <= _EPSILON:
        return 1.0
    return numerator / denominator


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))
```

- [ ] **Step 2: Run the focused tests and verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_color_normalization -q
```

Expected result: all tests in `tests.test_color_normalization` pass.

- [ ] **Step 3: Commit the pure helper and tests**

Run:

```powershell
git add src\O4_Color_Normalization.py tests\test_color_normalization.py
git commit -m "Add sRGB edge color normalization helpers"
```

Expected result: commit succeeds.

## Task 3: Add Failing Config and Imagery Integration Tests

**Files:**
- Modify: `tests/test_config_models.py`
- Create: `tests/test_imagery_color_normalization.py`
- Test: `tests/test_config_models.py`, `tests/test_imagery_color_normalization.py`

- [ ] **Step 1: Add the config registry assertion**

In `tests/test_config_models.py`, add this test method to `ConfigModelTests`:

```python
    def test_texture_color_normalization_is_opt_in_img_setting(self):
        definition = cfg_vars["normalize_texture_colors"]

        self.assertEqual(definition["module"], "IMG")
        self.assertIs(definition["type"], bool)
        self.assertIs(definition["default"], False)
        self.assertIs(
            coerce_config_value("normalize_texture_colors", "True", cfg_vars),
            True,
        )
```

- [ ] **Step 2: Create imagery integration tests**

Create `tests/test_imagery_color_normalization.py` with this content:

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

import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG


class ImageryColorNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_enabled = IMG.normalize_texture_colors
        self.addCleanup(self._restore_state)

    def _restore_state(self):
        IMG.normalize_texture_colors = self.original_enabled

    def test_normalize_texture_image_is_bypassed_when_disabled(self):
        IMG.normalize_texture_colors = False
        image = Image.new("RGB", (16, 16), (90, 80, 70))

        with mock.patch.object(IMG, "normalize_image_with_neighbors") as normalize:
            result = IMG.normalize_texture_image_if_enabled(
                image,
                self.temp_dir.name,
                32,
                48,
                16,
                "BI",
            )

        self.assertEqual(result.tobytes(), image.tobytes())
        normalize.assert_not_called()

    def test_normalize_texture_image_loads_existing_cardinal_neighbors(self):
        IMG.normalize_texture_colors = True
        image = Image.new("RGB", (16, 16), (90, 80, 70))
        attrs = (32, 48, 16, "BI")
        neighbor_attrs = {
            "north": (32, 32, 16, "BI"),
            "south": (32, 64, 16, "BI"),
            "west": (16, 48, 16, "BI"),
            "east": (48, 48, 16, "BI"),
        }
        for edge, edge_attrs in neighbor_attrs.items():
            path = os.path.join(
                self.temp_dir.name,
                FNAMES.jpeg_file_name_from_attributes(*edge_attrs),
            )
            Image.new("RGB", (16, 16), self._color_for_edge(edge)).save(path)

        def fake_normalize(target, neighbors):
            self.assertEqual(target.size, (16, 16))
            self.assertEqual(set(neighbors), {"north", "south", "west", "east"})
            return Image.new("RGB", target.size, (120, 120, 120))

        with mock.patch.object(
            IMG, "normalize_image_with_neighbors", side_effect=fake_normalize
        ) as normalize:
            result = IMG.normalize_texture_image_if_enabled(
                image,
                self.temp_dir.name,
                *attrs,
            )

        normalize.assert_called_once()
        self.assertEqual(result.getpixel((0, 0)), (120, 120, 120))

    def test_normalize_texture_image_skips_missing_and_invalid_neighbors(self):
        IMG.normalize_texture_colors = True
        image = Image.new("RGB", (16, 16), (90, 80, 70))
        bad_path = os.path.join(
            self.temp_dir.name,
            FNAMES.jpeg_file_name_from_attributes(32, 32, 16, "BI"),
        )
        with open(bad_path, "w", encoding="utf-8") as handle:
            handle.write("not an image")

        with mock.patch.object(
            IMG, "normalize_image_with_neighbors", return_value=image
        ) as normalize:
            result = IMG.normalize_texture_image_if_enabled(
                image,
                self.temp_dir.name,
                32,
                48,
                16,
                "BI",
            )

        self.assertEqual(result.tobytes(), image.tobytes())
        normalize.assert_not_called()

    def _color_for_edge(self, edge):
        return {
            "north": (100, 110, 120),
            "south": (120, 110, 100),
            "west": (80, 100, 120),
            "east": (120, 100, 80),
        }[edge]


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the focused tests and verify they fail**

Run:

```powershell
uv run python -m unittest tests.test_config_models tests.test_imagery_color_normalization -q
```

Expected result: failures because `normalize_texture_colors` and `normalize_texture_image_if_enabled()` do not exist yet.

## Task 4: Add the Config Flag and Imagery Integration Helper

**Files:**
- Modify: `src/O4_Cfg_Vars.py`
- Modify: `src/O4_Imagery_Utils.py`
- Test: `tests/test_config_models.py`, `tests/test_imagery_color_normalization.py`

- [ ] **Step 1: Add the config setting**

In `src/O4_Cfg_Vars.py`, add this app-level entry immediately after `max_texture_download_retries`:

```python
    "normalize_texture_colors": {
        "module": "IMG",
        "type": bool,
        "default": False,
        "hint": "When enabled, applies conservative neighbor-edge color normalization to orthophotos before DDS conversion. The correction uses local texture edge statistics only and does not blend neighbor pixels into the image.",
    },
```

- [ ] **Step 2: Import the pure helper and add the runtime flag**

In `src/O4_Imagery_Utils.py`, add this local import with the other `O4_*` imports:

```python
from O4_Color_Normalization import normalize_image_with_neighbors
```

Near the existing module-level imagery retry settings, add:

```python
normalize_texture_colors: bool = False
```

- [ ] **Step 3: Add neighbor-loading and opt-in normalization helpers**

In `src/O4_Imagery_Utils.py`, add these helpers before `download_jpeg_ortho()`:

```python
_NEIGHBOR_TEXTURE_OFFSETS = {
    "north": (0, -16),
    "south": (0, 16),
    "west": (-16, 0),
    "east": (16, 0),
}


def normalize_texture_image_if_enabled(
    image,
    file_dir,
    til_x_left,
    til_y_top,
    zoomlevel,
    provider_code,
):
    if not normalize_texture_colors:
        return image
    neighbors = _load_neighbor_texture_images(
        file_dir,
        til_x_left,
        til_y_top,
        zoomlevel,
        provider_code,
        image.size,
    )
    if not neighbors:
        return image
    return normalize_image_with_neighbors(image, neighbors)


def _load_neighbor_texture_images(
    file_dir,
    til_x_left,
    til_y_top,
    zoomlevel,
    provider_code,
    target_size,
):
    neighbors = {}
    for edge, (dx, dy) in _NEIGHBOR_TEXTURE_OFFSETS.items():
        neighbor_file = FNAMES.jpeg_file_name_from_attributes(
            til_x_left + dx,
            til_y_top + dy,
            zoomlevel,
            provider_code,
        )
        neighbor_path = os.path.join(file_dir, neighbor_file)
        if not os.path.isfile(neighbor_path):
            continue
        try:
            with Image.open(neighbor_path) as neighbor:
                if neighbor.size != target_size:
                    UI.vprint(
                        3,
                        "Skipping color-normalization neighbor with unexpected size",
                        neighbor_path,
                        neighbor.size,
                    )
                    continue
                neighbors[edge] = neighbor.convert("RGB")
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            UI.vprint(
                3,
                "Skipping color-normalization neighbor",
                neighbor_path,
                exc,
            )
    return neighbors
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_config_models tests.test_imagery_color_normalization -q
```

Expected result: focused config and imagery integration tests pass.

- [ ] **Step 5: Commit config and helper integration**

Run:

```powershell
git add src\O4_Cfg_Vars.py src\O4_Imagery_Utils.py tests\test_config_models.py tests\test_imagery_color_normalization.py
git commit -m "Add opt-in texture color normalization setting"
```

Expected result: commit succeeds.

## Task 5: Wire Normalization into New JPEG Saves

**Files:**
- Modify: `src/O4_Imagery_Utils.py`
- Test: `tests/test_imagery_color_normalization.py`

- [ ] **Step 1: Add a failing source-level regression test for complete new downloads**

In `tests/test_imagery_color_normalization.py`, add this test method to `ImageryColorNormalizationTests`:

```python
    def test_download_jpeg_ortho_normalizes_only_successful_final_image_before_save(self):
        source = inspect.getsource(IMG.download_jpeg_ortho)

        self.assertIn("if success:", source)
        self.assertIn("normalize_texture_image_if_enabled(", source)
        self.assertLess(
            source.index("normalize_texture_image_if_enabled("),
            source.index(".save(os.path.join(file_dir, file_name))"),
        )
```

Also add this import at the top of the file:

```python
import inspect
```

- [ ] **Step 2: Run the focused imagery tests and verify they fail**

Run:

```powershell
uv run python -m unittest tests.test_imagery_color_normalization -q
```

Expected result: source-level regression fails because `download_jpeg_ortho()` has not been wired yet.

- [ ] **Step 3: Normalize complete final images before saving newly downloaded JPEGs**

In `src/O4_Imagery_Utils.py`, replace the existing save block inside `download_jpeg_ortho()`:

```python
        if super_resol_factor == 1:
            big_image.save(os.path.join(file_dir, file_name))
        else:
            big_image.resize(
                (
                    int(width / super_resol_factor),
                    int(height / super_resol_factor),
                ),
                Image.Resampling.BICUBIC,
            ).save(os.path.join(file_dir, file_name))
```

with:

```python
        if super_resol_factor == 1:
            output_image = big_image.convert("RGB")
        else:
            output_image = big_image.resize(
                (
                    int(width / super_resol_factor),
                    int(height / super_resol_factor),
                ),
                Image.Resampling.BICUBIC,
            ).convert("RGB")
        if success:
            output_image = normalize_texture_image_if_enabled(
                output_image,
                file_dir,
                til_x_left,
                til_y_top,
                zoomlevel,
                provider_code,
            )
        output_image.save(os.path.join(file_dir, file_name))
```

- [ ] **Step 4: Run focused tests and verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_imagery_color_normalization -q
```

Expected result: imagery normalization tests pass.

- [ ] **Step 5: Commit the new JPEG integration**

Run:

```powershell
git add src\O4_Imagery_Utils.py tests\test_imagery_color_normalization.py
git commit -m "Normalize complete orthophotos before JPEG cache save"
```

Expected result: commit succeeds.

## Task 6: Wire Normalization into Existing Cached JPEG Conversion

**Files:**
- Modify: `src/O4_Imagery_Utils.py`
- Test: `tests/test_imagery_color_normalization.py`

- [ ] **Step 1: Add a failing source-level regression test for conversion**

In `tests/test_imagery_color_normalization.py`, add this test method to `ImageryColorNormalizationTests`:

```python
    def test_convert_texture_can_normalize_existing_cached_jpeg_before_conversion(self):
        source = inspect.getsource(IMG.convert_texture)

        self.assertIn("normalize_texture_image_if_enabled(", source)
        self.assertIn("file_to_convert = os.path.join(FNAMES.resource_path(\"tmp\"), png_file_name)", source)
```

- [ ] **Step 2: Run the focused imagery tests and verify they fail**

Run:

```powershell
uv run python -m unittest tests.test_imagery_color_normalization -q
```

Expected result: source-level conversion regression fails.

- [ ] **Step 3: Add a local helper in `convert_texture()` for normalized temporary conversion input**

Inside `convert_texture()`, after `erase_tmp_tif = False`, add:

```python
    def normalized_tmp_conversion_input(source_path):
        big_image = Image.open(source_path, "r").convert("RGB")
        big_image = normalize_texture_image_if_enabled(
            big_image,
            file_dir,
            til_x_left,
            til_y_top,
            zoomlevel,
            provider_code,
        )
        file_to_convert = os.path.join(FNAMES.resource_path("tmp"), png_file_name)
        big_image.save(file_to_convert)
        return file_to_convert
```

In the final no-preprocessing branch of `convert_texture()`, replace:

```python
        file_to_convert = os.path.join(file_dir, jpeg_file_name)
```

with:

```python
        source_path = os.path.join(file_dir, jpeg_file_name)
        if normalize_texture_colors:
            file_to_convert = normalized_tmp_conversion_input(source_path)
            erase_tmp_png = True
        else:
            file_to_convert = source_path
```

In the color-filter or masked-texture branch, after opening `big_image` and before applying `color_transform()`, add:

```python
        big_image = normalize_texture_image_if_enabled(
            big_image,
            file_dir,
            til_x_left,
            til_y_top,
            zoomlevel,
            provider_code,
        )
```

In the combined-texture branch, after `big_image = combine_textures(...)`, add:

```python
        if provider_code in providers_dict:
            big_image = normalize_texture_image_if_enabled(
                big_image,
                file_dir,
                til_x_left,
                til_y_top,
                zoomlevel,
                provider_code,
            )
```

- [ ] **Step 4: Run the focused imagery tests and verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_imagery_color_normalization -q
```

Expected result: imagery normalization tests pass.

- [ ] **Step 5: Commit conversion integration**

Run:

```powershell
git add src\O4_Imagery_Utils.py tests\test_imagery_color_normalization.py
git commit -m "Normalize cached JPEGs before texture conversion"
```

Expected result: commit succeeds.

## Task 7: Document the Opt-In Feature

**Files:**
- Modify: `README.md`
- Test: documentation review

- [ ] **Step 1: Add README documentation**

In `README.md`, after the existing imagery failure summary section, add:

```markdown
## Texture color normalization

`normalize_texture_colors` is an opt-in texture preprocessing setting. When
enabled, Ortho4XP compares a texture's north, south, east, and west edges with
already available neighboring JPEG textures at the same provider and zoom level.
It computes conservative luminance and RGB balance correction from those local
edge statistics before DDS conversion.

The feature does not blend neighbor pixels into the target image and does not
create persistent provider calibration data. Missing, unreadable, incomplete, or
wrong-sized neighbors are skipped; if no valid neighbor evidence exists, the
texture is left unchanged.
```

- [ ] **Step 2: Commit documentation**

Run:

```powershell
git add README.md
git commit -m "Document texture color normalization"
```

Expected result: commit succeeds.

## Task 8: Verification, TODO Closure, and GitHub Evidence

**Files:**
- Modify: `TODO.md`
- Test: repository verification

- [ ] **Step 1: Run formatting on changed files**

Run:

```powershell
uv run ruff format src\O4_Color_Normalization.py src\O4_Imagery_Utils.py src\O4_Cfg_Vars.py tests\test_color_normalization.py tests\test_imagery_color_normalization.py tests\test_config_models.py
```

Expected result: Ruff formats the changed files or reports they are already formatted.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
uv run python -m unittest tests.test_color_normalization tests.test_imagery_color_normalization tests.test_config_models -q
```

Expected result: all focused tests pass.

- [ ] **Step 3: Run full unittest discovery**

Run:

```powershell
uv run python -m unittest discover -s tests
```

Expected result: full `unittest` suite passes.

- [ ] **Step 4: Run Ruff on the standard Python surface**

Run:

```powershell
uv run ruff check Ortho4XP.py src
```

Expected result: Ruff reports no errors.

- [ ] **Step 5: Run ty on changed Python files**

Run:

```powershell
uv run ty check src\O4_Color_Normalization.py src\O4_Imagery_Utils.py src\O4_Cfg_Vars.py tests\test_color_normalization.py tests\test_imagery_color_normalization.py tests\test_config_models.py
```

Expected result: ty reports no errors for the changed files.

- [ ] **Step 6: Run full repository quality check when practical**

Run:

```powershell
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected result: quality check exits successfully.

- [ ] **Step 7: Mark TODO-016 done after verification passes**

In `TODO.md`, under `### TODO-016: Integrate Automated sRGB Histogram Color Normalization`, add:

```markdown
Status: Done
```

Also add a short completion note below the GitHub Issue line:

```markdown
Completed by adding opt-in neighbor-edge texture color normalization using
Pillow/NumPy sRGB linear-light statistics, bounded correction clamps, config
integration, documentation, and deterministic tests.
```

- [ ] **Step 8: Commit TODO closure**

Run:

```powershell
git add TODO.md
git commit -m "Close TODO-016 texture color normalization"
```

Expected result: commit succeeds.

- [ ] **Step 9: Add GitHub issue evidence and close issue #11**

Run:

```powershell
gh issue comment 11 --repo tvproductions/Ortho4XP --body "Implemented TODO-016 automated sRGB texture color normalization. Evidence: focused color-normalization/config tests passed; full unittest discovery passed; Ruff passed; ty passed on changed Python files; full quality-check passed. The implementation is opt-in via normalize_texture_colors, uses local cardinal-neighbor edge statistics, applies bounded sRGB-aware correction, skips missing or invalid neighbors, and does not blend neighbor pixels into target textures."
gh issue close 11 --repo tvproductions/Ortho4XP --comment "Closing after TODO-016 acceptance criteria and repository verification passed."
```

Expected result: issue #11 has an implementation evidence comment and is closed.

## Final Verification Checklist

- [ ] `normalize_texture_colors` defaults to `False`.
- [ ] Disabled normalization preserves current imagery behavior.
- [ ] New JPEG saves normalize only complete successful downloads.
- [ ] Existing cached JPEG conversion can normalize into a temporary PNG input.
- [ ] Neighbor pixels are used only for statistics, not spatial blending.
- [ ] Missing, corrupt, wrong-sized, or absent neighbors are skipped.
- [ ] Provider `color_filters`, mask imprinting, and DDS conversion remain on their existing paths.
- [ ] README documents the opt-in behavior.
- [ ] TODO-016 and GitHub Issue #11 are closed only after verification passes.
