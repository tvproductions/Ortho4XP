"""Behavior tests for the DSFTool header bridge loop.

The fixtures simulate DSFTool and 7z side effects with real temporary files.
That keeps the assertions focused on command sequencing, staged replacement,
compressed default scenery handling, and fail-closed behavior without invoking
external tools.
"""

import tempfile
import unittest
from pathlib import Path

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_DSF_Header_Bridge import splice_native_dsf_headers
from tests._dsf_header_bridge_helpers import (
    FakeToolResult,
    TextRoundTripTool,
    bridge_request,
    global_scenery_dsf_path,
)


class DsfHeaderBridgeLoopTests(unittest.TestCase):
    def test_round_trips_default_and_generated_dsf_text_with_dsftool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            default_dsf = global_scenery_dsf_path(root)
            default_dsf.parent.mkdir(parents=True)
            default_dsf.write_bytes(b"default dsf")
            generated_dsf = Path(tmp) / "build" / "+12-123.dsf.tmp"
            generated_dsf.parent.mkdir(parents=True)
            generated_dsf.write_bytes(b"generated dsf")
            tool = TextRoundTripTool(default_dsf)

            result = splice_native_dsf_headers(
                bridge_request(
                    tmp=Path(tmp),
                    root=root,
                    generated_dsf=generated_dsf,
                    run_external_tool=tool.run,
                )
            )

            self.assertTrue(result.applied)
            self.assertIn("PROPERTY sim/season/winter_raster", tool.spliced_text)
            self.assertEqual(generated_dsf.read_bytes(), b"spliced dsf")
            self.assertEqual(
                [call[1][0] for call in tool.calls],
                ["--dsf2text", "--dsf2text", "--text2dsf"],
            )
            self.assertTrue(
                all(call[0] == "DSFTool" for call in tool.calls),
                tool.calls,
            )
            self.assertTrue(
                all(call[2] == "custom-DSFTool" for call in tool.calls),
                tool.calls,
            )

    def test_missing_default_dsf_leaves_generated_dsf_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated_dsf = Path(tmp) / "+12-123.dsf.tmp"
            generated_dsf.write_bytes(b"generated dsf")

            result = splice_native_dsf_headers(
                bridge_request(
                    tmp=Path(tmp),
                    root=Path(tmp) / "missing",
                    generated_dsf=generated_dsf,
                    run_external_tool=lambda *_args, **_kwargs: self.fail(
                        "DSFTool should not run without a default DSF"
                    ),
                )
            )

            self.assertFalse(result.applied)
            self.assertEqual(result.reason, "missing default DSF")
            self.assertEqual(generated_dsf.read_bytes(), b"generated dsf")

    def test_compressed_default_dsf_is_extracted_before_dsftool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            default_dsf = global_scenery_dsf_path(root)
            default_dsf.parent.mkdir(parents=True)
            default_dsf.write_bytes(b"7z compressed dsf")
            generated_dsf = Path(tmp) / "+12-123.dsf.tmp"
            generated_dsf.write_bytes(b"generated dsf")
            tmp_dir = Path(tmp) / "tmp"
            tool = TextRoundTripTool(tmp_dir / "+12-123.dsf", tmp_dir / "+12-123.dsf")

            result = splice_native_dsf_headers(
                bridge_request(
                    tmp=Path(tmp),
                    root=root,
                    generated_dsf=generated_dsf,
                    run_external_tool=tool.run,
                )
            )

            self.assertTrue(result.applied)
            self.assertEqual(generated_dsf.read_bytes(), b"spliced dsf")
            self.assertEqual(tool.calls[0][0], "7z")
            self.assertEqual(tool.calls[0][2], "custom-7z")
            self.assertEqual(
                [call[1][0] for call in tool.calls[1:]],
                ["--dsf2text", "--dsf2text", "--text2dsf"],
            )
            self.assertFalse((tmp_dir / "+12-123.dsf").exists())

    def test_failed_dsftool_leaves_generated_dsf_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            default_dsf = global_scenery_dsf_path(root)
            default_dsf.parent.mkdir(parents=True)
            default_dsf.write_bytes(b"default dsf")
            generated_dsf = Path(tmp) / "+12-123.dsf.tmp"
            generated_dsf.write_bytes(b"generated dsf")

            result = splice_native_dsf_headers(
                bridge_request(
                    tmp=Path(tmp),
                    root=root,
                    generated_dsf=generated_dsf,
                    run_external_tool=lambda *_args, **_kwargs: FakeToolResult(
                        ok=False, error_summary="boom"
                    ),
                )
            )

            self.assertFalse(result.applied)
            self.assertEqual(result.reason, "default DSF text conversion failed")
            self.assertEqual(generated_dsf.read_bytes(), b"generated dsf")

    def test_unsupported_default_headers_leave_generated_dsf_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "XP12"
            default_dsf = global_scenery_dsf_path(root)
            default_dsf.parent.mkdir(parents=True)
            default_dsf.write_bytes(b"default dsf")
            generated_dsf = Path(tmp) / "+12-123.dsf.tmp"
            generated_dsf.write_bytes(b"generated dsf")
            calls = []

            def run_external_tool(tool_name, args, *, executable):
                calls.append((tool_name, tuple(args), executable))
                Path(args[-1]).write_text(
                    "PROPERTY sim/west -123\nTERRAIN_DEF terrain/default.ter\n",
                    encoding="utf-8",
                )
                return FakeToolResult(ok=True)

            result = splice_native_dsf_headers(
                bridge_request(
                    tmp=Path(tmp),
                    root=root,
                    generated_dsf=generated_dsf,
                    run_external_tool=run_external_tool,
                )
            )

            self.assertFalse(result.applied)
            self.assertEqual(result.reason, "no supported native header lines")
            self.assertEqual(generated_dsf.read_bytes(), b"generated dsf")
            self.assertEqual([call[1][0] for call in calls], ["--dsf2text"])


class DsfBuildIntegrationTests(unittest.TestCase):
    def test_build_dsf_invokes_native_header_bridge_before_success_return(self):
        source = (_path.SRC_DIR / "O4_DSF_Utils.py").read_text(encoding="utf-8")

        self.assertIn(
            "from O4_DSF_Header_Bridge import splice_native_dsf_headers_for_tile",
            source,
        )
        self.assertIn("splice_native_dsf_headers_for_tile(tile,", source)


if __name__ == "__main__":
    unittest.main()
