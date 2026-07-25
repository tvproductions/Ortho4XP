"""Pure geometry checks and bounded convolution for XP12 sand masks."""

import math
from dataclasses import dataclass
from numbers import Real

import numpy


@dataclass(frozen=True)
class SandMaskGeometry:
    width_pixels: int
    kernel_size: int


def _is_finite_real(value):
    """Convert real-number implementations without leaking overflow."""
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def validate_sand_mask(width_meters, pixel_size, image_shape):
    """Return safe pixel geometry or reject malformed sand-mask inputs."""
    width = _validated_width(width_meters)
    scale = _validated_pixel_size(pixel_size)
    shape = _validated_image_shape(image_shape)
    width_pixels = _width_pixels(width, scale)
    kernel_size = _kernel_size(width_pixels)
    if kernel_size > min(shape):
        raise ValueError(f"sand mask kernel {kernel_size} exceeds image shape {shape}")
    return SandMaskGeometry(width_pixels, kernel_size)


def _validated_width(value) -> float:
    """Normalize the user width while rejecting booleans and vector shapes.

    Sand mode accepts one scalar width.  The three-element configuration used
    by ``3steps`` must fail here before existing mask artifacts are removed.
    """
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("sand masks_width must be one finite non-negative number")
    if not _is_finite_real(value) or value < 0:
        raise ValueError("sand masks_width must be one finite non-negative number")
    return float(value)


def _validated_pixel_size(value) -> float:
    """Normalize the meter-to-pixel scale required for kernel sizing."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("sand mask pixel size must be finite and positive")
    if not _is_finite_real(value) or value <= 0:
        raise ValueError("sand mask pixel size must be finite and positive")
    return float(value)


def _validated_image_shape(image_shape) -> tuple[int, int]:
    """Require exactly two positive dimensions for separable convolution."""
    try:
        height, width = image_shape
    except (TypeError, ValueError):
        raise ValueError("sand mask input must be a non-empty 2D array") from None
    shape = (height, width)
    if not all(_is_positive_int(size) for size in shape):
        raise ValueError("sand mask input must be a non-empty 2D array")
    return shape


def _is_positive_int(value) -> bool:
    """Keep booleans and non-integral array metadata out of image geometry."""
    return not isinstance(value, bool) and isinstance(value, int) and value > 0


def _width_pixels(width_meters: float, pixel_size: float) -> int:
    """Convert meters to a bounded integral half-width."""
    try:
        return int(width_meters / pixel_size)
    except OverflowError:
        raise ValueError("sand mask width in pixels must be finite") from None


def _kernel_size(width_pixels: int) -> int:
    """Return the odd hat-kernel length, preserving the zero-width no-op."""
    return 0 if width_pixels == 0 else 2 * width_pixels - 1


def blur_sand_mask(img_array, width_meters, pixel_size):
    """Apply the validated separable hat convolution used by sand mode."""
    geometry = validate_sand_mask(width_meters, pixel_size, img_array.shape)
    if not geometry.width_pixels:
        return numpy.array(img_array, dtype=numpy.uint8)
    kernel = _hat_kernel(geometry.width_pixels)
    blurred = _convolve_rows(numpy.array(img_array), kernel)
    blurred = _convolve_rows(blurred.transpose(), kernel).transpose()
    return numpy.array(2 * numpy.minimum(blurred, 127), dtype=numpy.uint8)


def _hat_kernel(width_pixels: int):
    """Build a normalized triangular kernel with a single center maximum."""
    kernel = numpy.array(range(1, 2 * width_pixels))
    kernel[width_pixels:] = range(width_pixels - 1, 0, -1)
    return kernel / width_pixels**2


def _convolve_rows(image, kernel):
    """Apply one convolution axis in place to limit peak build memory."""
    for index, row in enumerate(image):
        image[index] = numpy.convolve(row, kernel, "same")
    return image
