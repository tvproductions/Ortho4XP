from collections.abc import Callable
from dataclasses import dataclass

import O4_Build_Context as BC
import O4_Build_Models as MODELS
import O4_Config_Utils as CFG
import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Mask_Utils as MASK
import O4_Mesh_Utils as MESH
import O4_Overlay_Utils as OVL
import O4_Tile_Utils as TILE
import O4_UI_Utils as UI
import O4_Vector_Map as VMAP


@dataclass(frozen=True)
class BuildResult:
    ok: bool
    step: str
    message: str = ""


TileCompleteCallback = Callable[[MODELS.BuildTileResult], None]


def build_tile_all(tile) -> BuildResult:
    """Run the current all-in-one tile sequence and return its structured result."""
    ctx = BC.BuildContext()
    interrupted = _run_build_steps(tile, ctx)
    if interrupted:
        return interrupted

    interrupted = _retry_incomplete_textures_if_needed(tile, ctx)
    if interrupted:
        return interrupted

    ctx.is_working = False
    _report_remaining_incomplete_textures()
    return BuildResult(ok=True, step="all")


def _run_build_steps(tile, ctx) -> BuildResult | None:
    for step, build_step in _build_steps():
        build_step(tile, ctx=ctx)
        if ctx.red_flag:
            return _interrupted(step)
    return None


def _build_steps():
    return (
        ("vector", VMAP.build_poly_file),
        ("mesh", MESH.build_mesh),
        ("masks", MASK.build_masks),
        ("tile", TILE.build_tile),
    )


def _interrupted(step: str) -> BuildResult:
    UI.exit_message_and_bottom_line("")
    return BuildResult(False, step, "interrupted")


def _retry_incomplete_textures_if_needed(tile, ctx) -> BuildResult | None:
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    if tile_coords not in IMG.incomplete_imgs:
        return None
    _retry_incomplete_textures(tile, ctx, tile_coords)
    if ctx.red_flag:
        return _interrupted("retry")
    return None


def _retry_incomplete_textures(tile, ctx, tile_coords: str) -> None:
    UI.lvprint(
        1,
        f"Attempting to rebuild textures with white squares: "
        f"{IMG.incomplete_texture_file_names(tile_coords)}",
    )
    TILE.delete_incomplete_imgs(tile)
    TILE.build_tile(tile, ctx=ctx)


def _report_remaining_incomplete_textures() -> None:
    if IMG.incomplete_imgs:
        UI.lvprint(
            0,
            f"\nERROR: Parts of the following images could not be obtained "
            f"and have been filled with white: "
            f"{IMG.incomplete_texture_file_names_by_tile()}",
        )


def build_batch(
    plan: MODELS.BuildPlan,
    *,
    on_tile_complete: TileCompleteCallback | None = None,
) -> MODELS.BuildBatchResult:
    """Run a validated multi-tile build plan and return aggregate results."""
    ctx = BC.BuildContext()
    if ctx.is_working:
        return MODELS.BuildBatchResult(False, (), "build already in progress")
    results: list[MODELS.BuildTileResult] = []
    for tile_plan in plan.tiles:
        result = _build_tile_plan(tile_plan, ctx)
        results.append(result)
        if on_tile_complete is not None:
            on_tile_complete(result)
        if not result.ok:
            return MODELS.BuildBatchResult(False, tuple(results), result.message)
    _report_remaining_incomplete_textures()
    return MODELS.BuildBatchResult(MODELS.batch_ok(tuple(results)), tuple(results))


def _build_tile_plan(
    tile_plan: MODELS.BuildTilePlan, ctx: BC.BuildContext
) -> MODELS.BuildTileResult:
    tile = CFG.Tile(tile_plan.lat, tile_plan.lon, tile_plan.custom_build_dir)
    setattr(tile, "default_website", tile_plan.provider)
    setattr(tile, "default_zl", tile_plan.zoom_level)
    tile.custom_build_dir = tile_plan.custom_build_dir
    tile.dem = None
    if tile_plan.override_tile_config:
        tile.read_from_config(use_global=True)
    else:
        tile.read_from_config()
    if _steps_need_tile_directory(tile_plan.steps):
        tile.make_dirs()
    for step in MODELS.ALL_STEPS:
        if step not in tile_plan.steps:
            continue
        ok = _run_batch_step(step, tile, ctx)
        if ctx.red_flag:
            UI.exit_message_and_bottom_line("")
            return MODELS.BuildTileResult(
                tile_plan.lat,
                tile_plan.lon,
                False,
                step,
                "interrupted",
            )
        if not ok:
            return MODELS.BuildTileResult(
                tile_plan.lat,
                tile_plan.lon,
                False,
                step,
                f"{step} failed",
            )
    return MODELS.BuildTileResult(tile_plan.lat, tile_plan.lon, True, "all")


def _steps_need_tile_directory(steps: tuple[str, ...]) -> bool:
    return bool({"vector", "mesh", "tile"}.intersection(steps))


def _run_batch_step(step: str, tile, ctx: BC.BuildContext) -> int:
    if step == "vector":
        return VMAP.build_poly_file(tile, ctx=ctx)
    if step == "mesh":
        return MESH.build_mesh(tile, ctx=ctx)
    if step == "masks":
        return MASK.build_masks(tile, ctx=ctx)
    if step == "tile":
        return _run_batch_tile_step(tile, ctx)
    if step == "overlays":
        return OVL.build_overlay(tile.lat, tile.lon)
    raise ValueError(f"unknown build step: {step}")


def _run_batch_tile_step(tile, ctx: BC.BuildContext) -> int:
    result = TILE.build_tile(tile, ctx=ctx)
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    if tile_coords in IMG.incomplete_imgs:
        _retry_incomplete_textures(tile, ctx, tile_coords)
    if ctx.red_flag:
        return 0
    return result
