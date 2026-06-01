from __future__ import annotations

from dataclasses import dataclass


ALL_STEPS = ("vector", "mesh", "masks", "tile", "overlays")
DEFAULT_STEPS = ("vector", "mesh", "masks", "tile")


@dataclass(frozen=True)
class BuildTilePlan:
    lat: int
    lon: int
    provider: str
    zoom_level: int
    output_dir: str
    custom_build_dir: str
    steps: tuple[str, ...]
    override_tile_config: bool


@dataclass(frozen=True)
class BuildPlan:
    tiles: tuple[BuildTilePlan, ...]


@dataclass(frozen=True)
class BuildTileResult:
    lat: int
    lon: int
    ok: bool
    step: str
    message: str = ""


@dataclass(frozen=True)
class BuildBatchResult:
    ok: bool
    tiles: tuple[BuildTileResult, ...]
    message: str = ""


def batch_ok(results: tuple[BuildTileResult, ...]) -> bool:
    return all(result.ok for result in results)
