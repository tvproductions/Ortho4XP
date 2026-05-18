import tempfile
import unittest
from pathlib import Path

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Bathymetry_Input import extract_validated_global_scenery_rasters
from tests.test_bathymetry_provider import global_scenery_dsf_path, valid_dsf_file


class BathymetryFacadeTests(unittest.TestCase):
    def test_public_facade_accepts_legacy_overlay_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            global_scenery_dsf_path(root).parent.mkdir(parents=True)
            global_scenery_dsf_path(root).write_bytes(valid_dsf_file())

            result = extract_validated_global_scenery_rasters(
                12,
                -123,
                primary_overlay_src=str(root),
                alternate_overlay_src="",
                tmp_dir=str(Path(tmp) / "tmp"),
                unzip_executable="7z",
                run_external_tool=lambda *args, **kwargs: None,
            )

        self.assertEqual(result.payload.bathymetry.name, "sea_level")


if __name__ == "__main__":
    unittest.main()
