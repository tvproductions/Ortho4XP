import tempfile
import unittest
from pathlib import Path

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_Bathymetry_Input import (
    BathymetryInputError,
    GlobalSceneryRasterSource,
)
from O4_Bathymetry_Source import extract_validated_global_scenery_rasters
from tests.test_bathymetry_provider import (
    global_scenery_dsf_path,
    raster_source,
    valid_dsf_file,
)


class FakeToolResult:
    def __init__(
        self,
        *,
        ok: bool,
        error_summary: str | None = None,
        returncode: int | None = None,
    ):
        self.ok = ok
        self.error_summary = error_summary
        self.returncode = returncode


class BathymetryCompressedProviderTests(unittest.TestCase):
    def test_reads_compressed_global_scenery_dsf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            global_scenery_dsf_path(root).parent.mkdir(parents=True)
            global_scenery_dsf_path(root).write_bytes(b"7z compressed DSF fixture")
            tmp_dir = Path(tmp) / "tmp"

            def extract(_tool, _args, *, executable):
                self.assertEqual(executable, "custom-7z")
                (tmp_dir / "+12-123.dsf").write_bytes(valid_dsf_file())
                return FakeToolResult(ok=True)

            result = extract_validated_global_scenery_rasters(
                GlobalSceneryRasterSource(
                    lat=12,
                    lon=-123,
                    primary_overlay_src=str(root),
                    alternate_overlay_src="",
                    tmp_dir=str(tmp_dir),
                    unzip_executable="custom-7z",
                    run_external_tool=extract,
                )
            )

            self.assertEqual(result.payload.bathymetry.name, "sea_level")
            self.assertFalse((tmp_dir / "+12-123.dsf").exists())
            self.assertFalse((tmp_dir / "+12-123.dsf.7z").exists())

    def test_failed_7z_result_is_rejected_with_error_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            global_scenery_dsf_path(root).parent.mkdir(parents=True)
            global_scenery_dsf_path(root).write_bytes(b"7z compressed DSF fixture")

            with self.assertRaisesRegex(
                BathymetryInputError,
                r"could not unpack compressed DSF.*bad archive",
            ):
                extract_validated_global_scenery_rasters(
                    raster_source(
                        tmp,
                        primary=root,
                        run_external_tool=lambda *_args, **_kwargs: FakeToolResult(
                            ok=False,
                            error_summary="bad archive",
                        ),
                    )
                )

    def test_failed_7z_result_is_rejected_with_returncode_when_no_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            global_scenery_dsf_path(root).parent.mkdir(parents=True)
            global_scenery_dsf_path(root).write_bytes(b"7z compressed DSF fixture")

            with self.assertRaisesRegex(
                BathymetryInputError,
                r"could not unpack compressed DSF.*returncode 7",
            ):
                extract_validated_global_scenery_rasters(
                    raster_source(
                        tmp,
                        primary=root,
                        run_external_tool=lambda *_args, **_kwargs: FakeToolResult(
                            ok=False,
                            returncode=7,
                        ),
                    )
                )

    def test_7z_success_without_extracted_dsf_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            global_scenery_dsf_path(root).parent.mkdir(parents=True)
            global_scenery_dsf_path(root).write_bytes(b"7z compressed DSF fixture")

            with self.assertRaisesRegex(
                BathymetryInputError,
                r"7z extraction did not produce DSF file",
            ):
                extract_validated_global_scenery_rasters(
                    raster_source(
                        tmp,
                        primary=root,
                        run_external_tool=lambda *_args, **_kwargs: FakeToolResult(
                            ok=True
                        ),
                    )
                )


if __name__ == "__main__":
    unittest.main()
