# TODO-041 AI Cloud and Seam Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve provider imagery scoring with deterministic cloud, haze, blue-sky exclusion, and four-edge seam-risk detection while keeping the default runtime dependency-free beyond NumPy/Pillow.

**Architecture:** Extend the existing `O4_Provider_Score_*` modules instead of adding a parallel pipeline. Keep metrics as 0-100 risk values where lower is better, add structured diagnostic details to the score context, and add optional neighbor-edge context without requiring any adjacent texture to exist.

**Tech Stack:** Python 3.13, `unittest`, NumPy, Pillow, existing Ortho4XP provider scoring modules.

## Global Constraints

- The default implementation must not add PyTorch, SAM, OpenCV, ONNX Runtime, OpenVINO, or model checkpoint dependencies.
- The scoring functions must remain deterministic and independent of network access, X-Plane installs, GDAL command-line tools, or provider servers.
- The implementation must follow the repository's `unittest` rule and write failing tests before production changes.
- Future optional backend failures must be logged and fall back to the heuristic backend; the default backend in this task has no optional dependency failure mode.
- `TODO.md` must be updated only after implementation and verification pass.

---

## File Structure

- Modify `src/O4_Provider_Score_Models.py`: add `ProviderScoreContext` and metric detail storage while preserving current metric fields.
- Modify `src/O4_Provider_Score_Clouds.py`: replace the single bright/low-saturation proxy with dense-cloud, haze/veil, blue-sky exclusion, and 5 percent tolerance.
- Modify `src/O4_Provider_Score_Seams.py`: add per-edge risk details, abrupt border gradients, and optional neighbor-edge comparison.
- Modify `src/O4_Provider_Score_Metrics.py`: pass optional scoring context into seam scoring and attach cloud/seam details to `ProviderScoreMetrics`.
- Modify `src/O4_Provider_Scoring.py`: accept optional scoring context in score entry points while preserving all existing callers.
- Modify `tests/test_provider_scoring.py`: add deterministic synthetic-image unit coverage for cloud/seam behavior and metric details.
- Modify `tests/test_provider_scoring_integration.py`: assert details are present in the structured log context.
- Modify `TODO.md`: mark TODO-041 done only after focused tests and quality checks pass.

## Task 1: Add Metric Detail Contracts

**Files:**
- Modify: `src/O4_Provider_Score_Models.py`
- Test: `tests/test_provider_scoring.py`

**Interfaces:**
- Consumes: existing `ProviderScoreMetrics(noise, jpeg_compression, clouds, color_drift, seam_risk)`.
- Produces: `ProviderScoreContext(neighbor_edges: Mapping[str, Any] | None = None)` and `ProviderScoreMetrics(..., details: dict[str, Any] = field(default_factory=dict))`.

- [ ] **Step 1: Write the failing detail-contract test**

Add this test method to `ProviderScoringTests` in `tests/test_provider_scoring.py`:

```python
    def test_metric_details_are_preserved_in_score_context(self):
        metrics = SCORE.ProviderScoreMetrics(
            noise=0,
            jpeg_compression=0,
            clouds=12.345,
            color_drift=0,
            seam_risk=23.456,
            details={
                "clouds": {"cloud_coverage_pct": 8.2},
                "seam_risk": {"worst_edge": "right"},
            },
        )

        result = SCORE.provider_score_from_metrics("BI", (32, 48, 16, "BI"), metrics)
        context = result.to_context()

        self.assertEqual(context["metrics"]["clouds"], 12.35)
        self.assertEqual(context["metrics"]["seam_risk"], 23.46)
        self.assertEqual(
            context["details"]["clouds"],
            {"cloud_coverage_pct": 8.2},
        )
        self.assertEqual(context["details"]["seam_risk"], {"worst_edge": "right"})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run python -m unittest tests.test_provider_scoring.ProviderScoringTests.test_metric_details_are_preserved_in_score_context
```

Expected: FAIL with `TypeError: ProviderScoreMetrics.__init__() got an unexpected keyword argument 'details'`.

- [ ] **Step 3: Implement the detail contract**

Replace `src/O4_Provider_Score_Models.py` with this content:

