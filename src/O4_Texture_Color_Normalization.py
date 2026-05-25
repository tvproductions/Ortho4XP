"""Texture-cache integration helpers for sRGB color normalization.

The imagery module owns provider downloads and texture conversion.  This module
owns the smaller normalization workflow that sits between those legacy stages:
build a context for one complete texture, discover cached north/south/east/west
neighbors in the same provider cache directory, skip missing or invalid files,
and delegate the actual color math to ``O4_Color_Normalization``.

Keeping this code separate prevents the large conversion functions from
absorbing neighbor lookup, temporary PNG creation, and combined-provider logging
branches.  The helpers return original images and paths unchanged when the
feature is disabled, so callers can use them without adding extra control flow.
"""

from dataclasses import dataclass
import os

from PIL import Image, UnidentifiedImageError

from O4_Color_Normalization import normalize_image_with_neighbors
import O4_File_Names as FNAMES
import O4_UI_Utils as UI


@dataclass(frozen=True)
class TextureColorContext:
    file_dir: str
    tile_x: int
    tile_y: int
    zoomlevel: int
    provider_code: str
    enabled: bool


_NEIGHBOR_TEXTURE_OFFSETS = {
    "north": (0, -16),
    "south": (0, 16),
    "west": (-16, 0),
    "east": (16, 0),
}


def texture_color_context(file_dir, texture_attrs, enabled):
    if file_dir is None:
        return None
    tile_x, tile_y, zoomlevel, provider_code = texture_attrs
    return TextureColorContext(
        file_dir,
        tile_x,
        tile_y,
        zoomlevel,
        provider_code,
        enabled,
    )


def normalize_completed_texture_image(image, success, context):
    if not success:
        return image
    return normalize_texture_image_if_enabled(image, context)


def normalize_combined_texture_image(image, context, provider_code, enabled):
    if context is not None:
        return normalize_texture_image_if_enabled(image, context)
    if enabled:
        UI.vprint(
            3,
            "Skipping texture color normalization for combined provider",
            provider_code,
            "because no cached provider directory is available for neighbor lookup.",
        )
    return image


def normalized_conversion_input_path(source_path, target_png_file_name, context):
    if context is None or not context.enabled:
        return source_path, False

    image = Image.open(source_path, "r").convert("RGB")
    image = normalize_texture_image_if_enabled(image, context)
    file_to_convert = os.path.join(FNAMES.resource_path("tmp"), target_png_file_name)
    image.save(file_to_convert)
    return file_to_convert, True


def texture_path_missing(path):
    return not path or not os.path.exists(path)


def normalize_texture_image_if_enabled(image, context):
    if context is None or not context.enabled:
        return image
    neighbors = load_neighbor_texture_images(context, image.size)
    if not neighbors:
        return image
    return normalize_image_with_neighbors(image, neighbors)


def load_neighbor_texture_images(context, target_size):
    neighbors = {}
    for edge, offset in _NEIGHBOR_TEXTURE_OFFSETS.items():
        neighbor = _load_neighbor_image(context, offset, target_size)
        if neighbor is not None:
            neighbors[edge] = neighbor
    return neighbors


def _load_neighbor_image(context, offset, target_size):
    neighbor_path = _neighbor_texture_path(context, offset)
    if not os.path.isfile(neighbor_path):
        return None
    try:
        return _read_neighbor_image(neighbor_path, target_size)
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        UI.vprint(
            3,
            "Skipping color-normalization neighbor",
            neighbor_path,
            exc,
        )
    return None


def _neighbor_texture_path(context, offset):
    dx, dy = offset
    neighbor_file = FNAMES.jpeg_file_name_from_attributes(
        context.tile_x + dx,
        context.tile_y + dy,
        context.zoomlevel,
        context.provider_code,
    )
    return os.path.join(context.file_dir, neighbor_file)


def _read_neighbor_image(neighbor_path, target_size):
    with Image.open(neighbor_path) as neighbor:
        if neighbor.size != target_size:
            UI.vprint(
                3,
                "Skipping color-normalization neighbor with unexpected size",
                neighbor_path,
                neighbor.size,
            )
            return None
        return neighbor.convert("RGB")
