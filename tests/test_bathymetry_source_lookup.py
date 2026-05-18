import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Bathymetry_Input import (
    BathymetryInputError,
    extract_validated_global_scenery_rasters,
)
from tests.test_bathymetry_provider import (
    global_scenery_dsf_path,
    raster_source,
    valid_dsf_file,
)


class BathymetrySourceLookupTests(unittest.TestCase):
    def test_missing_global_scenery_dsf_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                BathymetryInputError,
                r"custom_overlay_src.*custom_overlay_src_alternate.*XP12 Global Scenery",
            ):
                extract_validated_global_scenery_rasters(
                    raster_source(
                        tmp,
                        primary=Path(tmp) / "primary",
                        alternate=Path(tmp) / "alternate",
                        run_external_tool=lambda *args, **kwargs: None,
                    )
                )

    def test_reads_uncompressed_global_scenery_dsf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            global_scenery_dsf_path(root).parent.mkdir(parents=True)
            global_scenery_dsf_path(root).write_bytes(valid_dsf_file())

            result = extract_validated_global_scenery_rasters(
                raster_source(tmp, primary=root)
            )

        self.assertEqual(result.payload.bathymetry.name, "sea_level")

    def test_reads_alternate_source_when_primary_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            alternate = Path(tmp) / "XP12"
            global_scenery_dsf_path(alternate).parent.mkdir(parents=True)
            global_scenery_dsf_path(alternate).write_bytes(valid_dsf_file())

            result = extract_validated_global_scenery_rasters(
                raster_source(
                    tmp, primary=Path(tmp) / "missing-primary", alternate=alternate
                )
            )

        self.assertEqual(result.payload.bathymetry.name, "sea_level")

    def test_removes_temp_dsf_and_7z_sibling_after_uncompressed_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            global_scenery_dsf_path(root).parent.mkdir(parents=True)
            global_scenery_dsf_path(root).write_bytes(valid_dsf_file())
            tmp_dir = Path(tmp) / "tmp"
            tmp_dir.mkdir()
            temp_dsf = tmp_dir / "+12-123.dsf"
            temp_archive = Path(str(temp_dsf) + ".7z")
            temp_archive.write_bytes(b"stale archive")

            extract_validated_global_scenery_rasters(
                raster_source(tmp, primary=root, run_external_tool=mock.Mock())
            )

            self.assertFalse(temp_dsf.exists())
            self.assertFalse(temp_archive.exists())


if __name__ == "__main__":
    unittest.main()