```python
"""Data contracts for provider imagery scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

TextureAttributes = tuple[int, int, int, str]


@dataclass(frozen=True)
class ProviderScoreContext:
    neighbor_edges: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ProviderScoreMetrics:
    noise: float
    jpeg_compression: float
    clouds: float
    color_drift: float
    seam_risk: float
    details: dict[str, Any] = field(default_factory=dict)

    def clamped(self) -> ProviderScoreMetrics:
        return ProviderScoreMetrics(
            noise=_clamp_metric(self.noise),
            jpeg_compression=_clamp_metric(self.jpeg_compression),
            clouds=_clamp_metric(self.clouds),
            color_drift=_clamp_metric(self.color_drift),
            seam_risk=_clamp_metric(self.seam_risk),
            details=dict(self.details),
        )

    def to_context(self) -> dict[str, float]:
        return {
            "noise": round(self.noise, 2),
            "jpeg_compression": round(self.jpeg_compression, 2),
            "clouds": round(self.clouds, 2),
            "color_drift": round(self.color_drift, 2),
            "seam_risk": round(self.seam_risk, 2),
        }


@dataclass(frozen=True)
class ProviderScoreResult:
    provider_code: str
    texture_attributes: TextureAttributes
    metrics: ProviderScoreMetrics
    global_score: float
    quality_label: str

    @property
    def til_x_left(self) -> int:
        return self.texture_attributes[0]

    @property
    def til_y_top(self) -> int:
        return self.texture_attributes[1]

    @property
    def zoomlevel(self) -> int:
        return self.texture_attributes[2]

    def to_context(self) -> dict[str, Any]:
        return {
            "provider_code": self.provider_code,
            "tile_x": self.til_x_left,
            "tile_y": self.til_y_top,
            "zoomlevel": self.zoomlevel,
            "global_score": round(self.global_score, 2),
            "quality_label": self.quality_label,
            "metrics": self.metrics.to_context(),
            "details": self.metrics.details,
        }


def _clamp_metric(value: float) -> float:
    return min(100.0, max(0.0, float(value)))
```

- [ ] **Step 4: Run the detail-contract test to verify it passes**

Run:

```bash
uv run python -m unittest tests.test_provider_scoring.ProviderScoringTests.test_metric_details_are_preserved_in_score_context
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/O4_Provider_Score_Models.py tests/test_provider_scoring.py
git commit -m "feat: add provider score metric details"
```

## Task 2: Upgrade Cloud and Haze Detection

**Files:**
- Modify: `src/O4_Provider_Score_Clouds.py`
- Modify: `src/O4_Provider_Score_Metrics.py`
- Test: `tests/test_provider_scoring.py`

**Interfaces:**
- Consumes: `ProviderScoreMetrics.details` from Task 1.
- Produces: `cloud_score_details(sample: numpy.ndarray) -> tuple[float, dict[str, float]]`.

- [ ] **Step 1: Write failing cloud behavior tests**

Add these methods to `ProviderScoringTests`:

```python
    def test_small_cloud_coverage_under_tolerance_is_not_penalized(self):
        image = Image.new("RGB", (20, 20), (80, 130, 85))
        pixels = [(80, 130, 85)] * 400
        for index in range(16):
            pixels[index] = (242, 242, 242)
        image.putdata(pixels)

        result = SCORE.score_provider_image("BI", (32, 48, 16, "BI"), image)

        self.assertEqual(result.metrics.clouds, 0)
        self.assertLess(
            result.metrics.details["clouds"]["cloud_coverage_pct"],
            5.0,
        )

    def test_dense_cloud_coverage_above_tolerance_increases_cloud_risk(self):
        image = Image.new("RGB", (20, 20), (80, 130, 85))
        pixels = [(80, 130, 85)] * 400
        for index in range(80):
            pixels[index] = (242, 242, 242)
        image.putdata(pixels)

        result = SCORE.score_provider_image("BI", (32, 48, 16, "BI"), image)

        self.assertGreater(result.metrics.clouds, 20)
        self.assertGreater(
            result.metrics.details["clouds"]["dense_cloud_pct"],
            15,
        )

    def test_blue_sky_like_pixels_are_excluded_from_cloud_coverage(self):
        image = Image.new("RGB", (20, 20), (110, 155, 230))

        result = SCORE.score_provider_image("BI", (32, 48, 16, "BI"), image)

        self.assertEqual(result.metrics.clouds, 0)
        self.assertGreater(
            result.metrics.details["clouds"]["blue_sky_excluded_pct"],
            90,
        )

    def test_low_variance_haze_increases_cloud_risk(self):
        image = Image.new("RGB", (20, 20), (188, 188, 185))

        result = SCORE.score_provider_image("BI", (32, 48, 16, "BI"), image)

        self.assertGreater(result.metrics.clouds, 80)
        self.assertGreater(result.metrics.details["clouds"]["veil_pct"], 90)
```

