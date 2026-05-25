"""Small sRGB transfer-function helpers used by texture normalization."""

import numpy


def srgb_to_linear_array(values):
    """Convert 8-bit sRGB values to normalized linear-light floats."""

    srgb = numpy.asarray(values, dtype=numpy.float64) / 255.0
    return numpy.where(
        srgb <= 0.04045,
        srgb / 12.92,
        numpy.power((srgb + 0.055) / 1.055, 2.4),
    )


def linear_to_srgb_array(values):
    """Convert normalized linear-light floats to clipped 8-bit sRGB values."""

    linear = numpy.clip(numpy.asarray(values, dtype=numpy.float64), 0.0, 1.0)
    srgb = numpy.where(
        linear <= 0.0031308,
        linear * 12.92,
        1.055 * numpy.power(linear, 1 / 2.4) - 0.055,
    )
    return numpy.clip(numpy.rint(srgb * 255), 0, 255).astype(numpy.uint8)
