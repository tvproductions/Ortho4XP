from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import O4_File_Names as FNAMES


class BathymetryInputError(RuntimeError):
    """Raised when a water tile lacks valid XP12 bathymetry input."""


@dataclass(frozen=True)
class BathymetryErrorContext:
    tile_label: str
    source_path: str

    def error(self, message):
        return BathymetryInputError(
            f"Tile {self.tile_label} has invalid XP12 bathymetry input from "
            f"{self.source_path}: {message}. Point custom_overlay_src or "
            "custom_overlay_src_alternate at XP12 Global Scenery, or configure "
            "a future valid bathymetry provider."
        )


@dataclass(frozen=True)
class GlobalSceneryRasterSource:
    lat: int
    lon: int
    primary_overlay_src: str
    alternate_overlay_src: str
    tmp_dir: str
    unzip_executable: str
    run_external_tool: Callable[..., Any]

    @property
    def tile_label(self):
        return FNAMES.short_latlon(self.lat, self.lon)


@dataclass(frozen=True)
class RasterInfo:
    name: str
    width: int
    height: int
    bytes_per_pixel: int
    flags: int
    data: bytes


@dataclass(frozen=True)
class RasterPayload:
    layer_names: tuple[str, ...]
    rasters: tuple[RasterInfo, ...]
    elevation: RasterInfo
    bathymetry: RasterInfo


@dataclass(frozen=True)
class ValidatedRasterBytes:
    demn: bytes
    dems: bytes
    payload: RasterPayload
