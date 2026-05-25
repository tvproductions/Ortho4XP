# Texture Encoder Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace legacy DDS conversion worker plumbing with a structured native texture encoder backend and bounded `concurrent.futures` scheduling while preserving current `nvcompress`/`DDSTool` behavior.

**Architecture:** Add `src/O4_Texture_Encoder.py` for request/result data, native DDS command planning, retry behavior, and future CUDA/Vulkan backend seams. Add `src/O4_Texture_Conversion_Scheduler.py` for streaming queue consumption through `ThreadPoolExecutor`, then integrate it into `src/O4_Tile_Utils.py` and delegate DDS execution from `src/O4_Imagery_Utils.py`.

**Tech Stack:** Python 3.13, standard-library `dataclasses`, `concurrent.futures`, `queue`, `unittest`, existing `O4_Subprocess_Utils`, Ruff, ty.

---

## File Structure

- Create `src/O4_Texture_Encoder.py`
  - Owns DDS encode request/result dataclasses.
  - Owns native `nvcompress`/`DDSTool` command planning.
  - Owns native retry behavior and shared subprocess execution.
  - Defines conversion result coercion helpers used by the scheduler.
- Create `src/O4_Texture_Conversion_Scheduler.py`
  - Owns `TextureConversionJob` and `TextureConversionBatchResult`.
  - Consumes existing conversion queue items.
  - Schedules conversions with `ThreadPoolExecutor`.
  - Aggregates failed conversion results.
- Modify `src/O4_Imagery_Utils.py`
  - Imports `O4_Texture_Encoder as TEX`.
  - Keeps image preparation behavior.
  - Delegates DDS execution to `TEX.encode_texture()`.
  - Returns a structured conversion result for DDS conversions.
- Modify `src/O4_Tile_Utils.py`
  - Imports `O4_Texture_Conversion_Scheduler as TCS`.
  - Replaces direct `parallel_launch(IMG.convert_texture, ...)` conversion workers with one scheduler thread.
  - Sends one `"quit"` sentinel to the scheduler after downloads finish.
  - Reports conversion failures at tile-build level.
- Modify `tests/_imagery_color_normalization_helpers.py`
  - Patches encoder delegation instead of expecting direct DDS command execution.
- Modify `tests/test_imagery_convert_color_normalization.py`
  - Asserts DDS encode requests use the correct prepared input path.
- Create `tests/test_texture_encoder.py`
  - Covers native command planning and backend result mapping.
- Create `tests/test_texture_conversion_scheduler.py`
  - Covers bounded futures scheduling, interruption, and aggregation.
- Create `tests/test_tile_texture_conversion.py`
  - Covers tile-level conversion summary formatting.
- Modify `README.md`
  - Documents observable conversion scheduling/failure-summary behavior only.
- Modify `TODO.md`
  - Mark TODO-018 done after implementation and verification.

---

### Task 1: Native Texture Encoder Backend

**Files:**
- Create: `tests/test_texture_encoder.py`
- Create: `src/O4_Texture_Encoder.py`

- [ ] **Step 1: Write failing backend tests**

Create `tests/test_texture_encoder.py`:

```python
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
```

- [ ] **Step 2: Run the backend tests to verify failure**

Run:

```powershell
uv run python -m unittest tests.test_texture_encoder -q
```

Expected: failure with `ModuleNotFoundError: No module named 'O4_Texture_Encoder'`.

- [ ] **Step 3: Implement `src/O4_Texture_Encoder.py`**

Create `src/O4_Texture_Encoder.py`:

