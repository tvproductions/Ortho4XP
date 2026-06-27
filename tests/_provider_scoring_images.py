"""Image fixtures for provider scoring tests."""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image


def image_from_coords(
    pixel_fn: Callable[[int, int], tuple[int, int, int]],
) -> Image.Image:
    image = Image.new("RGB", (32, 32))
    image.putdata([pixel_fn(x, y) for y in range(32) for x in range(32)])
    return image


def uniform_image(
    color: tuple[int, int, int], size: tuple[int, int] = (32, 32)
) -> Image.Image:
    return Image.new("RGB", size, color)


def blocky_cloudy_edge_drift_image() -> Image.Image:
    # Mirrors the mixed-artifact fixture used by the quality scoring regression.
    pixels = []
    for y in range(32):
        for x in range(32):
            if x < 8:
                pixels.append((240, 240, 240))
            elif x >= 24:
                pixels.append((15, 45, 110))
            elif (x // 8 + y // 8) % 2 == 0:
                pixels.append((55, 75, 55))
            else:
                pixels.append((40, 70, 40))
    image = Image.new("RGB", (32, 32))
    image.putdata(pixels)
    return image


def cloud_coverage_image(cloud_pixels: int) -> Image.Image:
    # Cloud pixels are filled from the start of the buffer so coverage stays
    # deterministic without adding coordinate-specific logic to each test.
    image = uniform_image((80, 130, 85), size=(20, 20))
    pixels = [(80, 130, 85)] * 400
    for index in range(cloud_pixels):
        pixels[index] = (242, 242, 242)
    image.putdata(pixels)
    return image


def right_edge_problem_image() -> Image.Image:
    return image_from_coords(
        lambda x, _y: (210, 210, 210) if x >= 30 else (95, 130, 95)
    )


def top_gradient_problem_image() -> Image.Image:
    return image_from_coords(lambda _x, y: (225, 225, 225) if y == 1 else (90, 125, 90))
