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


class BuildCoreAllInOneTests(unittest.TestCase):
    def test_build_tile_all_runs_steps_in_order_and_returns_success(self):
        tile = _tile()
        calls = []

        def record(name):
            def _inner(_tile):
                calls.append(name)
                return 1

            return _inner

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.VMAP, "build_poly_file", side_effect=record("vector")),
            mock.patch.object(CORE.MESH, "build_mesh", side_effect=record("mesh")),
            mock.patch.object(CORE.MASK, "build_masks", side_effect=record("masks")),
            mock.patch.object(CORE.TILE, "build_tile", side_effect=record("tile")),
            mock.patch.object(CORE.UI, "lvprint") as lvprint,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(calls, ["vector", "mesh", "masks", "tile"])
        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        lvprint.assert_not_called()
        exit_line.assert_not_called()

    def test_build_tile_all_stops_after_vector_when_red_flag_is_set(self):
        tile = _tile()
        calls = []

        def vector(_tile):
            calls.append("vector")
            CORE.UI.red_flag = True
            return 1

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.VMAP, "build_poly_file", side_effect=vector),
            mock.patch.object(CORE.MESH, "build_mesh") as build_mesh,
            mock.patch.object(CORE.MASK, "build_masks") as build_masks,
            mock.patch.object(CORE.TILE, "build_tile") as build_tile,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(calls, ["vector"])
        self.assertEqual(result, CORE.BuildResult(False, "vector", "interrupted"))
        build_mesh.assert_not_called()
        build_masks.assert_not_called()
        build_tile.assert_not_called()
        exit_line.assert_called_once_with("")

    def test_build_tile_all_stops_after_mesh_when_red_flag_is_set(self):
        tile = _tile()
        calls = []

        def vector(_tile):
            calls.append("vector")
            return 1

        def mesh(_tile):
            calls.append("mesh")
            CORE.UI.red_flag = True
            return 1

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.VMAP, "build_poly_file", side_effect=vector),
            mock.patch.object(CORE.MESH, "build_mesh", side_effect=mesh),
            mock.patch.object(CORE.MASK, "build_masks") as build_masks,
            mock.patch.object(CORE.TILE, "build_tile") as build_tile,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(calls, ["vector", "mesh"])
        self.assertEqual(result, CORE.BuildResult(False, "mesh", "interrupted"))
        build_masks.assert_not_called()
        build_tile.assert_not_called()
        exit_line.assert_called_once_with("")

    def test_build_tile_all_stops_after_masks_when_red_flag_is_set(self):
        tile = _tile()
        calls = []

        def vector(_tile):
            calls.append("vector")
            return 1

        def mesh(_tile):
            calls.append("mesh")
            return 1

        def masks(_tile):
            calls.append("masks")
            CORE.UI.red_flag = True
            return 1

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.VMAP, "build_poly_file", side_effect=vector),
            mock.patch.object(CORE.MESH, "build_mesh", side_effect=mesh),
            mock.patch.object(CORE.MASK, "build_masks", side_effect=masks),
            mock.patch.object(CORE.TILE, "build_tile") as build_tile,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(calls, ["vector", "mesh", "masks"])
        self.assertEqual(result, CORE.BuildResult(False, "masks", "interrupted"))
        build_tile.assert_not_called()
        exit_line.assert_called_once_with("")

    def test_build_tile_all_stops_after_tile_when_red_flag_is_set(self):
        tile = _tile()
        calls = []

        def record(name):
            def _inner(_tile):
                calls.append(name)
                return 1

            return _inner

        def build_tile(_tile):
            calls.append("tile")
            CORE.UI.red_flag = True
            return 1

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.VMAP, "build_poly_file", side_effect=record("vector")),
            mock.patch.object(CORE.MESH, "build_mesh", side_effect=record("mesh")),
            mock.patch.object(CORE.MASK, "build_masks", side_effect=record("masks")),
            mock.patch.object(CORE.TILE, "build_tile", side_effect=build_tile),
            mock.patch.object(CORE.UI, "lvprint") as lvprint,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(calls, ["vector", "mesh", "masks", "tile"])
        self.assertEqual(result, CORE.BuildResult(False, "tile", "interrupted"))
        lvprint.assert_not_called()
        exit_line.assert_called_once_with("")

    def test_build_tile_all_stops_after_retry_when_red_flag_is_set(self):
        tile = _tile()
        tile_coords = "+12-123"
        incomplete = {tile_coords: [{"file_name": "bad.jpg"}]}
        calls = []

        def build_tile(_tile):
            calls.append("tile")
            if len(calls) == 2:
                CORE.UI.red_flag = True
            return 1

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", incomplete),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=1),
            mock.patch.object(CORE.MASK, "build_masks", return_value=1),
            mock.patch.object(CORE.TILE, "build_tile", side_effect=build_tile),
            mock.patch.object(CORE.TILE, "delete_incomplete_imgs", return_value=None),
            mock.patch.object(
                CORE.IMG,
                "incomplete_texture_file_names",
                return_value=["bad.jpg"],
            ),
            mock.patch.object(CORE.UI, "lvprint"),
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(calls, ["tile", "tile"])
        self.assertEqual(result, CORE.BuildResult(False, "retry", "interrupted"))
        exit_line.assert_called_once_with("")

    def test_build_tile_all_retries_step_three_for_incomplete_imagery(self):
        tile = _tile()
        tile_coords = "+12-123"
        incomplete = {tile_coords: [{"file_name": "bad.jpg"}]}

        def clear_incomplete(_tile):
            incomplete.pop(tile_coords, None)

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", incomplete),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=1),
            mock.patch.object(CORE.MASK, "build_masks", return_value=1),
            mock.patch.object(CORE.TILE, "build_tile", return_value=1) as build_tile,
            mock.patch.object(
                CORE.TILE,
                "delete_incomplete_imgs",
                side_effect=clear_incomplete,
            ) as delete_incomplete,
            mock.patch.object(
                CORE.IMG,
                "incomplete_texture_file_names",
                return_value=["bad.jpg"],
            ),
            mock.patch.object(CORE.UI, "lvprint") as lvprint,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        self.assertEqual(build_tile.call_count, 2)
        delete_incomplete.assert_called_once_with(tile)
        lvprint.assert_any_call(
            1,
            "Attempting to rebuild textures with white squares: ['bad.jpg']",
        )

    def test_build_tile_all_reports_remaining_incomplete_imagery(self):
        tile = _tile()
        tile_coords = "+12-123"
        incomplete = {tile_coords: [{"file_name": "still_bad.jpg"}]}

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", incomplete),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=1),
            mock.patch.object(CORE.MASK, "build_masks", return_value=1),
            mock.patch.object(CORE.TILE, "build_tile", return_value=1),
            mock.patch.object(CORE.TILE, "delete_incomplete_imgs", return_value=None),
            mock.patch.object(
                CORE.IMG,
                "incomplete_texture_file_names",
                return_value=["still_bad.jpg"],
            ),
            mock.patch.object(
                CORE.IMG,
                "incomplete_texture_file_names_by_tile",
                return_value={tile_coords: ["still_bad.jpg"]},
            ),
            mock.patch.object(CORE.UI, "lvprint") as lvprint,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        lvprint.assert_any_call(
            0,
            "\nERROR: Parts of the following images could not be obtained "
            "and have been filled with white: "
            "{'+12-123': ['still_bad.jpg']}",
        )


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
