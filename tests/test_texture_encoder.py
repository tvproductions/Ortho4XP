import unittest
from unittest import mock

# Texture encoder tests intentionally cover both the facade contract and the
# native backend's platform command lines.
# Retry tests use injected runtime dependencies so they never launch tools.
# Result-coercion tests document compatibility with legacy converter returns.
# The split keeps future backend modules free to reuse these shared model tests.

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Native_Texture_Encoder as NTE
import O4_Texture_Encoder as TEX
from O4_External_Command_Result import ExternalCommandResult


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


def _runtime(runner=None, sleep=None):
    return TEX.TextureEncoderRuntime(
        run_external_command=runner or mock.Mock(return_value=_command_result()),
        sleep=sleep or (lambda _seconds: None),
    )


class NativeTextureEncoderTests(unittest.TestCase):
    def test_windows_linux_bc1_command_uses_nvcompress(self):
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=False,
            executable="nvcompress",
        )

        self.assertEqual(
            backend.build_command(_request("bc1")),
            [
                "nvcompress",
                "-bc1",
                "-highest",
                "-alpha_dithering",
                "-mipfilter",
                "kaiser",
                "input.png",
                "output.dds",
            ],
        )

    def test_windows_linux_bc3_command_uses_nvcompress(self):
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=False,
            executable="nvcompress",
        )

        self.assertEqual(
            backend.build_command(_request("bc3")),
            [
                "nvcompress",
                "-bc3",
                "-highest",
                "-alpha_dithering",
                "-mipfilter",
                "kaiser",
                "-alpha",
                "input.png",
                "output.dds",
            ],
        )

    def test_default_windows_linux_executable_uses_repo_tool_resolver(self):
        with mock.patch.object(
            NTE.SP,
            "resolve_tool",
            return_value="Utils/win/nvcompress.exe",
        ) as resolve_tool:
            backend = TEX.NativeTextureEncoderBackend(is_macos=False)

            command = backend.build_command(_request("bc1"))

        resolve_tool.assert_called_once_with("nvcompress")
        self.assertEqual(command[0], "Utils/win/nvcompress.exe")

    def test_windows_linux_invalid_codec_raises_before_command_execution(self):
        runner = mock.Mock()
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=False,
            executable="nvcompress",
            runtime=_runtime(runner=runner),
        )

        with self.assertRaises(ValueError):
            backend.build_command(_request("bc5"))

        runner.assert_not_called()

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

    def test_macos_invalid_codec_raises_before_command_execution(self):
        runner = mock.Mock()
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=True,
            executable="DDSTool",
            runtime=_runtime(runner=runner),
        )

        with self.assertRaises(ValueError):
            backend.build_command(_request("bc5"))

        runner.assert_not_called()

    def test_encode_success_maps_shared_subprocess_result(self):
        runner = mock.Mock(return_value=_command_result())
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=False,
            executable="nvcompress",
            runtime=_runtime(runner=runner),
        )

        result = backend.encode(_request("bc1"))

        self.assertTrue(result.ok)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.backend_name, "native")
        self.assertEqual(result.tool_name, "nvcompress")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.error_summary, "")
        runner.assert_called_once_with(
            [
                "nvcompress",
                "-bc1",
                "-highest",
                "-alpha_dithering",
                "-mipfilter",
                "kaiser",
                "input.png",
                "output.dds",
            ],
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
            runtime=_runtime(runner=runner),
        )

        with mock.patch.object(NTE.UI, "lvprint"):
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
            runtime=_runtime(runner=runner, sleep=sleeps.append),
        )

        with mock.patch.object(NTE.UI, "lvprint"):
            result = backend.encode(_request("bc1", max_attempts=3))

        self.assertTrue(result.ok)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(runner.call_count, 3)
        self.assertEqual(sleeps, [1, 1])

    def test_encode_stops_at_attempt_limit_and_preserves_final_error(self):
        runner = mock.Mock(
            side_effect=[
                _command_result(False, 7, "return code 7: first"),
                _command_result(False, 8, "return code 8: final"),
            ]
        )
        sleeps = []
        backend = TEX.NativeTextureEncoderBackend(
            is_macos=False,
            executable="nvcompress",
            runtime=_runtime(runner=runner, sleep=sleeps.append),
        )

        with mock.patch.object(NTE.UI, "lvprint"):
            result = backend.encode(_request("bc1", max_attempts=2))

        self.assertFalse(result.ok)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(sleeps, [1])
        self.assertEqual(result.error_summary, "return code 8: final")


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

    def test_coerce_conversion_result_returns_existing_result_as_is(self):
        conversion_result = TEX.TextureConversionResult.success("legacy.dds", "GO2")

        result = TEX.coerce_conversion_result(
            conversion_result,
            display_name="output.dds",
            provider_code="BI",
        )

        self.assertIs(result, conversion_result)

    def test_coerce_conversion_result_converts_encode_result(self):
        encode_result = TEX.TextureEncodeResult(
            request=_request("bc3"),
            ok=False,
            attempts=2,
            backend_name="native",
            tool_name="nvcompress",
            returncode=7,
            error_summary="return code 7: failed",
        )

        result = TEX.coerce_conversion_result(
            encode_result,
            display_name="ignored.dds",
            provider_code="ignored",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.display_name, "output.dds")
        self.assertEqual(result.provider_code, "BI")
        self.assertEqual(result.error_summary, "return code 7: failed")
        self.assertIs(result.encode_result, encode_result)

    def test_coerce_conversion_result_maps_false_to_failure(self):
        result = TEX.coerce_conversion_result(
            False,
            display_name="output.dds",
            provider_code="BI",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.display_name, "output.dds")
        self.assertEqual(result.provider_code, "BI")
        self.assertEqual(result.error_summary, "conversion returned False")

    def test_coerce_conversion_result_maps_none_to_success(self):
        result = TEX.coerce_conversion_result(
            None,
            display_name="output.dds",
            provider_code="BI",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.display_name, "output.dds")
        self.assertEqual(result.provider_code, "BI")

    def test_coerce_conversion_result_maps_truthy_legacy_return_to_success(self):
        result = TEX.coerce_conversion_result(
            "legacy success",
            display_name="output.dds",
            provider_code="BI",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.display_name, "output.dds")
        self.assertEqual(result.provider_code, "BI")


if __name__ == "__main__":
    unittest.main()
