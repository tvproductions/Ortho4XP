import O4_Build_Context as BC
import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Mask_Utils as MASK
import O4_Mesh_Utils as MESH
import O4_Overlay_Utils as OVL
import O4_Tile_Utils as TILE
import O4_UI_Utils as UI
import O4_Vector_Map as VMAP


def steps_need_tile_directory(steps: tuple[str, ...]) -> bool:
    return bool({"vector", "mesh", "tile"}.intersection(steps))


def run_batch_step(step: str, tile, ctx: BC.BuildContext) -> int:
    if step == "tile":
        return run_batch_tile_step(tile, ctx)
    runner = _RUN_BATCH_STEP_DISPATCH.get(step)
    if runner is None:
        raise ValueError(f"unknown build step: {step}")
    return runner(tile, ctx)


def run_batch_tile_step(tile, ctx: BC.BuildContext) -> int:
    result = TILE.build_tile(tile, ctx=ctx)
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    if tile_coords in IMG.incomplete_imgs:
        _retry_incomplete_textures(tile, ctx, tile_coords)
    if ctx.red_flag:
        return 0
    return result


def _retry_incomplete_textures(tile, ctx, tile_coords: str) -> None:
    UI.lvprint(
        1,
        f"Attempting to rebuild textures with white squares: "
        f"{IMG.incomplete_texture_file_names(tile_coords)}",
    )
    TILE.delete_incomplete_imgs(tile)
    TILE.build_tile(tile, ctx=ctx)


def _run_batch_vector_step(tile, ctx: BC.BuildContext) -> int:
    return VMAP.build_poly_file(tile, ctx=ctx)


def _run_batch_mesh_step(tile, ctx: BC.BuildContext) -> int:
    return MESH.build_mesh(tile, ctx=ctx)


def _run_batch_mask_step(tile, ctx: BC.BuildContext) -> int:
    return MASK.build_masks(tile, ctx=ctx)


def _run_batch_overlay_step(tile, ctx: BC.BuildContext) -> int:
    return OVL.build_overlay(tile.lat, tile.lon)


_RUN_BATCH_STEP_DISPATCH = {
    "vector": _run_batch_vector_step,
    "mesh": _run_batch_mesh_step,
    "masks": _run_batch_mask_step,
    "overlays": _run_batch_overlay_step,
}