- [ ] **Step 2: Run the cloud tests to verify they fail**

Run:

```bash
uv run python -m unittest tests.test_provider_scoring.ProviderScoringTests.test_small_cloud_coverage_under_tolerance_is_not_penalized tests.test_provider_scoring.ProviderScoringTests.test_dense_cloud_coverage_above_tolerance_increases_cloud_risk tests.test_provider_scoring.ProviderScoringTests.test_blue_sky_like_pixels_are_excluded_from_cloud_coverage tests.test_provider_scoring.ProviderScoringTests.test_low_variance_haze_increases_cloud_risk
```

Expected: FAIL because `metrics.details["clouds"]` is missing and the old cloud proxy penalizes all bright low-saturation pixels without the new tolerance/details.

- [ ] **Step 3: Implement cloud details and tolerance**

Replace `src/O4_Provider_Score_Clouds.py` with this content:

```python
"""Cloud and haze proxy metrics for provider scoring."""

from __future__ import annotations

import numpy


def cloud_score(sample: numpy.ndarray) -> float:
    score, _details = cloud_score_details(sample)
    return score


def cloud_score_details(sample: numpy.ndarray) -> tuple[float, dict[str, float]]:
    if sample.size == 0 or sample.ndim != 3 or sample.shape[2] < 3:
        return 0.0, _cloud_details(0.0, 0.0, 0.0, 0.0)

    rgb = sample[:, :, :3].astype(numpy.float64)
    red = rgb[:, :, 0]
    green = rgb[:, :, 1]
    blue = rgb[:, :, 2]
    max_channel = numpy.max(rgb, axis=2)
    min_channel = numpy.min(rgb, axis=2)
    luminance = (red + green + blue) / 3.0
    saturation = max_channel - min_channel

    dense_cloud = (luminance >= 220) & (saturation <= 28)
    local_std = _local_luminance_std(luminance, block_size=4)
    veil = (luminance >= 180) & (saturation <= 38) & (local_std <= 8.0)
    blue_sky = (blue > red + 10) & (blue > green + 5) & (luminance >= 145)
    cloud_mask = (dense_cloud | veil) & ~blue_sky

    cloud_coverage = float(numpy.mean(cloud_mask) * 100)
    dense_coverage = float(numpy.mean(dense_cloud & ~blue_sky) * 100)
    veil_coverage = float(numpy.mean(veil & ~blue_sky) * 100)
    blue_sky_coverage = float(numpy.mean(blue_sky) * 100)
    risk = min(100.0, max(0.0, (cloud_coverage - 5.0) * 2.1))
    return risk, _cloud_details(
        cloud_coverage,
        dense_coverage,
        veil_coverage,
        blue_sky_coverage,
    )


def _local_luminance_std(luminance: numpy.ndarray, block_size: int) -> numpy.ndarray:
    height, width = luminance.shape
    std_map = numpy.zeros((height, width), dtype=numpy.float64)
    for y_start in range(0, height, block_size):
        y_end = min(height, y_start + block_size)
        for x_start in range(0, width, block_size):
            x_end = min(width, x_start + block_size)
            block = luminance[y_start:y_end, x_start:x_end]
            std_map[y_start:y_end, x_start:x_end] = float(numpy.std(block))
    return std_map


def _cloud_details(
    cloud_coverage: float,
    dense_coverage: float,
    veil_coverage: float,
    blue_sky_coverage: float,
) -> dict[str, float]:
    return {
        "cloud_coverage_pct": round(cloud_coverage, 2),
        "dense_cloud_pct": round(dense_coverage, 2),
        "veil_pct": round(veil_coverage, 2),
        "blue_sky_excluded_pct": round(blue_sky_coverage, 2),
    }
```

