import math
from dataclasses import dataclass
from numbers import Real


@dataclass(frozen=True)
class SandMaskGeometry:
    width_pixels: int
    kernel_size: int


def validate_sand_mask(width_meters, pixel_size, image_shape):
    if (
        isinstance(width_meters, bool)
        or not isinstance(width_meters, Real)
        or not math.isfinite(float(width_meters))
        or width_meters < 0
    ):
        raise ValueError("sand masks_width must be one finite non-negative number")
    if (
        isinstance(pixel_size, bool)
        or not isinstance(pixel_size, Real)
        or not math.isfinite(float(pixel_size))
        or pixel_size <= 0
    ):
        raise ValueError("sand mask pixel size must be finite and positive")
    try:
        shape_dimensions = len(image_shape)
    except TypeError:
        raise ValueError("sand mask input must be a non-empty 2D array") from None
    if shape_dimensions != 2 or any(
        isinstance(size, bool) or not isinstance(size, int) or size <= 0
        for size in image_shape
    ):
        raise ValueError("sand mask input must be a non-empty 2D array")
    width_pixels = int(width_meters / pixel_size)
    kernel_size = 0 if width_pixels == 0 else 2 * width_pixels - 1
    if kernel_size > min(image_shape):
        raise ValueError(
            f"sand mask kernel {kernel_size} exceeds image shape {image_shape}"
        )
    return SandMaskGeometry(width_pixels, kernel_size)
