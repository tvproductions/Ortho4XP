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


def encode_result(request, ok):
    return TCU.TEX.TextureEncodeResult(
        request=request,
        ok=ok,
        attempts=1,
        backend_name="test",
        tool_name="test",
        returncode=0 if ok else 7,
        error_summary="" if ok else "failed",
    )


class TextureMaskLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.temp_png = root / "source.png"
        self.mask_png = root / "mask.png"
        self.temp_png.write_bytes(b"temporary")
        self.mask_png.write_bytes(b"mask")
        self.tile = SimpleNamespace(
            build_dir=str(root),
            dds_qa_enabled=False,
            dds_qa_psnr_threshold=0,
        )
        self.cleanup = TextureCleanupPlan(
            always_paths=(str(self.temp_png),),
            success_paths=(str(self.mask_png),),
        )

    def _convert(self, encoder):
        with mock.patch.object(TCU.TEX, "encode_texture", side_effect=encoder):
            return TCU.convert_dds_texture(
                self.tile,
                (32, 48, 16, "BI"),
                (str(self.temp_png), "out.dds", True),
                self.cleanup,
            )

    def test_success_removes_temporary_and_imprinted_mask(self):
        def successful_encoder(request):
            output_path = Path(request.output_path)
            output_path.parent.mkdir()
            output_path.write_bytes(b"dds")
            return encode_result(request, True)

        result = self._convert(successful_encoder)
        self.assertTrue(result.ok)
        self.assertFalse(self.temp_png.exists())
        self.assertFalse(self.mask_png.exists())

    def test_missing_output_removes_temporary_but_retains_mask(self):
        result = self._convert(lambda request: encode_result(request, True))
        self.assertTrue(result.ok)
        self.assertFalse(self.temp_png.exists())
        self.assertTrue(self.mask_png.exists())

    def test_returned_failure_removes_temporary_but_retains_mask(self):
        result = self._convert(lambda request: encode_result(request, False))
        self.assertFalse(result.ok)
        self.assertFalse(self.temp_png.exists())
        self.assertTrue(self.mask_png.exists())

    def test_encoder_exception_removes_temporary_but_retains_mask(self):
        with self.assertRaisesRegex(RuntimeError, "encoder exploded"):
            self._convert(
                lambda _request: (_ for _ in ()).throw(RuntimeError("encoder exploded"))
            )
        self.assertFalse(self.temp_png.exists())
        self.assertTrue(self.mask_png.exists())

    def test_quality_exception_removes_temporary_but_retains_mask(self):
        with (
            mock.patch.object(
                TCU.TEX,
                "encode_texture",
                side_effect=lambda request: encode_result(request, True),
            ),
            mock.patch.object(
                TCU.DQA,
                "run_enabled_dds_quality_check",
                side_effect=RuntimeError("quality exploded"),
            ),
            self.assertRaisesRegex(RuntimeError, "quality exploded"),
        ):
            TCU.convert_dds_texture(
                self.tile,
                (32, 48, 16, "BI"),
                (str(self.temp_png), "out.dds", True),
                self.cleanup,
            )
        self.assertFalse(self.temp_png.exists())
        self.assertTrue(self.mask_png.exists())


if __name__ == "__main__":
    unittest.main()