Modify `src/O4_Provider_Score_Metrics.py` so `compute_provider_score_metrics()` attaches cloud details:

```python
"""Metric orchestration for provider imagery scoring."""

from PIL import Image

import O4_Provider_Score_Artifacts as ART
import O4_Provider_Score_Edges as EDGE
from O4_Provider_Score_Models import ProviderScoreContext, ProviderScoreMetrics


def compute_provider_score_metrics(
    image: Image.Image,
    scoring_context: ProviderScoreContext | None = None,
) -> ProviderScoreMetrics:
    sample = ART.sample_rgb_array(image)
    luma = ART.luminance(sample)
    cloud_risk, cloud_details = ART.cloud_score_details(sample)
    return ProviderScoreMetrics(
        noise=ART.noise_score(sample),
        jpeg_compression=ART.jpeg_compression_score(luma),
        clouds=cloud_risk,
        color_drift=EDGE.color_drift_score(sample),
        seam_risk=EDGE.seam_risk_score(sample),
        details={
            "clouds": cloud_details,
        },
    )
```

Replace `src/O4_Provider_Score_Artifacts.py` with this content so the new cloud helper is exported through the existing compatibility facade:

```python
"""Compatibility facade for provider artifact metrics."""

from O4_Provider_Score_Clouds import cloud_score, cloud_score_details
from O4_Provider_Score_Compression import jpeg_compression_score, noise_score
from O4_Provider_Score_Sampling import luminance, mean_of_arrays, sample_rgb_array

__all__ = [
    "cloud_score",
    "cloud_score_details",
    "jpeg_compression_score",
    "luminance",
    "mean_of_arrays",
    "noise_score",
    "sample_rgb_array",
]
```

- [ ] **Step 4: Run the cloud tests to verify they pass**

Run:

```bash
uv run python -m unittest tests.test_provider_scoring.ProviderScoringTests.test_small_cloud_coverage_under_tolerance_is_not_penalized tests.test_provider_scoring.ProviderScoringTests.test_dense_cloud_coverage_above_tolerance_increases_cloud_risk tests.test_provider_scoring.ProviderScoringTests.test_blue_sky_like_pixels_are_excluded_from_cloud_coverage tests.test_provider_scoring.ProviderScoringTests.test_low_variance_haze_increases_cloud_risk tests.test_provider_scoring.ProviderScoringTests.test_uniform_low_risk_image_scores_high_quality
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/O4_Provider_Score_Artifacts.py src/O4_Provider_Score_Clouds.py src/O4_Provider_Score_Metrics.py tests/test_provider_scoring.py
git commit -m "feat: improve provider cloud scoring"
```

## Task 3: Upgrade Seam Detection and Optional Neighbor Context

**Files:**
- Modify: `src/O4_Provider_Score_Seams.py`
- Modify: `src/O4_Provider_Score_Edges.py`
- Modify: `src/O4_Provider_Score_Metrics.py`
- Modify: `src/O4_Provider_Scoring.py`
- Test: `tests/test_provider_scoring.py`

**Interfaces:**
- Consumes: `ProviderScoreContext(neighbor_edges=...)` from Task 1.
- Produces: `seam_risk_score_details(sample: numpy.ndarray, scoring_context: ProviderScoreContext | None = None) -> tuple[float, dict[str, object]]`.

- [ ] **Step 1: Write failing seam behavior tests**

Add these methods to `ProviderScoringTests`:

```python
    def test_single_problematic_edge_increases_seam_risk_and_identifies_edge(self):
        image = Image.new("RGB", (32, 32), (95, 130, 95))
        pixels = []
        for y in range(32):
            for x in range(32):
                pixels.append((210, 210, 210) if x >= 30 else (95, 130, 95))
        image.putdata(pixels)

        result = SCORE.score_provider_image("BI", (32, 48, 16, "BI"), image)

        self.assertGreater(result.metrics.seam_risk, 20)
        self.assertEqual(result.metrics.details["seam_risk"]["worst_edge"], "right")
        self.assertGreater(
            result.metrics.details["seam_risk"]["edges"]["right"]["risk"],
            result.metrics.details["seam_risk"]["edges"]["left"]["risk"],
        )

    def test_abrupt_border_gradient_increases_seam_risk(self):
        image = Image.new("RGB", (32, 32), (90, 125, 90))
        pixels = []
        for y in range(32):
            for x in range(32):
                pixels.append((225, 225, 225) if y == 1 else (90, 125, 90))
        image.putdata(pixels)

        result = SCORE.score_provider_image("BI", (32, 48, 16, "BI"), image)

        self.assertGreater(result.metrics.seam_risk, 10)
        self.assertGreater(
            result.metrics.details["seam_risk"]["edges"]["top"]["border_gradient"],
            50,
        )

    def test_neighbor_edge_mismatch_increases_seam_risk_when_context_is_supplied(self):
        image = Image.new("RGB", (32, 32), (95, 130, 95))
        neighbor_edge = numpy.full((32, 2, 3), 230.0)
        scoring_context = SCORE.ProviderScoreContext(
            neighbor_edges={"right": neighbor_edge}
        )

        result = SCORE.score_provider_image(
            "BI",
            (32, 48, 16, "BI"),
            image,
            scoring_context=scoring_context,
        )

        self.assertGreater(result.metrics.seam_risk, 20)
        self.assertTrue(result.metrics.details["seam_risk"]["neighbor_compared"])
        self.assertEqual(result.metrics.details["seam_risk"]["worst_edge"], "right")
```

Update the top imports in `tests/test_provider_scoring.py` to include NumPy:

```python
import math
import unittest

import numpy
from PIL import Image
```

- [ ] **Step 2: Run the seam tests to verify they fail**

Run:

```bash
uv run python -m unittest tests.test_provider_scoring.ProviderScoringTests.test_single_problematic_edge_increases_seam_risk_and_identifies_edge tests.test_provider_scoring.ProviderScoringTests.test_abrupt_border_gradient_increases_seam_risk tests.test_provider_scoring.ProviderScoringTests.test_neighbor_edge_mismatch_increases_seam_risk_when_context_is_supplied
```

Expected: FAIL because `seam_risk` details are missing, `score_provider_image()` does not accept `scoring_context`, and current seam scoring does not expose per-edge results.

- [ ] **Step 3: Implement seam details and context-aware scoring**

Replace `src/O4_Provider_Score_Seams.py` with this content:

```python
"""Edge seam-risk metric for provider scoring."""

from __future__ import annotations

from typing import Any

import numpy

from O4_Provider_Score_Models import ProviderScoreContext
from O4_Provider_Score_Sampling import luminance


def seam_risk_score(sample: numpy.ndarray) -> float:
    score, _details = seam_risk_score_details(sample)
    return score


def seam_risk_score_details(
    sample: numpy.ndarray,
    scoring_context: ProviderScoreContext | None = None,
) -> tuple[float, dict[str, Any]]:
    if sample.size == 0 or sample.ndim != 3 or sample.shape[2] < 3:
        return 0.0, _empty_details()

    rgb = sample[:, :, :3].astype(numpy.float64)
    band = max(1, min(rgb.shape[0], rgb.shape[1]) // 16)
    interior = _interior(rgb, band)
    interior_luma = luminance(interior)
    interior_luma_mean = float(numpy.mean(interior_luma))
    interior_rgb_mean = _rgb_mean(interior)
    neighbor_edges = scoring_context.neighbor_edges if scoring_context else None

    edge_details = {}
    for edge_name, edge in _edge_arrays(rgb, band).items():
        edge_luma = luminance(edge)
        luma_drift = abs(float(numpy.mean(edge_luma)) - interior_luma_mean)
        rgb_drift = float(numpy.mean(numpy.abs(_rgb_mean(edge) - interior_rgb_mean)))
        border_gradient = _border_gradient(rgb, edge_name, band)
        neighbor_drift = _neighbor_drift(edge, edge_name, neighbor_edges)
        risk = max(
            0.0,
            luma_drift - 12.0,
            rgb_drift - 12.0,
            border_gradient - 18.0,
            neighbor_drift - 12.0,
        )
        edge_details[edge_name] = {
            "risk": round(risk, 2),
            "luminance_drift": round(luma_drift, 2),
            "rgb_drift": round(rgb_drift, 2),
            "border_gradient": round(border_gradient, 2),
            "neighbor_drift": round(neighbor_drift, 2),
        }

    worst_edge = max(edge_details, key=lambda edge: edge_details[edge]["risk"])
    score = float(edge_details[worst_edge]["risk"])
    return score, {
        "worst_edge": worst_edge,
        "edges": edge_details,
        "neighbor_compared": any(
            details["neighbor_drift"] > 0 for details in edge_details.values()
        ),
    }


def _edge_arrays(sample: numpy.ndarray, band: int) -> dict[str, numpy.ndarray]:
    return {
        "left": sample[:, :band, :],
        "right": sample[:, -band:, :],
        "top": sample[:band, :, :],
        "bottom": sample[-band:, :, :],
    }


def _interior(sample: numpy.ndarray, band: int) -> numpy.ndarray:
    interior = sample[band:-band, band:-band, :]
    if interior.size == 0:
        return sample
    return interior


def _rgb_mean(edge: numpy.ndarray) -> numpy.ndarray:
    return edge.reshape(-1, 3).mean(axis=0)


def _border_gradient(sample: numpy.ndarray, edge_name: str, band: int) -> float:
    height, width = sample.shape[:2]
    if edge_name == "left" and width > band:
        return float(numpy.mean(numpy.abs(sample[:, band, :] - sample[:, band - 1, :])))
    if edge_name == "right" and width > band:
        return float(
            numpy.mean(numpy.abs(sample[:, width - band, :] - sample[:, width - band - 1, :]))
        )
    if edge_name == "top" and height > band:
        return float(numpy.mean(numpy.abs(sample[band, :, :] - sample[band - 1, :, :])))
    if edge_name == "bottom" and height > band:
        return float(
            numpy.mean(numpy.abs(sample[height - band, :, :] - sample[height - band - 1, :, :]))
        )
    return 0.0


def _neighbor_drift(
    edge: numpy.ndarray,
    edge_name: str,
    neighbor_edges: Any,
) -> float:
    if not neighbor_edges or edge_name not in neighbor_edges:
        return 0.0
    neighbor = numpy.asarray(neighbor_edges[edge_name], dtype=numpy.float64)
    if neighbor.size == 0 or neighbor.ndim != 3 or neighbor.shape[2] < 3:
        return 0.0
    return float(numpy.mean(numpy.abs(_rgb_mean(edge) - _rgb_mean(neighbor[:, :, :3]))))


def _empty_details() -> dict[str, Any]:
    edges = {
        edge: {
            "risk": 0.0,
            "luminance_drift": 0.0,
            "rgb_drift": 0.0,
            "border_gradient": 0.0,
            "neighbor_drift": 0.0,
        }
        for edge in ("left", "right", "top", "bottom")
    }
    return {"worst_edge": "left", "edges": edges, "neighbor_compared": False}
```

Update `src/O4_Provider_Score_Edges.py` to export the new seam helper:

```python
from O4_Provider_Score_Color import color_drift_score
from O4_Provider_Score_Seams import seam_risk_score, seam_risk_score_details

__all__ = ["color_drift_score", "seam_risk_score", "seam_risk_score_details"]
```

Replace `src/O4_Provider_Scoring.py` with this content so score entry points accept optional context while existing callers remain valid:

```python
"""Provider imagery quality scoring for downloaded texture images."""

from __future__ import annotations

from PIL import Image

import O4_UI_Utils as UI
from O4_Provider_Score_Metrics import compute_provider_score_metrics
from O4_Provider_Score_Models import (
    ProviderScoreContext,
    ProviderScoreMetrics,
    ProviderScoreResult,
    TextureAttributes,
)
from O4_Texture_Source import TextureSource


def score_provider_image(
    provider_code: str,
    texture_attributes: TextureAttributes,
    image: Image.Image,
    scoring_context: ProviderScoreContext | None = None,
) -> ProviderScoreResult:
    metrics = compute_provider_score_metrics(image, scoring_context)
    return provider_score_from_metrics(provider_code, texture_attributes, metrics)


def provider_score_from_metrics(
    provider_code: str,
    texture_attributes: TextureAttributes,
    metrics: ProviderScoreMetrics,
) -> ProviderScoreResult:
    clamped = metrics.clamped()
    artifact_risk = (
        clamped.noise
        + clamped.jpeg_compression
        + clamped.clouds
        + clamped.color_drift
        + clamped.seam_risk
    ) / 5
    global_score = round(100 - artifact_risk, 2)
    return ProviderScoreResult(
        provider_code=provider_code,
        texture_attributes=texture_attributes,
        metrics=clamped,
        global_score=global_score,
        quality_label=_quality_label(global_score),
    )


def log_provider_score(result: ProviderScoreResult) -> None:
    UI.log_event("Provider imagery score", level="INFO", context=result.to_context())


def score_and_log_provider_image(
    provider_code: str,
    texture_attributes: TextureAttributes,
    image: Image.Image,
    scoring_context: ProviderScoreContext | None = None,
) -> ProviderScoreResult:
    result = score_provider_image(
        provider_code,
        texture_attributes,
        image,
        scoring_context,
    )
    log_provider_score(result)
    return result


def scored_value[T](
    value: T, texture_attributes: TextureAttributes, image: Image.Image
) -> T:
    score_and_log_provider_image(texture_attributes[3], texture_attributes, image)
    return value


def texture_source(
    tile: object,
    texture_attributes: TextureAttributes,
    image: Image.Image,
    cache: tuple[str | None, bool],
) -> TextureSource:
    score_and_log_provider_image(texture_attributes[3], texture_attributes, image)
    cache_path, wrote_cache = cache
    return TextureSource(tile, texture_attributes, image, cache_path, wrote_cache)


def _quality_label(global_score: float) -> str:
    if global_score >= 90:
        return "excellent"
    if global_score >= 75:
        return "good"
    if global_score >= 60:
        return "fair"
    return "poor"
```

Update `src/O4_Provider_Score_Metrics.py` so the seam helper and details are used:

```python
"""Metric orchestration for provider imagery scoring."""

from PIL import Image

import O4_Provider_Score_Artifacts as ART
import O4_Provider_Score_Edges as EDGE
from O4_Provider_Score_Models import ProviderScoreContext, ProviderScoreMetrics


def compute_provider_score_metrics(
    image: Image.Image,
    scoring_context: ProviderScoreContext | None = None,
) -> ProviderScoreMetrics:
    sample = ART.sample_rgb_array(image)
    luma = ART.luminance(sample)
    cloud_risk, cloud_details = ART.cloud_score_details(sample)
    seam_risk, seam_details = EDGE.seam_risk_score_details(sample, scoring_context)
    return ProviderScoreMetrics(
        noise=ART.noise_score(sample),
        jpeg_compression=ART.jpeg_compression_score(luma),
        clouds=cloud_risk,
        color_drift=EDGE.color_drift_score(sample),
        seam_risk=seam_risk,
        details={
            "clouds": cloud_details,
            "seam_risk": seam_details,
        },
    )
```

- [ ] **Step 4: Run the seam tests to verify they pass**

Run:

```bash
uv run python -m unittest tests.test_provider_scoring.ProviderScoringTests.test_single_problematic_edge_increases_seam_risk_and_identifies_edge tests.test_provider_scoring.ProviderScoringTests.test_abrupt_border_gradient_increases_seam_risk tests.test_provider_scoring.ProviderScoringTests.test_neighbor_edge_mismatch_increases_seam_risk_when_context_is_supplied
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/O4_Provider_Score_Seams.py src/O4_Provider_Score_Edges.py src/O4_Provider_Score_Metrics.py src/O4_Provider_Scoring.py tests/test_provider_scoring.py
git commit -m "feat: improve provider seam scoring"
```

## Task 4: Integration Logging and TODO Evidence

**Files:**
- Modify: `tests/test_provider_scoring_integration.py`
- Modify: `TODO.md`

