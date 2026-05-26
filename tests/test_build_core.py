import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Core as CORE


def _tile():
    return SimpleNamespace(lat=12, lon=-123, build_dir="build")


def _record_step(calls, name):
    def _inner(_tile):
        calls.append(name)
        return 1

    return _inner


class BuildCoreAllInOneTests(unittest.TestCase):
    def test_build_tile_all_runs_steps_in_order_and_returns_success(self):
        tile = _tile()
        calls = []

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(
                CORE.VMAP, "build_poly_file", side_effect=_record_step(calls, "vector")
            ),
            mock.patch.object(
                CORE.MESH, "build_mesh", side_effect=_record_step(calls, "mesh")
            ),
            mock.patch.object(
                CORE.MASK, "build_masks", side_effect=_record_step(calls, "masks")
            ),
            mock.patch.object(
                CORE.TILE, "build_tile", side_effect=_record_step(calls, "tile")
            ),
            mock.patch.object(CORE.UI, "lvprint") as lvprint,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(calls, ["vector", "mesh", "masks", "tile"])
        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        lvprint.assert_not_called()
        exit_line.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