```python
import sys
import time
from dataclasses import dataclass
from typing import Callable, Literal

from O4_External_Command_Result import ExternalCommandResult
import O4_Subprocess_Utils as SP
import O4_UI_Utils as UI


TextureCodec = Literal["bc1", "bc3"]
RunExternalCommand = Callable[..., ExternalCommandResult]
Sleep = Callable[[float], None]


@dataclass(frozen=True)
class TextureEncodeRequest:
    source_path: str
    output_path: str
    codec: TextureCodec
    display_name: str
    provider_code: str = ""
    til_x_left: int | None = None
    til_y_top: int | None = None
    zoomlevel: int | None = None
    max_attempts: int = 10


@dataclass(frozen=True)
class TextureEncodeResult:
    request: TextureEncodeRequest
    ok: bool
    attempts: int
    backend_name: str
    tool_name: str
    returncode: int | None
    error_summary: str


@dataclass(frozen=True)
class TextureConversionResult:
    ok: bool
    display_name: str
    provider_code: str = ""
    error_summary: str = ""
    encode_result: TextureEncodeResult | None = None

    @classmethod
    def success(cls, display_name: str, provider_code: str = ""):
        return cls(ok=True, display_name=display_name, provider_code=provider_code)

    @classmethod
    def failure(
        cls,
        display_name: str,
        provider_code: str = "",
        error_summary: str = "",
    ):
        return cls(
            ok=False,
            display_name=display_name,
            provider_code=provider_code,
            error_summary=error_summary,
        )

    @classmethod
    def from_encode_result(cls, result: TextureEncodeResult):
        return cls(
            ok=result.ok,
            display_name=result.request.display_name,
            provider_code=result.request.provider_code,
            error_summary=result.error_summary,
            encode_result=result,
        )


class TextureEncoderBackend:
    name = "abstract"

    def build_command(self, request: TextureEncodeRequest) -> list[str]:
        raise NotImplementedError

    def encode(self, request: TextureEncodeRequest) -> TextureEncodeResult:
        raise NotImplementedError


class NativeTextureEncoderBackend(TextureEncoderBackend):
    name = "native"

    def __init__(
        self,
        *,
        is_macos: bool | None = None,
        executable: str | None = None,
        run_external_command: RunExternalCommand | None = None,
        sleep: Sleep | None = None,
    ):
        self.is_macos = sys.platform.startswith("darwin") if is_macos is None else is_macos
        self.executable = executable
        self._run_external_command = run_external_command or SP.run_external_command
        self._sleep = sleep or time.sleep

    @property
    def tool_name(self) -> str:
        return "DDSTool" if self.is_macos else "nvcompress"

    def build_command(self, request: TextureEncodeRequest) -> list[str]:
        executable = self.executable or SP.resolve_tool(self.tool_name)
        if self.is_macos:
            flag = "--png2dxt5" if request.codec == "bc3" else "--png2dxt1"
            return [executable, flag, request.source_path, request.output_path]
        flag = "-bc3" if request.codec == "bc3" else "-bc1"
        return [executable, flag, "-fast", request.source_path, request.output_path]

    def encode(self, request: TextureEncodeRequest) -> TextureEncodeResult:
        max_attempts = max(1, int(request.max_attempts))
        last_result: ExternalCommandResult | None = None
        for attempt in range(1, max_attempts + 1):
            result = self._run_external_command(
                self.build_command(request),
                tool_name=self.tool_name,
            )
            if result.ok:
                return _encode_result_from_command(
                    request,
                    attempt,
                    self.name,
                    self.tool_name,
                    result,
                )
            last_result = result
            if attempt < max_attempts:
                UI.lvprint(1, "WARNING: Could not convert texture", request.output_path)
                self._sleep(1)
        UI.lvprint(
            1,
            "ERROR: Could not convert texture",
            request.output_path,
            f"({max_attempts} tries)",
        )
        assert last_result is not None
        return _encode_result_from_command(
            request,
            max_attempts,
            self.name,
            self.tool_name,
            last_result,
        )


def encode_texture(
    request: TextureEncodeRequest,
    backend: TextureEncoderBackend | None = None,
) -> TextureEncodeResult:
    active_backend = backend or NativeTextureEncoderBackend()
    return active_backend.encode(request)


def coerce_conversion_result(
    result,
    *,
    display_name: str,
    provider_code: str = "",
) -> TextureConversionResult:
    if isinstance(result, TextureConversionResult):
        return result
    if isinstance(result, TextureEncodeResult):
        return TextureConversionResult.from_encode_result(result)
    if result is False:
        return TextureConversionResult.failure(
            display_name,
            provider_code,
            "conversion returned False",
        )
    return TextureConversionResult.success(display_name, provider_code)


def _encode_result_from_command(
    request: TextureEncodeRequest,
    attempts: int,
    backend_name: str,
    tool_name: str,
    result: ExternalCommandResult,
) -> TextureEncodeResult:
    return TextureEncodeResult(
        request=request,
        ok=result.ok,
        attempts=attempts,
        backend_name=backend_name,
        tool_name=tool_name,
        returncode=result.returncode,
        error_summary=result.error_summary,
    )
```

