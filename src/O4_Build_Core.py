"""Core tile-build orchestration boundaries.

This module owns Ortho4XP build policy: tile lifecycle events, current
all-in-one step order, batch-plan preparation, retry behavior for incomplete
imagery, and mapping controlled failures back to public build result objects.
The generic named-step execution mechanics live in `O4_Pipeline`; the small
build-facing adapter in `O4_Build_Pipeline` keeps those mechanics out of this
legacy build surface.
"""

from collections.abc import Callable
from dataclasses import dataclass

import O4_Build_Cache as CACHE
import O4_Build_Context as BC
import O4_Build_Models as MODELS
import O4_Build_Pipeline as BPIPE
import O4_Config_Utils as CFG
import O4_Event_Bus as EVENTS
import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Mask_Utils as MASK
import O4_Mesh_Utils as MESH
import O4_Overlay_Utils as OVL
import O4_Pipeline as PIPELINE
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
    _publish_event(EVENTS.EventName.TILE_START, tile, mode="all")
    if _publish_cache_hit_if_current(tile, mode="all"):
        ctx.is_working = False
        _publish_event(EVENTS.EventName.TILE_COMPLETE, tile, mode="all", step="all")
        return BuildResult(ok=True, step="all")
    interrupted = _run_all_build_phases(tile, ctx)
    if interrupted:
        _publish_all_build_error(tile, interrupted)
        return interrupted
    ctx.is_working = False
    _report_remaining_incomplete_textures()
    _write_cache_metadata_if_complete(tile)
    _publish_event(EVENTS.EventName.TILE_COMPLETE, tile, mode="all", step="all")
    return BuildResult(ok=True, step="all")


def _run_all_build_phases(tile, ctx) -> BuildResult | None:
    for build_phase in (_run_build_steps, _retry_incomplete_textures_if_needed):
        interrupted = build_phase(tile, ctx)
        if interrupted:
            return interrupted
    return None


def _publish_all_build_error(tile, result: BuildResult) -> None:
    _publish_event(
        EVENTS.EventName.TILE_ERROR,
        tile,
        mode="all",
        step=result.step,
        message=result.message,
    )


def _run_build_steps(tile, ctx) -> BuildResult | None:
    result = BPIPE.run_named_steps(
        tile,
        BPIPE.BuildPipelineSpec(
            mode="all",
            steps=_build_steps(),
            run_step=lambda build_step: _run_all_in_one_step(build_step, tile, ctx),
            on_step_complete=lambda _state, completed, total: _publish_progress(
                tile,
                mode="all",
                progress=(completed, total),
            ),
        ),
    )
    return _build_result_from_pipeline(result)


def _build_result_from_pipeline(result: PIPELINE.PipelineResult) -> BuildResult | None:
    if result.ok:
        return None
    if result.message == "interrupted":
        return _interrupted(result.failed_step or "unknown")
    return BuildResult(False, result.failed_step or "unknown", result.message)


def _run_all_in_one_step(build_step, tile, ctx) -> PIPELINE.StepOutcome:
    build_step(tile, ctx=ctx)
    if ctx.red_flag:
        return PIPELINE.StepOutcome(False, "interrupted")
    return PIPELINE.StepOutcome()


def _build_steps():
    return (
        ("vector", VMAP.build_poly_file),
        ("mesh", MESH.build_mesh),
        ("masks", MASK.build_masks),
        ("tile", TILE.build_tile),
    )


def _publish_event(event_name: EVENTS.EventName, tile, *, mode: str, **payload) -> None:
    EVENTS.publish(event_name, lat=tile.lat, lon=tile.lon, mode=mode, **payload)


