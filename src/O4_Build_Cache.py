"""Tile build cache metadata helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

import O4_Build_Cache_IO as CACHE_IO
import O4_Cfg_Vars as CFGV
import O4_UI_Utils as UI

SCHEMA_VERSION = 1
METADATA_FILE_NAME = "tile_meta.json"

# Keep the cache facade small: build policy lives in O4_Build_Core, while
# serialization details stay in O4_Build_Cache_IO.


@dataclass(frozen=True)
class CacheHit:
    metadata_path: str
    parameter_hash: str


def tile_meta_path(tile) -> str:
    return os.path.join(tile.build_dir, METADATA_FILE_NAME)


def parameter_snapshot(tile) -> dict[str, object]:
    # The snapshot uses the same registry that tile configs write, so new tile
    # settings automatically affect the cache key.
    return {
        key: CACHE_IO.json_stable_value(getattr(tile, key))
        for key in CFGV.list_tile_vars
    }


def parameter_hash(tile) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "tile": _tile_payload(tile),
        "build_parameters": parameter_snapshot(tile),
    }
    return CACHE_IO.hash_payload(payload)


def read_cache_hit(tile) -> CacheHit | None:
    # Unit tests and adapters sometimes use partial tile doubles. Only real
    # configured tiles can participate in persistent cache decisions.
    if not _has_complete_parameter_set(tile):
        return None
    metadata_path = tile_meta_path(tile)
    metadata = CACHE_IO.read_json_dict(metadata_path)
    if not _metadata_matches(tile, metadata):
        return None
    return CacheHit(metadata_path, parameter_hash(tile))


def _metadata_matches(tile, metadata: Mapping[str, object] | None) -> bool:
    if metadata is None:
        return False
    return metadata == _metadata_payload(tile)


def write_cache_metadata(tile) -> None:
    if not _has_complete_parameter_set(tile):
        return
    metadata_path = tile_meta_path(tile)
    metadata = _metadata_payload(tile)
    try:
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        CACHE_IO.write_json_atomically(metadata_path, METADATA_FILE_NAME, metadata)
    except OSError as exc:
        # A scenery build should not become failed only because its optimization
        # metadata could not be written.
        UI.log_exception(exc, context={"cache_metadata_path": metadata_path})


def _metadata_payload(tile) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "tile": _tile_payload(tile),
        "build_parameters": parameter_snapshot(tile),
        "parameter_hash": parameter_hash(tile),
    }


def _tile_payload(tile) -> dict[str, int]:
    return {"lat": int(tile.lat), "lon": int(tile.lon)}


def _has_complete_parameter_set(tile) -> bool:
    return all(hasattr(tile, key) for key in CFGV.list_tile_vars)