- [ ] **Step 4: Run the backend tests to verify pass**

Run:

```powershell
uv run python -m unittest tests.test_texture_encoder -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the native encoder backend**

Run:

```powershell
git add src/O4_Texture_Encoder.py tests/test_texture_encoder.py
git commit -m "feat: add native texture encoder backend"
```

---

### Task 2: DDS Conversion Delegates To Encoder Backend

**Files:**
- Modify: `src/O4_Imagery_Utils.py`
- Modify: `tests/_imagery_color_normalization_helpers.py`
- Modify: `tests/test_imagery_convert_color_normalization.py`

- [ ] **Step 1: Update conversion tests to assert encoder request paths**

In `tests/_imagery_color_normalization_helpers.py`, update `_conversion_core_patch()` and `ConvertTexturePatchContext` so DDS conversion tests patch `IMG.TEX.encode_texture`:

```python
def _conversion_core_patch():
    return mock.patch.multiple(
        IMG,
        is_macos=False,
        run_external_command=mock.DEFAULT,
        color_transform=mock.DEFAULT,
        combine_textures=mock.DEFAULT,
    )
```

Add an encoder patch to `_convert_texture_patches()` immediately after the core patch:

```python
patches = [
    _conversion_core_patch(),
    mock.patch.object(IMG.TEX, "encode_texture"),
    mock.patch.object(TCN, "normalize_texture_image_if_enabled"),
    mock.patch.dict(
        IMG.providers_dict, settings.providers(provider_code), clear=True
    ),
    mock.patch.dict(
        IMG.local_combined_providers_dict,
        settings.combined_providers(provider_code),
        clear=True,
    ),
    mock.patch.object(
        FNAMES, "jpeg_file_dir_from_attributes", return_value=self.temp_dir.name
    ),
    mock.patch.object(FNAMES, "resource_path", return_value=tmp_dir),
    mock.patch.object(IMG.UI, "vprint"),
]
```

Update `ConvertTexturePatchContext.__enter__()`:

```python
def __enter__(self):
    multiple_mocks = self.patches[0].start()
    self.started.append(self.patches[0])
    self.run_external_command = multiple_mocks["run_external_command"]
    self.run_external_command.return_value = self.command_result
    self.color_transform = multiple_mocks["color_transform"]
    self.combine_textures = multiple_mocks["combine_textures"]
    self.encode_texture = self.patches[1].start()
    self.started.append(self.patches[1])
    self.encode_texture.return_value = IMG.TEX.TextureEncodeResult(
        request=IMG.TEX.TextureEncodeRequest(
            source_path="input.png",
            output_path="output.dds",
            codec="bc1",
            display_name="output.dds",
        ),
        ok=True,
        attempts=1,
        backend_name="native",
        tool_name="nvcompress",
        returncode=0,
        error_summary="",
    )
    self.normalize = self.patches[2].start()
    self.started.append(self.patches[2])
    for patcher in self.patches[3:-1]:
        patcher.start()
        self.started.append(patcher)
    self.vprint = self.patches[-1].start()
    self.started.append(self.patches[-1])
    return self
```

Replace the `command` property with an `encode_request` property:

```python
@property
def encode_request(self):
    return self.encode_texture.call_args.args[0]
