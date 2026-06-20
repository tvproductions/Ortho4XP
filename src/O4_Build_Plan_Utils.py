import O4_Build_Context as BC
import O4_Build_Models as MODELS
import O4_Build_Plan_State as PLAN_STATE
import O4_Build_Plan_Steps as PLAN_STEPS
import O4_Config_Utils as CFG
import O4_UI_Utils as UI


def selected_build_steps(steps: tuple[str, ...]) -> tuple[str, ...]:
    selected_steps: list[str] = []
    for step in MODELS.ALL_STEPS:
        if step in steps:
            selected_steps.append(step)
    return tuple(selected_steps)


def run_build_tile_plan_steps(
    tile_plan: MODELS.BuildTilePlan,
    tile,
    ctx,
    publishers: PLAN_STATE.BuildTilePlanPublishersProto,
) -> MODELS.BuildTileResult | None:
    selected_steps = selected_build_steps(tile_plan.steps)
    total_steps = len(selected_steps)
    state = PLAN_STATE.BuildTilePlanState(tile_plan, tile, publishers)

    for completed_steps, step in enumerate(selected_steps, start=1):
        if (
            result := _run_build_tile_plan_step(
                state,
                step,
                ctx,
                (completed_steps, total_steps),
            )
        ) is not None:
            return result
    return None


def _run_build_tile_plan_step(
    state: PLAN_STATE.BuildTilePlanState,
    step: str,
    ctx: BC.BuildContext,
    progress: tuple[int, int],
) -> MODELS.BuildTileResult | None:
    completed_steps, total_steps = progress
    publishers = state.publishers
    publishers.publish_step(state.tile, mode="batch", step=step, status="start")
    ok = publishers.run_batch_step(step, state.tile, ctx)
    if ctx.red_flag:
        UI.exit_message_and_bottom_line("")
        return PLAN_STATE.build_tile_plan_failure(state, step, "interrupted")
    if not ok:
        return PLAN_STATE.build_tile_plan_failure(state, step, f"{step} failed")
    publishers.publish_step(state.tile, mode="batch", step=step, status="complete")
    publishers.publish_progress(
        state.tile,
        mode="batch",
        completed_steps=completed_steps,
        total_steps=total_steps,
    )
    return None


def run_build_tile_plan(
    tile_plan: MODELS.BuildTilePlan,
    ctx: BC.BuildContext,
    publishers: PLAN_STATE.BuildTilePlanPublishersProto,
) -> MODELS.BuildTileResult:
    tile = CFG.Tile(tile_plan.lat, tile_plan.lon, tile_plan.custom_build_dir)
    publishers.publish_tile_start(tile, mode="batch")
    tile.default_website = tile_plan.provider
    tile.default_zl = tile_plan.zoom_level
    tile.custom_build_dir = tile_plan.custom_build_dir
    tile.dem = None
    if tile_plan.override_tile_config:
        tile.read_from_config(use_global=True)
    else:
        tile.read_from_config()
    if PLAN_STEPS.steps_need_tile_directory(tile_plan.steps):
        tile.make_dirs()
    if (
        result := run_build_tile_plan_steps(tile_plan, tile, ctx, publishers)
    ) is not None:
        return result
    publishers.publish_tile_complete(tile, mode="batch")
    return MODELS.BuildTileResult(tile_plan.lat, tile_plan.lon, True, "all")
