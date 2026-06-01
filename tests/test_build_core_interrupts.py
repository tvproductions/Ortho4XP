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


def _step(calls, name, interrupt_step):
    def _inner(_tile, ctx=None):
        calls.append(name)
        if name == interrupt_step:
            CORE.UI.red_flag = True
        return 1

    return _inner


class BuildCoreInterruptTests(unittest.TestCase):
    def test_build_tile_all_stops_after_interrupted_build_step(self):
        cases = (
            ("vector", ["vector"]),
            ("mesh", ["vector", "mesh"]),
            ("masks", ["vector", "mesh", "masks"]),
            ("tile", ["vector", "mesh", "masks", "tile"]),
        )

        for interrupted_step, expected_calls in cases:
            with self.subTest(interrupted_step=interrupted_step):
                result, calls, exit_line = self._run_interrupted_step(interrupted_step)

            self.assertEqual(calls, expected_calls)
            self.assertEqual(
                result,
                CORE.BuildResult(False, interrupted_step, "interrupted"),
            )
            exit_line.assert_called_once_with("")

    def test_build_tile_all_stops_after_interrupted_retry(self):
        tile = _tile()
        tile_coords = "+12-123"
        incomplete = {tile_coords: [{"file_name": "bad.jpg"}]}
        calls = []

        def build_tile(_tile, ctx=None):
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

    def _run_interrupted_step(self, interrupted_step):
        calls = []
        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(
                CORE.VMAP,
                "build_poly_file",
                side_effect=_step(calls, "vector", interrupted_step),
            ),
            mock.patch.object(
                CORE.MESH,
                "build_mesh",
                side_effect=_step(calls, "mesh", interrupted_step),
            ),
            mock.patch.object(
                CORE.MASK,
                "build_masks",
                side_effect=_step(calls, "masks", interrupted_step),
            ),
            mock.patch.object(
                CORE.TILE,
                "build_tile",
                side_effect=_step(calls, "tile", interrupted_step),
            ),
            mock.patch.object(CORE.UI, "lvprint") as lvprint,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(_tile())

        lvprint.assert_not_called()
        return result, calls, exit_line


if __name__ == "__main__":
    unittest.main()