```

In `tests/test_imagery_convert_color_normalization.py`, replace `conversion.command[-2]` assertions:

```python
self.assertEqual(conversion.encode_request.source_path, cached_path)
```

and:

```python
self.assertEqual(conversion.encode_request.source_path, expected_png)
```

- [ ] **Step 2: Run conversion tests to verify failure**

Run:

```powershell
uv run python -m unittest tests.test_imagery_convert_color_normalization -q
```

Expected: failure because `O4_Imagery_Utils` does not import `O4_Texture_Encoder` and still runs DDS commands directly.

- [ ] **Step 3: Delegate DDS execution in `O4_Imagery_Utils.py`**

Add the import near the other local imports:

```python
import O4_Texture_Encoder as TEX
```

Add this helper near `convert_texture()`:

```python
def _texture_encode_request(
    tile,
    til_x_left,
    til_y_top,
    zoomlevel,
    provider_code,
    *,
    source_path,
    output_file_name,
    dxt5,
):
    return TEX.TextureEncodeRequest(
        source_path=source_path,
        output_path=os.path.join(tile.build_dir, "textures", output_file_name),
        codec="bc3" if dxt5 else "bc1",
        display_name=output_file_name,
        provider_code=provider_code,
        til_x_left=til_x_left,
        til_y_top=til_y_top,
        zoomlevel=zoomlevel,
    )
```

Add this cleanup helper near `convert_texture()`:

```python
def _cleanup_conversion_temps(
    *,
    erase_tmp_png,
    png_file_name,
    erase_tmp_tif=False,
    tmp_tif_file_name=None,
):
    if erase_tmp_png:
        try:
            os.remove(os.path.join(FNAMES.resource_path("tmp"), png_file_name))
        except OSError as exc:
            UI.vprint(3, exc)
    if erase_tmp_tif and tmp_tif_file_name:
        try:
            os.remove(tmp_tif_file_name)
        except OSError as exc:
            UI.vprint(3, exc)
```

Inside `convert_texture()`, replace the current DDS `conv_cmd` construction block with:

```python
    if type == "dds":
        request = _texture_encode_request(
            tile,
            til_x_left,
            til_y_top,
            zoomlevel,
            provider_code,
            source_path=file_to_convert,
            output_file_name=out_file_name,
            dxt5=dxt5,
        )
        try:
            encode_result = TEX.encode_texture(request)
            return TEX.TextureConversionResult.from_encode_result(encode_result)
        finally:
            _cleanup_conversion_temps(
                erase_tmp_png=erase_tmp_png,
                png_file_name=png_file_name,
            )
```

Leave the existing GeoTIFF GDAL command construction under the `else:` path. Replace the old cleanup block at the end of `convert_texture()` with:

```python
    _cleanup_conversion_temps(
        erase_tmp_png=erase_tmp_png,
        png_file_name=png_file_name,
        erase_tmp_tif=erase_tmp_tif,
        tmp_tif_file_name=tmp_tif_file_name if erase_tmp_tif else None,
    )
    return TEX.TextureConversionResult.success(out_file_name, provider_code)
```

For the early geotag failure path, replace `return` with:

```python
                _cleanup_conversion_temps(
                    erase_tmp_png=erase_tmp_png,
                    png_file_name=png_file_name,
                )
                return TEX.TextureConversionResult.failure(
                    out_file_name,
                    provider_code,
                    "Could not geotag texture",
                )
```

- [ ] **Step 4: Run focused conversion tests**

Run:

```powershell
uv run python -m unittest tests.test_texture_encoder tests.test_imagery_convert_color_normalization -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit DDS encoder delegation**

Run:

```powershell
git add src/O4_Imagery_Utils.py tests/_imagery_color_normalization_helpers.py tests/test_imagery_convert_color_normalization.py
git commit -m "refactor: delegate dds conversion to texture encoder"
```

---

### Task 3: Futures Texture Conversion Scheduler

**Files:**
- Create: `tests/test_texture_conversion_scheduler.py`
- Create: `src/O4_Texture_Conversion_Scheduler.py`

- [ ] **Step 1: Write failing scheduler tests**

Create `tests/test_texture_conversion_scheduler.py`:

```python
import queue
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Scheduler as TCS
import O4_Texture_Encoder as TEX


class FakeUI:
    def __init__(self):
        self.red_flag = False
        self.progress = []

    def progress_bar(self, bar, value):
        self.progress.append((bar, value))


def _tile():
    return SimpleNamespace(lat=12, lon=-123)


def _queue(*provider_codes):
    items = queue.Queue()
    for index, provider_code in enumerate(provider_codes):
        items.put((_tile(), 32 + index * 16, 48, 16, provider_code))
    items.put("quit")
    return items


class TextureConversionSchedulerTests(unittest.TestCase):
    def test_scheduler_honors_worker_limit(self):
        ui = FakeUI()
        active = 0
        max_active = 0
        lock = threading.Lock()

        def convert_texture(tile, til_x_left, til_y_top, zoomlevel, provider_code):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return TEX.TextureConversionResult.success(
                f"{provider_code}.dds",
                provider_code,
            )

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("A", "B", "C", "D"),
                2,
                convert_texture=convert_texture,
                poll_interval=0.001,
            )

        self.assertEqual(result.completed, 4)
        self.assertEqual(result.failed, 0)
        self.assertFalse(result.interrupted)
        self.assertLessEqual(max_active, 2)
        self.assertIn((3, 100), ui.progress)

    def test_scheduler_aggregates_failed_jobs(self):
        ui = FakeUI()

        def convert_texture(tile, til_x_left, til_y_top, zoomlevel, provider_code):
            if provider_code == "BAD":
                return TEX.TextureConversionResult.failure(
                    "bad.dds",
                    provider_code,
                    "encoder failed",
                )
            return TEX.TextureConversionResult.success("ok.dds", provider_code)

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("OK", "BAD"),
                2,
                convert_texture=convert_texture,
                poll_interval=0.001,
            )

        self.assertEqual(result.completed, 2)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.failures[0].display_name, "bad.dds")
        self.assertEqual(result.failures[0].provider_code, "BAD")
        self.assertEqual(result.failures[0].error_summary, "encoder failed")

    def test_scheduler_converts_exceptions_to_failures(self):
        ui = FakeUI()

        def convert_texture(tile, til_x_left, til_y_top, zoomlevel, provider_code):
            raise RuntimeError("boom")

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("BI"),
                1,
                convert_texture=convert_texture,
                poll_interval=0.001,
            )

        self.assertEqual(result.completed, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.failures[0].provider_code, "BI")
        self.assertIn("boom", result.failures[0].error_summary)

    def test_scheduler_respects_red_flag_before_scheduling(self):
        ui = FakeUI()
        ui.red_flag = True
        convert_texture = mock.Mock()

        with mock.patch.object(TCS, "UI", ui):
            result = TCS.run_texture_conversion_queue(
                _queue("BI"),
                1,
                convert_texture=convert_texture,
                poll_interval=0.001,
            )

        self.assertEqual(result.completed, 0)
        self.assertEqual(result.failed, 0)
        self.assertTrue(result.interrupted)
        convert_texture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run scheduler tests to verify failure**

Run:

```powershell
uv run python -m unittest tests.test_texture_conversion_scheduler -q
```

Expected: failure with `ModuleNotFoundError: No module named 'O4_Texture_Conversion_Scheduler'`.

- [ ] **Step 3: Implement the scheduler module**

Create `src/O4_Texture_Conversion_Scheduler.py`:

```python
import queue
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Callable

import O4_File_Names as FNAMES
import O4_Texture_Encoder as TEX
import O4_UI_Utils as UI


ConvertTexture = Callable[[object, int, int, int, str], object]


@dataclass(frozen=True)
class TextureConversionJob:
    tile: object
    til_x_left: int
    til_y_top: int
    zoomlevel: int
    provider_code: str

    @classmethod
    def from_queue_item(cls, item):
        tile, til_x_left, til_y_top, zoomlevel, provider_code = item
        return cls(tile, til_x_left, til_y_top, zoomlevel, provider_code)

    @property
    def display_name(self) -> str:
        return FNAMES.dds_file_name_from_attributes(
            self.til_x_left,
            self.til_y_top,
            self.zoomlevel,
            self.provider_code,
        )


@dataclass(frozen=True)
class TextureConversionBatchResult:
    completed: int
    failed: int
    interrupted: bool
    failures: tuple[TEX.TextureConversionResult, ...]


