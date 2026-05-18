import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


def water_mesh_fixture():
    import numpy

    node_coords = numpy.array([0.1, 0.1, 0.0, 0.0, 1.0] * 3)
    tri_idx = numpy.array([0, 1, 2])
    tri_types = numpy.array([2])
    mesh_result = (1.3, 3, node_coords, 1, tri_idx, tri_types)
    recut_result = (
        3,
        node_coords,
        [0, 0, 0],
        [False, False, False],
        1,
        tri_idx,
        tri_types,
    )
    return mesh_result, recut_result


@contextmanager
def patched_build_dsf_until_bathymetry(DSF, error):
    mesh_result, recut_result = water_mesh_fixture()
    with (
        mock.patch.object(DSF, "zone_list_to_ortho_dico", return_value={}),
        mock.patch.object(
            DSF.FNAMES,
            "mesh_file",
            return_value="build/Data+12-123.mesh",
        ),
        mock.patch.object(DSF.MESH, "read_mesh_file", return_value=mesh_result),
        mock.patch.object(DSF.BATHY, "recut_water_tris", return_value=recut_result),
        mock.patch.object(
            DSF.BATHY,
            "compute_depth_ratio_bounds_from_masks",
            return_value=[0, 0, 0],
        ),
        mock.patch.object(
            DSF,
            "extract_required_bathymetry_rasters",
            side_effect=error,
        ),
        mock.patch.object(DSF.UI, "exit_message_and_bottom_line") as exit_message,
        mock.patch.object(DSF.os.path, "exists") as exists,
    ):
        yield exit_message, exists


class BathymetryWaterGateTests(unittest.TestCase):
    def test_all_land_tiles_do_not_require_bathymetry(self):
        from O4_DSF_Utils import mesh_requires_bathymetry

        self.assertFalse(mesh_requires_bathymetry([0, 0, 0]))

    def test_water_tiles_require_bathymetry(self):
        from O4_DSF_Utils import mesh_requires_bathymetry

        self.assertTrue(mesh_requires_bathymetry([0, 1, 0]))
        self.assertTrue(mesh_requires_bathymetry([0, 2, 0]))

    def test_all_land_tiles_return_empty_rasters_without_calling_provider(self):
        import O4_DSF_Utils as DSF

        tile = SimpleNamespace(lat=12, lon=-123)
        with mock.patch.object(
            DSF, "extract_elevation_and_bathymetry_data"
        ) as provider:
            self.assertEqual(
                DSF.extract_required_bathymetry_rasters(tile, [0, 0, 0]),
                DSF.XP12_EMPTY_BATHYMETRY_RASTERS,
            )

        provider.assert_not_called()

    def test_build_dsf_reports_bathymetry_input_error_before_writing_dsf(self):
        import O4_DSF_Utils as DSF

        tile = SimpleNamespace(
            lat=12,
            lon=-123,
            build_dir="build",
            use_masks_for_inland=False,
        )
        error = DSF.BATHY_INPUT.BathymetryInputError("missing valid bathymetry")

        with patched_build_dsf_until_bathymetry(DSF, error) as (
            exit_message,
            exists,
        ):
            self.assertEqual(DSF.build_dsf(tile, mock.Mock()), 0)

        exit_message.assert_called_once_with(str(error))
        exists.assert_not_called()


if __name__ == "__main__":
    unittest.main()
