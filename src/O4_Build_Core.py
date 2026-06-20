from collections.abc import Callable
from dataclasses import dataclass

import O4_Build_Context as BC
import O4_Build_Models as MODELS
import O4_Build_Plan_Batch as PLAN_BATCH
import O4_Build_Plan_State as PLAN_STATE
import O4_Build_Plan_Steps as PLAN_STEPS
import O4_Config_Utils as CFG
import O4_Event_Bus as EVENTS
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
    _publish_tile_start(tile, mode="all")
    interrupted = _run_build_steps(tile, ctx)
    if interrupted:
        _publish_tile_error(
            tile, mode="all", step=interrupted.step, message=interrupted.message
        )
        return interrupted

    interrupted = _retry_incomplete_textures_if_needed(tile, ctx)
    if interrupted:
        _publish_tile_error(
            tile, mode="all", step=interrupted.step, message=interrupted.message
        )
        return interrupted

    ctx.is_working = False
    _report_remaining_incomplete_textures()
    _publish_tile_complete(tile, mode="all")
    return BuildResult(ok=True, step="all")


def _run_build_steps(tile, ctx) -> BuildResult | None:
    steps = _build_steps()
    total_steps = len(steps)
    for completed_steps, (step, build_step) in enumerate(steps, start=1):
        _publish_step(tile, mode="all", step=step, status="start")
        build_step(tile, ctx=ctx)
        if ctx.red_flag:
            return _interrupted(step)
        _publish_step(tile, mode="all", step=step, status="complete")
        _publish_progress(
            tile,
            mode="all",
            completed_steps=completed_steps,
            total_steps=total_steps,
        )
    return None


def _build_steps():
    return (
        ("vector", VMAP.build_poly_file),
        ("mesh", MESH.build_mesh),
        ("masks", MASK.build_masks),
        ("tile", TILE.build_tile),
    )


def _tile_event_payload(tile, *, mode: str) -> dict[str, object]:
    return {"lat": tile.lat, "lon": tile.lon, "mode": mode}


def _publish_tile_start(tile, *, mode: str) -> None:
    EVENTS.publish(EVENTS.EventName.TILE_START, **_tile_event_payload(tile, mode=mode))


def _publish_tile_complete(tile, *, mode: str, step: str = "all") -> None:
    EVENTS.publish(
        EVENTS.EventName.TILE_COMPLETE,
        **_tile_event_payload(tile, mode=mode),
        step=step,
    )


def _publish_tile_error(tile, *, mode: str, step: str, message: str) -> None:
    EVENTS.publish(
        EVENTS.EventName.TILE_ERROR,
        **_tile_event_payload(tile, mode=mode),
        step=step,
        message=message,
    )


def _publish_step(tile, *, mode: str, step: str, status: str) -> None:
    EVENTS.publish(
        EVENTS.EventName.PIPELINE_STEP,
        **_tile_event_payload(tile, mode=mode),
        step=step,
        status=status,
    )


def _publish_progress(
    tile,
    *,
    mode: str,
    completed_steps: int,
    total_steps: int,
) -> None:
    EVENTS.publish(
        EVENTS.EventName.TILE_PROGRESS,
        **_tile_event_payload(tile, mode=mode),
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


def build_batch(
    plan: MODELS.BuildPlan,
    *,
    on_tile_complete: TileCompleteCallback | None = None,
) -> MODELS.BuildBatchResult:
    """Run a validated multi-tile build plan and return aggregate results."""
    ctx = BC.BuildContext()
    if ctx.is_working:
        return MODELS.BuildBatchResult(False, (), "build already in progress")
    publishers = _build_batch_publishers(on_tile_complete)
    result = PLAN_BATCH.run_build_batch(plan, ctx, publishers)
    if result.ok:
        _report_remaining_incomplete_textures()
    return result


def _build_batch_publishers(
    on_tile_complete: TileCompleteCallback | None,
) -> PLAN_STATE.BuildTilePlanPublishers:
    return PLAN_STATE.BuildTilePlanPublishers(
        PLAN_STEPS.run_batch_step,
        _publish_tile_start,
        _publish_tile_complete,
        _publish_step,
        _publish_progress,
        _publish_tile_error,
        on_tile_complete,
    )