def run_texture_conversion_queue(
    convert_queue,
    max_workers,
    *,
    convert_texture: ConvertTexture,
    progress_bar=3,
    poll_interval=0.05,
) -> TextureConversionBatchResult:
    worker_count = max(1, int(max_workers))
    completed = 0
    failures: list[TEX.TextureConversionResult] = []
    futures: set[Future[TEX.TextureConversionResult]] = set()
    sentinel_seen = False
    interrupted = False

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        while not sentinel_seen or futures:
            while (
                not sentinel_seen
                and len(futures) < worker_count
                and not UI.red_flag
            ):
                item = _next_queue_item(convert_queue, poll_interval, bool(futures))
                if item is None:
                    break
                if isinstance(item, str) and item == "quit":
                    sentinel_seen = True
                    break
                job = TextureConversionJob.from_queue_item(item)
                futures.add(executor.submit(_run_job, job, convert_texture))

            if UI.red_flag:
                interrupted = True
                sentinel_seen = True

            if not futures:
                if sentinel_seen:
                    break
                time.sleep(poll_interval)
                continue

            done, pending = wait(
                futures,
                timeout=poll_interval,
                return_when=FIRST_COMPLETED,
            )
            futures = set(pending)
            for future in done:
                result = future.result()
                completed += 1
                if not result.ok:
                    failures.append(result)
                _update_progress(
                    completed,
                    len(futures),
                    convert_queue.qsize(),
                    progress_bar,
                )

    UI.progress_bar(progress_bar, 100)
    return TextureConversionBatchResult(
        completed=completed,
        failed=len(failures),
        interrupted=interrupted or UI.red_flag,
        failures=tuple(failures),
    )


def _next_queue_item(convert_queue, poll_interval, has_active_futures):
    timeout = 0 if has_active_futures else poll_interval
    try:
        return convert_queue.get(timeout=timeout)
    except queue.Empty:
        return None


def _run_job(
    job: TextureConversionJob,
    convert_texture: ConvertTexture,
) -> TEX.TextureConversionResult:
    try:
        result = convert_texture(
            job.tile,
            job.til_x_left,
            job.til_y_top,
            job.zoomlevel,
            job.provider_code,
        )
    except Exception as exc:
        return TEX.TextureConversionResult.failure(
            job.display_name,
            job.provider_code,
            str(exc),
        )
    return TEX.coerce_conversion_result(
        result,
        display_name=job.display_name,
        provider_code=job.provider_code,
    )


def _update_progress(completed, active, queued, progress_bar):
    denominator = completed + active + queued
    value = int(100 * completed / denominator) if denominator else 100
    UI.progress_bar(progress_bar, value)
```

- [ ] **Step 4: Run scheduler and encoder tests**

Run:

```powershell
uv run python -m unittest tests.test_texture_encoder tests.test_texture_conversion_scheduler -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the futures scheduler**

Run:

```powershell
git add src/O4_Texture_Conversion_Scheduler.py tests/test_texture_conversion_scheduler.py
git commit -m "feat: add texture conversion futures scheduler"
```

---

### Task 4: Integrate Scheduler Into Step 3

**Files:**
- Modify: `src/O4_Tile_Utils.py`
- Create: `tests/test_tile_texture_conversion.py`

- [ ] **Step 1: Write tile summary tests**

Create `tests/test_tile_texture_conversion.py`:

