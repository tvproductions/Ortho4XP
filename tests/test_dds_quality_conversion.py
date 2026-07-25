import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Utils as TCU
from O4_Texture_Models import TextureCleanupPlan


def _encode_result(ok=True):
    request = TCU.TEX.TextureEncodeRequest(
        source_path="source.png",
        output_path=os.path.join("build", "textures", "out.dds"),
        codec="bc1",
        display_name="out.dds",
        provider_code="BI",
    )
    return TCU.TEX.TextureEncodeResult(
        request=request,
        ok=ok,
        attempts=1,
        backend_name="native",
        tool_name="nvcompress",
        returncode=0 if ok else 7,
        error_summary="" if ok else "failed",
    )


class DdsQualityConversionIntegrationTests(unittest.TestCase):
    def test_successful_dds_conversion_runs_enabled_quality_check_before_cleanup(self):
        with tempfile.TemporaryDirectory() as build_dir:
            output_path = Path(build_dir) / "textures" / "out.dds"
            output_path.parent.mkdir()
            output_path.write_bytes(b"dds")
            tile = SimpleNamespace(
                build_dir=build_dir,
                dds_qa_enabled=True,
                dds_qa_psnr_threshold=35.5,
            )
            cleanup_events = []

            def cleanup(paths):
                cleanup_events.append(paths)

            with (
                mock.patch.object(
                    TCU.TEX, "encode_texture", return_value=_encode_result()
                ),
                mock.patch.object(
                    TCU.DQA,
                    "run_enabled_dds_quality_check",
                    side_effect=lambda *_args: cleanup_events.append("qa"),
                ) as qa,
                mock.patch.object(TCU, "cleanup_conversion_paths", side_effect=cleanup),
            ):
                result = TCU.convert_dds_texture(
                    tile,
                    (32, 48, 16, "BI"),
                    ("source.png", "out.dds", False),
                    TextureCleanupPlan(
                        always_paths=("source.png",),
                        success_paths=("mask.png",),
                    ),
                )

        self.assertTrue(result.ok)
        qa.assert_called_once()
        self.assertIs(qa.call_args.args[0], tile)
        self.assertTrue(qa.call_args.args[1].ok)
        self.assertEqual(cleanup_events, ["qa", ("mask.png",), ("source.png",)])

    def test_dds_quality_check_is_skipped_after_encode_failure_inside_qa_helper(self):
        tile = SimpleNamespace(
            build_dir="build",
            dds_qa_enabled=True,
            dds_qa_psnr_threshold=35.5,
        )

        with (
            mock.patch.object(
                TCU.TEX, "encode_texture", return_value=_encode_result(ok=False)
            ),
            mock.patch.object(TCU.DQA, "run_enabled_dds_quality_check") as qa,
            mock.patch.object(TCU, "cleanup_conversion_paths") as cleanup,
        ):
            result = TCU.convert_dds_texture(
                tile,
                (32, 48, 16, "BI"),
                ("source.png", "out.dds", False),
                TextureCleanupPlan(
                    always_paths=("source.png",),
                    success_paths=("mask.png",),
                ),
            )

        self.assertFalse(result.ok)
        qa.assert_called_once()
        self.assertFalse(qa.call_args.args[1].ok)
        cleanup.assert_called_once_with(("source.png",))


if __name__ == "__main__":
    unittest.main()
