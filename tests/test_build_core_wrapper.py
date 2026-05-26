import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Core as CORE
import O4_Tile_Utils as TILE


def _tile():
    return SimpleNamespace(lat=12, lon=-123, build_dir="build")


class TileBuildAllWrapperTests(unittest.TestCase):
    def test_tile_utils_build_all_preserves_integer_success(self):
        with mock.patch.object(
            CORE,
            "build_tile_all",
            return_value=CORE.BuildResult(True, "all"),
        ) as build_tile_all:
            self.assertEqual(TILE.build_all(_tile()), 1)

        build_tile_all.assert_called_once()

    def test_tile_utils_build_all_preserves_integer_failure(self):
        with mock.patch.object(
            CORE,
            "build_tile_all",
            return_value=CORE.BuildResult(False, "mesh", "interrupted"),
        ) as build_tile_all:
            self.assertEqual(TILE.build_all(_tile()), 0)

        build_tile_all.assert_called_once()


if __name__ == "__main__":
    unittest.main()