**Interfaces:**
- Consumes: `ProviderScoreResult.to_context()` from Task 1 and metric details from Tasks 2-3.
- Produces: integration evidence that `Provider imagery score` logs contain `details.clouds` and `details.seam_risk`.

- [ ] **Step 1: Write the failing integration assertion**

In `test_build_texture_source_records_provider_score()` in `tests/test_provider_scoring_integration.py`, add these assertions after `self.assertGreaterEqual(score_context["global_score"], 90)`:

```python
        self.assertIn("details", score_context)
        self.assertIn("clouds", score_context["details"])
        self.assertIn("seam_risk", score_context["details"])
        self.assertIn(
            "cloud_coverage_pct",
            score_context["details"]["clouds"],
        )
        self.assertIn("worst_edge", score_context["details"]["seam_risk"])
```

- [ ] **Step 2: Run the integration test**

Run:

```bash
uv run python -m unittest tests.test_provider_scoring_integration.ProviderScoringIntegrationTests.test_build_texture_source_records_provider_score
```

Expected after Tasks 1-3: PASS. If running this task before Tasks 1-3, expected failure is missing `details`.

- [ ] **Step 3: Run focused provider scoring tests**

Run:

```bash
uv run python -m unittest tests.test_provider_scoring tests.test_provider_scoring_integration
```

Expected: PASS.

- [ ] **Step 4: Run changed-file lint and type checks**

Run:

```bash
uv run ruff format src\O4_Provider_Score_Models.py src\O4_Provider_Score_Clouds.py src\O4_Provider_Score_Seams.py src\O4_Provider_Score_Metrics.py src\O4_Provider_Score_Edges.py src\O4_Provider_Scoring.py tests\test_provider_scoring.py tests\test_provider_scoring_integration.py
uv run ruff check src\O4_Provider_Score_Models.py src\O4_Provider_Score_Clouds.py src\O4_Provider_Score_Seams.py src\O4_Provider_Score_Metrics.py src\O4_Provider_Score_Edges.py src\O4_Provider_Scoring.py tests\test_provider_scoring.py tests\test_provider_scoring_integration.py
uv run ty check src\O4_Provider_Score_Models.py src\O4_Provider_Score_Clouds.py src\O4_Provider_Score_Seams.py src\O4_Provider_Score_Metrics.py src\O4_Provider_Score_Edges.py src\O4_Provider_Scoring.py
```

Expected: all commands PASS. If `ruff format` changes files, rerun the focused tests from Step 3 after formatting.

- [ ] **Step 5: Run broader verification**

Run:

```bash
uv run python -m unittest discover -s tests
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected: all commands PASS.

- [ ] **Step 6: Update TODO-041 evidence**

After verification passes, update `TODO.md` under `TODO-041`:

```markdown
Status: Done

Completion note: implemented deterministic provider imagery cloud and seam
detection enhancements in the existing provider scoring modules. Cloud scoring
now combines dense-cloud, atmospheric-veil, blue-sky exclusion, and 5 percent
tolerance logic. Seam scoring now analyzes all four edges independently,
records worst-edge diagnostics, detects abrupt border gradients, and accepts
optional neighbor-edge context without adding required CV or ML dependencies.

Verification note: focused provider scoring tests, provider scoring integration
tests, full unittest discovery, changed-file Ruff/format/ty checks, and the full
repository quality gate passed.
```

- [ ] **Step 7: Commit Task 4**

```bash
git add TODO.md tests/test_provider_scoring_integration.py
git commit -m "docs: close ai cloud seam detection"
```

## Self-Review Checklist

- Spec coverage: Tasks 1-4 cover cloud criteria, haze/veil, blue-sky exclusion, 5 percent tolerance, four-edge seam analysis, abrupt gradients, optional neighbor-edge context, structured details, deterministic tests, no new heavy dependencies, and TODO evidence.
- Placeholder scan: this plan intentionally contains no `TBD`, `TODO`, `implement later`, or unspecified code steps.
- Type consistency: `ProviderScoreContext`, `ProviderScoreMetrics.details`, `cloud_score_details()`, `seam_risk_score_details()`, and `scoring_context` are introduced before any task consumes them.
