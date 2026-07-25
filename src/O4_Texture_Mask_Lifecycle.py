"""Texture-mask inputs and cleanup ownership for DDS conversion.

Mask files are source artifacts until an encoded DDS exists and optional
quality assurance accepts it. Temporary conversion images have shorter
ownership and are always removable after an encode attempt.
"""

import os
from dataclasses import dataclass

from PIL import Image

import O4_File_Names as FNAMES
import O4_UI_Utils as UI


@dataclass(frozen=True)
class DdsMaskInput:
    """A detached grayscale mask plus the source path that owns it."""

    image: Image.Image
    path: str


@dataclass(frozen=True)
class TextureCleanupPlan:
    """Paths removed after every attempt and only after accepted success."""

    always_paths: tuple[str, ...] = ()
    success_paths: tuple[str, ...] = ()


def load_dds_mask(tile, texture_attrs) -> DdsMaskInput | None:
    """Load an imprinted DDS mask without retaining an open file handle."""
    if not tile.imprint_masks_to_dds:
        return None
    mask_path = os.path.join(
        tile.build_dir,
        "textures",
        FNAMES.mask_file(*texture_attrs),
    )
    if not os.path.exists(mask_path):
        return None
    with Image.open(mask_path) as mask_image:
        return DdsMaskInput(mask_image.convert("L"), mask_path)


def cleanup_plan(file_to_convert, erase_temporary, mask_input):
    """Build the two-phase cleanup contract for one DDS conversion."""
    return TextureCleanupPlan(
        always_paths=(file_to_convert,) if erase_temporary else (),
        success_paths=(mask_input.path,) if mask_input is not None else (),
    )


def cleanup_conversion_paths(paths: tuple[str, ...]) -> None:
    """Remove conversion-owned paths while retaining legacy diagnostic logging."""
    for path in paths:
        try:
            os.remove(path)
        except OSError as exc:
            UI.vprint(3, exc)


def save_conversion_temp(image, path: str) -> None:
    """Remove a partial file when image serialization does not complete."""
    saved = False
    try:
        image.save(path)
        saved = True
    finally:
        if not saved:
            cleanup_conversion_paths((path,))