def _publish_progress(
    tile,
    *,
    mode: str,
    progress: tuple[int, int],
) -> None:
    completed_steps, total_steps = progress
    _publish_event(
        EVENTS.EventName.TILE_PROGRESS,
        tile,
        mode=mode,
        completed_steps=completed_steps,
        total_steps=total_steps,
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


def _publish_cache_hit_if_current(tile, *, mode: str) -> bool:
    hit = CACHE.read_cache_hit(tile)
    if hit is None:
        return False
    _publish_event(
        EVENTS.EventName.CACHE_HIT,
        tile,
        mode=mode,
        metadata_path=hit.metadata_path,
        parameter_hash=hit.parameter_hash,
    )
    return True


def _write_cache_metadata_if_complete(tile) -> None:
    if _tile_has_incomplete_textures(tile):
        return
    CACHE.write_cache_metadata(tile)


def _tile_has_incomplete_textures(tile) -> bool:
    return FNAMES.short_latlon(tile.lat, tile.lon) in IMG.incomplete_imgs


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
    _publish_event(EVENTS.EventName.TILE_START, tile, mode="batch")
    _prepare_batch_tile(tile, tile_plan)
    selected_steps = _selected_batch_steps(tile_plan)
    if _is_full_tile_build(selected_steps) and _publish_cache_hit_if_current(
        tile, mode="batch"
    ):
        return _complete_batch_tile(tile_plan, tile)
    result = _run_batch_pipeline(tile, ctx, selected_steps)
    failed_result = _failed_batch_result(tile_plan, tile, result)
    if failed_result is not None:
        return failed_result
    if _is_full_tile_build(selected_steps):
        _write_cache_metadata_if_complete(tile)
    return _complete_batch_tile(tile_plan, tile)


def _selected_batch_steps(tile_plan: MODELS.BuildTilePlan) -> list[str]:
    return [step for step in MODELS.ALL_STEPS if step in tile_plan.steps]


def _run_batch_pipeline(
    tile,
    ctx: BC.BuildContext,
    selected_steps: list[str],
) -> PIPELINE.PipelineResult:
    return BPIPE.run_named_steps(
        tile,
        BPIPE.BuildPipelineSpec(
            mode="batch",
            steps=((step, step) for step in selected_steps),
            run_step=lambda step: _run_batch_plan_step(tile, ctx, step),
            on_step_complete=lambda _state, completed, total: _publish_progress(
                tile,
                mode="batch",
                progress=(completed, total),
            ),
        ),
    )


def _failed_batch_result(
    tile_plan: MODELS.BuildTilePlan,
    tile,
    result: PIPELINE.PipelineResult,
) -> MODELS.BuildTileResult | None:
    if not result.ok:
        message = result.message
        step = result.failed_step or "unknown"
        _publish_event(
            EVENTS.EventName.TILE_ERROR,
            tile,
            mode="batch",
            step=step,
            message=message,
        )
        return MODELS.BuildTileResult(
            tile_plan.lat, tile_plan.lon, False, step, message
        )
    return None


def _complete_batch_tile(
    tile_plan: MODELS.BuildTilePlan, tile
) -> MODELS.BuildTileResult:
    _publish_event(EVENTS.EventName.TILE_COMPLETE, tile, mode="batch", step="all")
    return MODELS.BuildTileResult(tile_plan.lat, tile_plan.lon, True, "all")


def _is_full_tile_build(steps: list[str]) -> bool:
    return tuple(steps) == MODELS.DEFAULT_STEPS


def _prepare_batch_tile(tile, tile_plan: MODELS.BuildTilePlan) -> None:
    tile.default_website = tile_plan.provider
    tile.default_zl = tile_plan.zoom_level
    tile.custom_build_dir = tile_plan.custom_build_dir
    tile.dem = None
    if tile_plan.override_tile_config:
        tile.read_from_config(use_global=True)
    else:
        tile.read_from_config()
    if _steps_need_tile_directory(tile_plan.steps):
        tile.make_dirs()


def _run_batch_plan_step(
    tile,
    ctx: BC.BuildContext,
    step: str,
) -> PIPELINE.StepOutcome:
    ok = _run_batch_step(step, tile, ctx)
    if ctx.red_flag:
        UI.exit_message_and_bottom_line("")
        return PIPELINE.StepOutcome(False, "interrupted")
    if ok:
        return PIPELINE.StepOutcome()
    return PIPELINE.StepOutcome(False, f"{step} failed")


def _steps_need_tile_directory(steps: tuple[str, ...]) -> bool:
    return bool({"vector", "mesh", "tile"}.intersection(steps))


_BATCH_STEP_RUNNERS = {
    "vector": lambda tile, ctx: VMAP.build_poly_file(tile, ctx=ctx),
    "mesh": lambda tile, ctx: MESH.build_mesh(tile, ctx=ctx),
    "masks": lambda tile, ctx: MASK.build_masks(tile, ctx=ctx),
    "tile": lambda tile, ctx: _run_batch_tile_step(tile, ctx),
    "overlays": lambda tile, ctx: OVL.build_overlay(tile.lat, tile.lon),
}


def _run_batch_step(step: str, tile, ctx: BC.BuildContext) -> int:
    try:
        return _BATCH_STEP_RUNNERS[step](tile, ctx)
    except KeyError as exc:
        raise ValueError(f"unknown build step: {step}") from exc


def _run_batch_tile_step(tile, ctx: BC.BuildContext) -> int:
    result = TILE.build_tile(tile, ctx=ctx)
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    if tile_coords in IMG.incomplete_imgs:
        _retry_incomplete_textures(tile, ctx, tile_coords)
    if ctx.red_flag:
        return 0
    return result
