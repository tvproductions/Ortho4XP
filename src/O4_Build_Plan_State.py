from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import O4_Build_Context as BC
import O4_Build_Models as MODELS


@dataclass(frozen=True)
class BuildTilePlanPublishers:
    run_batch_step: Callable[[str, object, BC.BuildContext], int]
    publish_tile_start: Callable[..., None]
    publish_tile_complete: Callable[..., None]
    publish_step: Callable[..., None]
    publish_progress: Callable[..., None]
    publish_tile_error: Callable[..., None]
    on_tile_complete: Callable[[MODELS.BuildTileResult], None] | None = None


class BuildTilePlanPublishersProto(Protocol):
    run_batch_step: Callable[[str, object, BC.BuildContext], int]
    publish_tile_start: Callable[..., None]
    publish_tile_complete: Callable[..., None]
    publish_step: Callable[..., None]
    publish_progress: Callable[..., None]
    publish_tile_error: Callable[..., None]
    on_tile_complete: Callable[[MODELS.BuildTileResult], None] | None


@dataclass(frozen=True)
class BuildTilePlanState:
    tile_plan: MODELS.BuildTilePlan
    tile: object
    publishers: BuildTilePlanPublishersProto


def build_tile_plan_failure(
    state: BuildTilePlanState, step: str, message: str
) -> MODELS.BuildTileResult:
    state.publishers.publish_tile_error(
        state.tile, mode="batch", step=step, message=message
    )
    return MODELS.BuildTileResult(
        state.tile_plan.lat,
        state.tile_plan.lon,
        False,
        step,
        message,
    )
