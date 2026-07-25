"""Optional DDS compression quality checks for generated textures."""

import math
import os
from dataclasses import dataclass
from typing import Literal

import numpy
from PIL import Image

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

# DDS QA policy:
# - Disabled unless tile config opts in.
# - Runs only after the native DDS encoder reports success.
# - Uses Pillow's DDS reader to exercise the actual compressed output.
# - Reports decode and metric problems as warnings, not conversion failures.
# - Keeps metrics dependency-light: NumPy arrays, MSE, and PSNR.


@dataclass(frozen=True)
class DdsQualityMetrics:
    mse: float
    psnr: float
    width: int
    height: int


DdsQualityDisposition = Literal[
    "skipped",
    "passed",
    "below_threshold",
    "error",
]


@dataclass(frozen=True)
class DdsQualityCheckResult:
    disposition: DdsQualityDisposition
    metrics: DdsQualityMetrics | None = None
    error_summary: str = ""

    @property
    def allows_cleanup(self) -> bool:
        return self.disposition in ("skipped", "passed")


@dataclass(frozen=True)
class DdsQualityRequest:
    source_png_path: str
    dds_path: str
    decoded_png_path: str
    threshold: float
    display_name: str


def decode_dds_to_png(dds_path: str, decoded_png_path: str) -> None:
    with Image.open(dds_path) as image:
        os.makedirs(os.path.dirname(decoded_png_path), exist_ok=True)
        image.save(decoded_png_path, format="PNG")


def compute_quality_metrics(source_path: str, decoded_path: str) -> DdsQualityMetrics:
    with (
        Image.open(source_path) as source_image,
        Image.open(decoded_path) as decoded_image,
    ):
        source, decoded = _comparable_images(source_image, decoded_image)
        source_array = numpy.asarray(source, dtype=numpy.float64)
        decoded_array = numpy.asarray(decoded, dtype=numpy.float64)

    if source_array.shape != decoded_array.shape:
        raise ValueError(
            "DDS QA images have different shapes: "
            f"{source_array.shape} != {decoded_array.shape}"
        )
    mse = float(numpy.mean((source_array - decoded_array) ** 2))
    return DdsQualityMetrics(
        mse=mse,
        psnr=_psnr(mse),
        width=int(source_array.shape[1]),
        height=int(source_array.shape[0]),
    )


def run_enabled_dds_quality_check(tile, encode_result) -> DdsQualityCheckResult:
    if not encode_result.ok or not getattr(tile, "dds_qa_enabled", False):
        return DdsQualityCheckResult("skipped")
    request = encode_result.request
    return run_dds_quality_check(
        DdsQualityRequest(
            request.source_path,
            request.output_path,
            os.path.join(FNAMES.resource_path("tmp"), f"{request.display_name}.qa.png"),
            float(getattr(tile, "dds_qa_psnr_threshold", 30.0)),
            request.display_name,
        )
    )


def run_dds_quality_check(request: DdsQualityRequest) -> DdsQualityCheckResult:
    try:
        decode_dds_to_png(request.dds_path, request.decoded_png_path)
        metrics = compute_quality_metrics(
            request.source_png_path, request.decoded_png_path
        )
    except Exception as exc:
        error_summary = f"{type(exc).__name__}: {exc}"
        UI.vprint(
            1,
            "WARNING: DDS QA failed for",
            request.display_name,
            error_summary,
        )
        return DdsQualityCheckResult("error", error_summary=error_summary)

    if metrics.psnr < request.threshold:
        UI.vprint(
            1,
            "WARNING: DDS QA quality below threshold for",
            request.display_name,
            f"PSNR={metrics.psnr:.2f} dB",
            f"threshold={request.threshold:.2f} dB",
            f"MSE={metrics.mse:.2f}",
        )
        return DdsQualityCheckResult("below_threshold", metrics)
    return DdsQualityCheckResult("passed", metrics)


def _comparable_images(source_image, decoded_image):
    mode = "RGBA" if "A" in (source_image.mode + decoded_image.mode) else "RGB"
    return source_image.convert(mode), decoded_image.convert(mode)


def _psnr(mse: float) -> float:
    if mse == 0:
        return math.inf
    return 20 * math.log10(255.0 / math.sqrt(mse))