```python
import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Scheduler as TCS
import O4_Texture_Encoder as TEX
import O4_Tile_Utils as TILE


def _tile():
    return SimpleNamespace(lat=12, lon=-123)


class TileTextureConversionSummaryTests(unittest.TestCase):
    def test_reports_failed_conversion_providers(self):
        result = TCS.TextureConversionBatchResult(
            completed=3,
            failed=2,
            interrupted=False,
            failures=(
                TEX.TextureConversionResult.failure("a.dds", "BI", "bad"),
                TEX.TextureConversionResult.failure("b.dds", "GO2", "bad"),
            ),
        )

        with mock.patch.object(TILE.UI, "vprint") as vprint:
            TILE._report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(
            1,
            "DDS conversion summary:",
            "2 failed texture(s)",
            "for tile +12-123.",
            "Providers: BI=1, GO2=1.",
        )

    def test_reports_successful_conversion_completion(self):
        result = TCS.TextureConversionBatchResult(
            completed=2,
            failed=0,
            interrupted=False,
            failures=(),
        )

        with mock.patch.object(TILE.UI, "vprint") as vprint:
            TILE._report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(1, " *DDS conversion of textures completed.")

    def test_reports_interrupted_conversion(self):
        result = TCS.TextureConversionBatchResult(
            completed=0,
            failed=0,
            interrupted=True,
            failures=(),
        )

        with mock.patch.object(TILE.UI, "vprint") as vprint:
            TILE._report_texture_conversion_result(_tile(), result)

        vprint.assert_any_call(1, "DDS conversion process interrupted.")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tile summary test to verify failure**

Run:

```powershell
uv run python -m unittest tests.test_tile_texture_conversion -q
```

Expected: failure because `_report_texture_conversion_result()` does not exist.

- [ ] **Step 3: Modify imports in `src/O4_Tile_Utils.py`**

Add the scheduler import:

```python
import O4_Texture_Conversion_Scheduler as TCS
```

Keep `parallel_launch` and `parallel_join` because `download_textures()` still uses the current queue worker utility.

- [ ] **Step 4: Add tile-level conversion reporting helpers**

Add these helpers above `build_tile()`:

```python
def _report_texture_conversion_result(tile, result):
    if result.interrupted:
        UI.vprint(1, "DDS conversion process interrupted.")
        return
    if result.failed:
        provider_counts = _texture_conversion_provider_counts(result.failures)
        UI.vprint(
            1,
            "DDS conversion summary:",
            f"{result.failed} failed texture(s)",
            f"for tile {FNAMES.short_latlon(tile.lat, tile.lon)}.",
            f"Providers: {provider_counts}.",
        )
        return
    if result.completed >= 1:
        UI.vprint(1, " *DDS conversion of textures completed.")


def _texture_conversion_provider_counts(failures):
    counts = defaultdict(int)
    for failure in failures:
        counts[failure.provider_code or "unknown"] += 1
    return ", ".join(
        f"{provider}={count}" for provider, count in sorted(counts.items())
    )
```

- [ ] **Step 5: Replace conversion worker launch in `build_tile()`**

In `build_tile()`, replace the conversion worker state:

```python
    convert_launched = False
    convert_result_holder = {}
```

Replace the `parallel_launch(IMG.convert_texture, ...)` block with:

```python
            convert_thread = threading.Thread(
                target=_run_texture_conversion_scheduler,
                args=(convert_queue, convert_result_holder),
            )
            convert_thread.start()
            convert_launched = True
```

Add this helper above `build_tile()`:

```python
def _run_texture_conversion_scheduler(convert_queue, result_holder):
    result_holder["result"] = TCS.run_texture_conversion_queue(
        convert_queue,
        max_convert_slots,
        convert_texture=IMG.convert_texture,
    )
```

Replace the post-download conversion shutdown block:

```python
        if convert_launched:
            for _ in range(max_convert_slots):
                convert_queue.put("quit")
            parallel_join(convert_workers)
            if UI.red_flag:
                UI.vprint(1, "DDS conversion process interrupted.")
            elif dico_conv_progress["done"] >= 1:
                UI.vprint(1, " *DDS conversion of textures completed.")
```

with:

```python
        if convert_launched:
            convert_queue.put("quit")
            convert_thread.join()
            _report_texture_conversion_result(
                tile,
                convert_result_holder["result"],
            )
```

- [ ] **Step 6: Run focused integration tests**

Run:

```powershell
uv run python -m unittest tests.test_texture_encoder tests.test_texture_conversion_scheduler tests.test_tile_texture_conversion tests.test_imagery_convert_color_normalization -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit Step 3 scheduler integration**

Run:

```powershell
git add src/O4_Tile_Utils.py tests/test_tile_texture_conversion.py
git commit -m "refactor: schedule texture conversion with futures"
```

---

### Task 5: Documentation, TODO Closeout, And Quality Verification

**Files:**
- Modify: `README.md`
- Modify: `TODO.md`

- [ ] **Step 1: Update README texture conversion notes**

In `README.md`, after the texture download retry paragraph and before `## Texture color normalization`, add:

```markdown
## Texture conversion scheduling

`max_convert_slots` controls the bounded CPU worker count used for DDS texture
conversion during Step 3. Ortho4XP schedules conversions through a native
texture encoder backend while preserving the platform-specific tools used by
this fork: `nvcompress` on Windows/Linux and `DDSTool` on macOS.

If one or more DDS conversions fail, Step 3 prints a concise conversion summary
with failed texture counts by imagery provider. Full external command details,
return codes, and stderr summaries continue to be written to
`Ortho4XP.log.json` by the shared subprocess runner.
```

