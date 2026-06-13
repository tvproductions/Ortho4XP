import os
import unittest
from types import SimpleNamespace

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401
import O4_File_Names as names


class FileNamesTests(unittest.TestCase):
    def test_latlon_format_helpers_handle_hemispheres_and_rounding(self):
        self.assertEqual(names.short_latlon(43, -79), "+43-079")
        self.assertEqual(names.round_latlon(43, -79), "+40-080")
        self.assertEqual(names.hem_latlon(43, -79), "N43W079")
        self.assertEqual(
            names.long_latlon(43, -79),
            os.path.join("+40-080", "+43-079"),
        )

    def test_latlon_format_helpers_handle_negative_fractional_values(self):
        self.assertEqual(names.short_latlon(-1.25, 7.8), "-01+008")
        self.assertEqual(names.round_latlon(-1.25, 7.8), "-10+000")
        self.assertEqual(names.hem_latlon(-1.25, 7.8), "S01E008")

    def test_tile_dir_uses_config_driven_naming(self):
        self.assertEqual(names.tile_dir(43, -79), "Ortho4XP_Mesh_+43-079")

    def test_tile_dir_is_configurable_via_prefix(self):
        self.assertTrue(names.tile_dir(43, -79).startswith("Ortho4XP"))

    def test_build_dir_uses_config_driven_tile_dir(self):
        self.assertEqual(
            names.build_dir(43, -79, ""),
            os.path.join(names.Tile_dir, "Ortho4XP_Mesh_+43-079"),
        )

    def test_build_dir_appends_tile_name_for_directory_like_custom_path(self):
        custom_dir = os.path.join("D:", "tiles") + os.sep
        self.assertEqual(
            names.build_dir(43, -79, custom_dir),
            os.path.join("D:", "tiles", "Ortho4XP_Mesh_+43-079"),
        )

    def test_overlay_dir_uses_config_driven_naming(self):
        self.assertEqual(names.overlay_dir_name(), "Ortho4XP_Overlays")

    def test_overlay_dir_name_returns_monolithic_name_by_default(self):
        self.assertEqual(names.overlay_dir_name(), "Ortho4XP_Overlays")

    def test_overlay_dir_name_with_per_tile_and_coords(self):
        self.assertEqual(names.overlay_dir_name(43, -79), "Ortho4XP_Overlays")

    def test_no_legacy_z_prefix_remains_in_tile_dir(self):
        result = names.tile_dir(43, -79)
        self.assertNotIn("zOrtho4XP", result)

    def test_overlay_dir_has_no_legacy_y_prefix(self):
        basename = os.path.basename(names.Overlay_dir)
        self.assertNotEqual(basename, "yOrtho4XP_Overlays")
        self.assertEqual(basename, "Ortho4XP_Overlays")

    def test_mesh_and_dsf_file_paths_use_tile_naming_conventions(self):
        build_dir = os.path.join("Tiles", "Ortho4XP_Mesh_+43-079")

        self.assertEqual(
            names.mesh_file(build_dir, 43, -79),
            os.path.join(build_dir, "Data+43-079.mesh"),
        )
        self.assertEqual(
            names.dsf_file(build_dir, 43, -79),
            os.path.join(
                build_dir,
                "Earth nav data",
                "+40-080",
                "+43-079.dsf",
            ),
        )

    def test_iteration_input_and_output_files_include_expected_suffixes(self):
        tile = SimpleNamespace(build_dir="build", lat=43, lon=-79, iterate=2)

        self.assertEqual(
            names.input_node_file(tile),
            os.path.join("build", "Data+43-079.2.node"),
        )
        self.assertEqual(
            names.output_node_file(tile),
            os.path.join("build", "Data+43-079.3.node"),
        )


if __name__ == "__main__":
    unittest.main()
