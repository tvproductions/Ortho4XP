import O4_Build_Context as BC
import O4_Build_Models as MODELS
import O4_Build_Plan_State as PLAN_STATE
import O4_Build_Plan_Utils as PLAN


def run_build_batch(
    plan: MODELS.BuildPlan,
    ctx: BC.BuildContext,
    publishers: PLAN_STATE.BuildTilePlanPublishersProto,
) -> MODELS.BuildBatchResult:
    results: list[MODELS.BuildTileResult] = []
    for tile_plan in plan.tiles:
        result = PLAN.run_build_tile_plan(tile_plan, ctx, publishers)
        results.append(result)
        if publishers.on_tile_complete is not None:
            publishers.on_tile_complete(result)
        if not result.ok:
            return MODELS.BuildBatchResult(False, tuple(results), result.message)
    return MODELS.BuildBatchResult(MODELS.batch_ok(tuple(results)), tuple(results))
