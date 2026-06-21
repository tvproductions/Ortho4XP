import unittest
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Core as CORE
import O4_Build_Models as MODELS


def _tile():
    return SimpleNamespace(lat=12, lon=-123, build_dir="build")


def _tile_plan(*, steps=("vector", "mesh", "masks", "tile")):
    return MODELS.BuildTilePlan(
        lat=12,
        lon=-123,
        provider="BI",
        zoom_level=16,
        output_dir="Tiles",
        custom_build_dir="Tiles/",
        steps=steps,
        override_tile_config=False,
    )


def _cache_hit():
    return SimpleNamespace(
        metadata_path="build/tile_meta.json",
        parameter_hash="abc123",
    )


def _batch_tile(lat, lon, custom):
    return SimpleNamespace(
        lat=lat,
        lon=lon,
        custom_build_dir=custom,
        build_dir=f"build-{lat}-{lon}",
        dem=None,
        default_website="",
        default_zl=0,
        make_dirs=mock.Mock(),
        read_from_config=mock.Mock(return_value=1),
    )


class BuildCoreCacheTests(unittest.TestCase):
    def test_build_tile_all_skips_steps_on_cache_hit(self):
        with (
            _patched_all_steps() as steps,
            mock.patch.object(CORE.CACHE, "read_cache_hit", return_value=_cache_hit()),
            mock.patch.object(CORE.CACHE, "write_cache_metadata") as write_cache,
        ):
            result = CORE.build_tile_all(_tile())

        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        for step in steps:
            step.assert_not_called()
        write_cache.assert_not_called()

    def test_build_tile_all_writes_cache_metadata_after_success(self):
        tile = _tile()
        with (
            _patched_successful_all_build(),
            mock.patch.object(CORE.CACHE, "read_cache_hit", return_value=None),
            mock.patch.object(CORE.CACHE, "write_cache_metadata") as write_cache,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        write_cache.assert_called_once_with(tile)

    def test_full_batch_skips_steps_on_cache_hit(self):
        with (
            _patched_batch_tile_class(),
            _patched_all_steps() as steps,
            mock.patch.object(CORE.CACHE, "read_cache_hit", return_value=_cache_hit()),
            mock.patch.object(CORE.CACHE, "write_cache_metadata") as write_cache,
        ):
            result = CORE.build_batch(MODELS.BuildPlan((_tile_plan(),)))

        self.assertTrue(result.ok)
        for step in steps:
            step.assert_not_called()
        write_cache.assert_not_called()

    def test_partial_batch_does_not_skip_on_cache_hit(self):
        with (
            _patched_batch_tile_class(),
            mock.patch.object(CORE.CACHE, "read_cache_hit", return_value=_cache_hit()),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1) as vector,
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
        ):
            result = CORE.build_batch(
                MODELS.BuildPlan((_tile_plan(steps=("vector",)),))
            )

        self.assertTrue(result.ok)
        vector.assert_called_once()

    def test_full_batch_writes_cache_metadata_after_success(self):
        tile = _batch_tile(12, -123, "Tiles/")
        with (
            mock.patch.object(CORE.CFG, "Tile", return_value=tile),
            _patched_successful_all_build(),
            mock.patch.object(CORE.CACHE, "read_cache_hit", return_value=None),
            mock.patch.object(CORE.CACHE, "write_cache_metadata") as write_cache,
        ):
            result = CORE.build_batch(MODELS.BuildPlan((_tile_plan(),)))

        self.assertTrue(result.ok)
        write_cache.assert_called_once_with(tile)


@contextmanager
def _patched_all_steps():
    with ExitStack() as stack:
        yield (
            stack.enter_context(mock.patch.object(CORE.VMAP, "build_poly_file")),
            stack.enter_context(mock.patch.object(CORE.MESH, "build_mesh")),
            stack.enter_context(mock.patch.object(CORE.MASK, "build_masks")),
            stack.enter_context(mock.patch.object(CORE.TILE, "build_tile")),
        )


@contextmanager
def _patched_successful_all_build():
    with (
        mock.patch.object(CORE.UI, "red_flag", False),
        mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
        mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
        mock.patch.object(CORE.MESH, "build_mesh", return_value=1),
        mock.patch.object(CORE.MASK, "build_masks", return_value=1),
        mock.patch.object(CORE.TILE, "build_tile", return_value=1),
        mock.patch.object(CORE.UI, "lvprint"),
        mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
    ):
        yield


def _patched_batch_tile_class():
    return mock.patch.object(CORE.CFG, "Tile", side_effect=_batch_tile)


if __name__ == "__main__":
    unittest.main()
