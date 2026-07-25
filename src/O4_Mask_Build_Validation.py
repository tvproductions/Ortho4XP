"""Preflight validation for mask-build filesystem and sand geometry inputs."""

import os

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Mask_Validation as MV
import O4_UI_Utils as UI


def mask_build_inputs_are_valid(tile):
    """Report invalid prerequisites before any mask output is replaced."""
    mesh_path = FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)
    if not os.path.exists(mesh_path):
        UI.lvprint(0, "ERROR: Mesh file ", mesh_path, "absent.")
        UI.exit_message_and_bottom_line("")
        return False
    if tile.masking_mode != "sand":
        return True
    pixel_size = GEO.webmercator_pixel_size(tile.lat + 0.5, tile.mask_zl)
    try:
        MV.validate_sand_mask(
            tile.masks_width,
            pixel_size,
            (4096 + 2 * 1024, 4096 + 2 * 1024),
        )
    except ValueError as exc:
        UI.lvprint(0, f"ERROR: Invalid sand mask configuration: {exc}")
        UI.exit_message_and_bottom_line("")
        return False
    return True
