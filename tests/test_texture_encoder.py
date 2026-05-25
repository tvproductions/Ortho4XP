import unittest
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

from O4_External_Command_Result import ExternalCommandResult
import O4_Texture_Encoder as TEX


def _request(codec="bc1", max_attempts=10):
    return TEX.TextureEncodeRequest(
        source_path="input.png",
        output_path="output.dds",
        codec=codec,
        display_name="output.dds",
        provider_code="BI",
        til_x_left=32,
        til_y_top=48,
        zoomlevel=16,
        max_attempts=max_attempts,
    )


def _command_result(ok=True, returncode=0, error_summary=""):
    return ExternalCommandResult(
        tool_name="nvcompress",
        args=["encoder"],
        returncode=returncode,
        stdout="",
        stderr="",
        ok=ok,
        error_summary=error_summary,
    )


class NativeTextureEncoderTests(unittest.TestCase):
    def test_windows_linux_bc1_command_uses_nvcompress(self):
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=False,
            executable="nvcompress",
        )

        self.assertEqual(
            backend.build_command(_request("bc1")),
            ["nvcompress", "-bc1", "-fast", "input.png", "output.dds"],
        )

    def test_windows_linux_bc3_command_uses_nvcompress(self):
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=False,
            executable="nvcompress",
        )

        self.assertEqual(
            backend.build_command(_request("bc3")),
            ["nvcompress", "-bc3", "-fast", "input.png", "output.dds"],
        )

    def test_macos_bc1_command_uses_ddstool(self):
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=True,
            executable="DDSTool",
        )

        self.assertEqual(
            backend.build_command(_request("bc1")),
            ["DDSTool", "--png2dxt1", "input.png", "output.dds"],
        )

    def test_macos_bc3_command_uses_ddstool(self):
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=True,
            executable="DDSTool",
        )

        self.assertEqual(
            backend.build_command(_request("bc3")),
            ["DDSTool", "--png2dxt5", "input.png", "output.dds"],
        )

    def test_encode_success_maps_shared_subprocess_result(self):
        runner = mock.Mock(return_value=_command_result())
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=False,
            executable="nvcompress",
            run_external_command=runner,
            sleep=lambda _seconds: None,
        )

        result = backend.encode(_request("bc1"))

        self.assertTrue(result.ok)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.backend_name, "native")
        self.assertEqual(result.tool_name, "nvcompress")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.error_summary, "")
        runner.assert_called_once_with(
            ["nvcompress", "-bc1", "-fast", "input.png", "output.dds"],
            tool_name="nvcompress",
        )

    def test_encode_failure_preserves_error_summary(self):
        runner = mock.Mock(
            return_value=_command_result(
                ok=False,
                returncode=7,
                error_summary="return code 7: failed",
            )
        )
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=False,
            executable="nvcompress",
            run_external_command=runner,
            sleep=lambda _seconds: None,
        )

        with mock.patch.object(TEX.UI, "lvprint"):
            result = backend.encode(_request("bc1", max_attempts=1))

        self.assertFalse(result.ok)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.error_summary, "return code 7: failed")

    def test_encode_retries_until_success_or_attempt_limit(self):
        runner = mock.Mock(
            side_effect=[
                _command_result(False, 7, "return code 7: first"),
                _command_result(False, 7, "return code 7: second"),
                _command_result(True, 0, ""),
            ]
        )
        sleeps = []
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=False,
            executable="nvcompress",
            run_external_command=runner,
            sleep=sleeps.append,
        )

        with mock.patch.object(TEX.UI, "lvprint"):
            result = backend.encode(_request("bc1", max_attempts=3))

        self.assertTrue(result.ok)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(runner.call_count, 3)
        self.assertEqual(sleeps, [1, 1])


class TextureConversionResultTests(unittest.TestCase):
    def test_conversion_result_wraps_encode_result(self):
        encode_result = TEX.TextureEncodeResult(
            request=_request("bc3"),
            ok=False,
            attempts=2,
            backend_name="native",
            tool_name="nvcompress",
            returncode=7,
            error_summary="return code 7: failed",
        )

        result = TEX.TextureConversionResult.from_encode_result(encode_result)

        self.assertFalse(result.ok)
        self.assertEqual(result.display_name, "output.dds")
        self.assertEqual(result.provider_code, "BI")
        self.assertEqual(result.error_summary, "return code 7: failed")
        self.assertIs(result.encode_result, encode_result)


if __name__ == "__main__":
    unittest.main()
