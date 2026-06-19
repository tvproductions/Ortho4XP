"""Color filter operations for provider texture preprocessing."""

from collections.abc import Callable
from math import pi, tan
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter

FilterOperation = Callable[[Image.Image, list[Any]], Image.Image]


def color_transform(
    im: Image.Image, color_code: str, color_filters_dict: dict[str, Any]
):
    try:
        for color_filter in color_filters_dict[color_code]:
            im = _apply_color_filter(im, color_filter)
        return im
    except (TypeError, ValueError):
        return im


def _apply_color_filter(im: Image.Image, color_filter: list[Any]) -> Image.Image:
    handler = _FILTER_OPERATIONS.get(color_filter[0])
    if handler is not None:
        return handler(im, color_filter)
    return im


def _apply_brightness_contrast_step(
    im: Image.Image, color_filter: list[Any]
) -> Image.Image:
    brightness, contrast = color_filter[1:3]
    return _apply_brightness_contrast(im, brightness, contrast)


def _apply_brightness_contrast(
    im: Image.Image, brightness: float, contrast: float
) -> Image.Image:
    # Both values range from -127 to 127.
    # http://gimp.sourcearchive.com/documentation/2.6.1/
    # gimpbrightnesscontrastconfig_8c-source.html
    contrast_factor = tan(pi / 4 * (1 + contrast / 128))
    if brightness >= 0:
        return im.point(
            lambda i: (
                128
                + contrast_factor * (brightness + (255 - brightness) / 255 * i - 128)
            )
        )
    return im.point(
        lambda i: 128 + contrast_factor * ((255 + brightness) / 255 * i - 128)
    )


def _apply_saturation(im: Image.Image, color_filter: list[Any]) -> Image.Image:
    saturation = color_filter[1]
    return ImageEnhance.Color(im).enhance(1 + saturation / 100)


def _apply_sharpness(im: Image.Image, color_filter: list[Any]) -> Image.Image:
    return ImageEnhance.Sharpness(im).enhance(color_filter[1])


def _apply_sharpen(im: Image.Image, color_filter: list[Any]) -> Image.Image:
    radius, amount, threshold = color_filter[1:4]
    return im.filter(
        ImageFilter.UnsharpMask(
            radius=radius,
            percent=int(amount),
            threshold=int(threshold),
        )
    )


def _apply_blur(im: Image.Image, color_filter: list[Any]) -> Image.Image:
    return im.filter(ImageFilter.GaussianBlur(color_filter[1]))


def _apply_levels(im: Image.Image, color_filter: list[Any]) -> Image.Image:
    # Levels range between 0 and 255; gamma is neutral at 1.
    # https://pippin.gimp.org/image-processing/chap_point.html
    bands = im.split()
    for j in [0, 1, 2]:
        in_min, gamma, in_max, out_min, out_max = color_filter[5 * j + 1 : 5 * j + 6]
        bands[j].paste(
            bands[j].point(
                lambda i, in_min=in_min, gamma=gamma, in_max=in_max, out_min=out_min, out_max=out_max: (
                    out_min
                    + (out_max - out_min)
                    * ((max(in_min, min(i, in_max)) - in_min) / (in_max - in_min))
                    ** (1 / gamma)
                )
            )
        )
    return Image.merge(im.mode, bands)


_FILTER_OPERATIONS: dict[str, FilterOperation] = {
    "brightness-contrast": _apply_brightness_contrast_step,
    "saturation": _apply_saturation,
    "sharpness": _apply_sharpness,
    "sharpen": _apply_sharpen,
    "blur": _apply_blur,
    "levels": _apply_levels,
}
