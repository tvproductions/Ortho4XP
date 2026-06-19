"""Config-driven resampling policy for Pillow and GDAL call sites."""

from typing import Any

from PIL import Image

from O4_Cfg_Vars import cfg_tile_vars

RESAMPLING_METHODS = ("nearest", "bilinear", "bicubic", "lanczos")

_PILLOW_RESAMPLING = {
    "nearest": Image.Resampling.NEAREST,
    "bilinear": Image.Resampling.BILINEAR,
    "bicubic": Image.Resampling.BICUBIC,
    "lanczos": Image.Resampling.LANCZOS,
}

_GDAL_RESAMPLING = {
    "nearest": "near",
    "bilinear": "bilinear",
    "bicubic": "cubic",
    "lanczos": "lanczos",
}


def pillow_resampling(method: str) -> Image.Resampling:
    try:
        return _PILLOW_RESAMPLING[method]
    except KeyError as exc:
        raise ValueError(f"Unsupported resampling method: {method}") from exc


def gdal_resampling(method: str) -> str:
    try:
        return _GDAL_RESAMPLING[method]
    except KeyError as exc:
        raise ValueError(f"Unsupported resampling method: {method}") from exc


def tile_pillow_resampling(tile: Any, key: str) -> Image.Resampling:
    return pillow_resampling(_tile_resampling_method(tile, key))


def tile_gdal_resampling(tile: Any, key: str) -> str:
    return gdal_resampling(_tile_resampling_method(tile, key))


def resize_image(method: str, image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return image.resize(size, pillow_resampling(method))


def tile_resize_image(
    tile: Any, key: str, image: Image.Image, size: tuple[int, int]
) -> Image.Image:
    return image.resize(size, tile_pillow_resampling(tile, key))


def _tile_resampling_method(tile: Any, key: str) -> str:
    method = getattr(tile, key, cfg_tile_vars[key]["default"])
    if not isinstance(method, str):
        raise ValueError(f"Unsupported resampling method: {method}")
    return method