- [ ] **Step 2: Mark TODO-018 done**

In `TODO.md`, under `### TODO-018: Deploy Multi-Threaded Texture Encoder Backend`, add:

```markdown
Status: Done
```

Do not change TODO ordering. Preserve the GitHub Issue reference.

- [ ] **Step 3: Run focused tests**

Run:

```powershell
uv run python -m unittest tests.test_texture_encoder tests.test_texture_conversion_scheduler tests.test_tile_texture_conversion tests.test_imagery_convert_color_normalization tests.test_subprocess_regression -q
```

Expected: all tests pass.

- [ ] **Step 4: Run Ruff on changed files**

Run:

```powershell
uv run ruff check src\O4_Texture_Encoder.py src\O4_Texture_Conversion_Scheduler.py src\O4_Imagery_Utils.py src\O4_Tile_Utils.py tests\test_texture_encoder.py tests\test_texture_conversion_scheduler.py tests\test_tile_texture_conversion.py tests\test_imagery_convert_color_normalization.py tests\_imagery_color_normalization_helpers.py
```

Expected: no Ruff violations.

- [ ] **Step 5: Run ty on changed Python files**

Run:

```powershell
uv run ty check src\O4_Texture_Encoder.py src\O4_Texture_Conversion_Scheduler.py src\O4_Imagery_Utils.py src\O4_Tile_Utils.py tests\test_texture_encoder.py tests\test_texture_conversion_scheduler.py tests\test_tile_texture_conversion.py
```

Expected: no ty errors for the checked files.

- [ ] **Step 6: Run the repository quality check**

Run:

```powershell
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected: full quality check passes.

- [ ] **Step 7: Comment on GitHub issue #13 with evidence**

Run:

```powershell
gh issue comment 13 --repo tvproductions/Ortho4XP --body "Implemented TODO-018 multi-threaded texture encoder backend. Evidence: focused texture encoder/scheduler/conversion tests passed; subprocess regression passed; Ruff passed on changed files; ty passed on changed Python files; full repository quality check passed. The implementation adds a native DDS encoder backend for current nvcompress/DDSTool behavior, schedules Step 3 conversions through bounded concurrent.futures workers controlled by max_convert_slots, aggregates conversion failures at tile-build level, and keeps CUDA/Vulkan as future backend extension points behind the request/result contract."
```

Expected: the issue receives the implementation/evidence comment.

- [ ] **Step 8: Close GitHub issue #13**

Run:

```powershell
gh issue close 13 --repo tvproductions/Ortho4XP --comment "Closed after TODO-018 acceptance criteria and repository quality verification passed."
```

Expected: issue #13 is closed.

- [ ] **Step 9: Commit docs and TODO closeout**

Run:

```powershell
git add README.md TODO.md
git commit -m "docs: close texture encoder backend todo"
```

- [ ] **Step 10: Final status check**

Run:

```powershell
git status --short
```

Expected: no uncommitted changes except unrelated user-owned changes that existed before this implementation.

---

## Self-Review Checklist

- Spec coverage:
  - Native request/result backend: Task 1.
  - DDS delegation from `convert_texture()`: Task 2.
  - `concurrent.futures` scheduling: Task 3 and Task 4.
  - Failure aggregation: Task 3 and Task 4.
  - Future CUDA/Vulkan seams: Task 1 backend interface and README restraint in Task 5.
  - Tests: Tasks 1 through 4.
  - Docs and TODO/GHI closeout: Task 5.
- Marker scan:
  - No unresolved marker text or incomplete steps.
  - `TODO-018` and `TODO.md` references are issue/work-queue names.
- Type consistency:
  - `TextureEncodeRequest`, `TextureEncodeResult`, and `TextureConversionResult` names are consistent across tasks.
  - Scheduler uses `TextureConversionBatchResult` and `TextureConversionJob` consistently.
  - `IMG.convert_texture()` returns a `TextureConversionResult` for DDS and GeoTIFF paths.
