from dataclasses import dataclass

import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Mask_Utils as MASK
import O4_Mesh_Utils as MESH
import O4_Tile_Utils as TILE
import O4_UI_Utils as UI
import O4_Vector_Map as VMAP


@dataclass(frozen=True)
class BuildResult:
    ok: bool
    step: str
    message: str = ""


def build_tile_all(tile) -> BuildResult:
    """Run the current all-in-one tile sequence and return its structured result."""
    VMAP.build_poly_file(tile)
    if UI.red_flag:
        return _interrupted("vector")

    MESH.build_mesh(tile)
    if UI.red_flag:
        return _interrupted("mesh")

    MASK.build_masks(tile)
    if UI.red_flag:
        return _interrupted("masks")

    TILE.build_tile(tile)
    if UI.red_flag:
        return _interrupted("tile")

    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    if tile_coords in IMG.incomplete_imgs:
        _retry_incomplete_textures(tile, tile_coords)
        if UI.red_flag:
            return _interrupted("retry")

    UI.is_working = 0  # ty:ignore[invalid-assignment]
    _report_remaining_incomplete_textures()
    return BuildResult(ok=True, step="all")


def _interrupted(step: str) -> BuildResult:
    UI.exit_message_and_bottom_line("")
    return BuildResult(False, step, "interrupted")


def _retry_incomplete_textures(tile, tile_coords: str) -> None:
    UI.lvprint(
        1,
        f"Attempting to rebuild textures with white squares: "
        f"{IMG.incomplete_texture_file_names(tile_coords)}",
    )
    TILE.delete_incomplete_imgs(tile)
    TILE.build_tile(tile)


def _report_remaining_incomplete_textures() -> None:
    if IMG.incomplete_imgs:
        UI.lvprint(
            0,
            f"\nERROR: Parts of the following images could not be obtained "
            f"and have been filled with white: "
            f"{IMG.incomplete_texture_file_names_by_tile()}",
        )
