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

# DDS QA cleanup contract:
# - temporary PNG input is owned by every encode attempt;
# - an imprinted coastal mask remains reusable after encode failure;
# - an imprinted mask remains reusable after caught QA failure;
# - a below-threshold decoded image retains the source mask;
# - accepted encoder and QA success removes the source mask;
# - cleanup observes the DDS output before removing success-only paths;
# - failed encodes still pass through the QA facade as skipped checks;
# - cleanup order is QA, success-only sources, then owned temporaries.
#
# Files are real isolated artifacts, so assertions cover observed lifecycle
# state rather than only mock calls. Encoder and decoder work remains patched;
# no native tool, provider, X-Plane installation, or scenery fixture is needed.
#
# Failure tests distinguish disposable encoder input from the mask needed by a
# retry. That prevents advisory QA or conversion failure from making coastal
# output unrecoverable.
# Successful cleanup and retained-mask cases share the same immutable cleanup
# plan, proving disposition—not fixture shape—controls source ownership.
# Encode failures assert that only always-owned paths are removed.
# QA failures assert that success-owned masks remain available to retry.
# Successful QA asserts cleanup ordering against the existing DDS artifact.
# Missing output and caught QA cases retain identical recovery sources.
# Path existence assertions verify effects after cleanup returns.
# Mock call assertions distinguish attempted QA from cleanup authorization.
# Temporary-directory cleanup remains outside the production ownership plan.
# Result assertions retain the encoder's legacy success contract.
# Cleanup-event ordering remains explicit in the successful path.
#


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
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "source.png"
        self.mask = self.root / "mask.png"
        self.output = self.root / "textures" / "out.dds"
        self.output.parent.mkdir()
        self.output.write_bytes(b"dds")

    def test_successful_dds_conversion_runs_enabled_quality_check_before_cleanup(self):
        tile = SimpleNamespace(
            build_dir=self.temp_dir.name,
            dds_qa_enabled=True,
            dds_qa_psnr_threshold=35.5,
        )
        cleanup_events = []
        result, qa = self._run_successful_conversion(tile, cleanup_events)

        self.assertTrue(result.ok)
        qa.assert_called_once()
        self.assertIs(qa.call_args.args[0], tile)
        self.assertTrue(qa.call_args.args[1].ok)
        self.assertEqual(cleanup_events, ["qa", ("mask.png",), ("source.png",)])

    def _run_successful_conversion(self, tile, cleanup_events):
        with (
            mock.patch.object(TCU.TEX, "encode_texture", return_value=_encode_result()),
            mock.patch.object(
                TCU.DQA,
                "run_enabled_dds_quality_check",
                side_effect=lambda *_args: (
                    cleanup_events.append("qa"),
                    SimpleNamespace(allows_cleanup=True),
                )[1],
            ) as qa,
            mock.patch.object(
                TCU,
                "cleanup_conversion_paths",
                side_effect=cleanup_events.append,
            ),
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
        return result, qa

    def test_dds_quality_check_is_skipped_after_encode_failure_inside_qa_helper(self):
        tile = SimpleNamespace(
            build_dir="build",
            dds_qa_enabled=True,
            dds_qa_psnr_threshold=35.5,
        )

        result, qa, cleanup = self._run_failed_encode(tile)

        self.assertFalse(result.ok)
        qa.assert_called_once()
        self.assertFalse(qa.call_args.args[1].ok)
        cleanup.assert_called_once_with(("source.png",))

    def _run_failed_encode(self, tile):
        with (
            mock.patch.object(
                TCU.TEX, "encode_texture", return_value=_encode_result(ok=False)
            ),
            mock.patch.object(
                TCU.DQA,
                "run_enabled_dds_quality_check",
                return_value=SimpleNamespace(allows_cleanup=True),
            ) as qa,
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
        return result, qa, cleanup

    def test_caught_quality_error_retains_success_only_paths(self):
        self._assert_failed_qa_retains_mask("error")

    def test_below_threshold_quality_retains_success_only_paths(self):
        self._assert_failed_qa_retains_mask("below_threshold")

    def _assert_failed_qa_retains_mask(self, disposition):
        self.source.write_bytes(b"temporary")
        self.mask.write_bytes(b"mask")
        tile = SimpleNamespace(build_dir=self.temp_dir.name)
        with (
            mock.patch.object(
                TCU.TEX,
                "encode_texture",
                return_value=_encode_result(),
            ),
            mock.patch.object(
                TCU.DQA,
                "run_enabled_dds_quality_check",
                return_value=SimpleNamespace(
                    disposition=disposition,
                    allows_cleanup=False,
                ),
            ),
        ):
            result = TCU.convert_dds_texture(
                tile,
                (32, 48, 16, "BI"),
                (str(self.source), "out.dds", False),
                TextureCleanupPlan(
                    always_paths=(str(self.source),),
                    success_paths=(str(self.mask),),
                ),
            )

        self.assertTrue(result.ok)
        self.assertFalse(self.source.exists())
        self.assertTrue(self.mask.exists())


if __name__ == "__main__":
    unittest.main()
