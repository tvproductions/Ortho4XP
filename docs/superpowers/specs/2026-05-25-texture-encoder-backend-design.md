# Texture Encoder Backend Design

## Problem

TODO-018 calls for removing serial texturing bottlenecks before adding
GPU-specific backends. The current Step 3 texture flow can run multiple
conversion workers, but the conversion behavior is still coupled to legacy
queue workers and `IMG.convert_texture()`. That function prepares images,
constructs external DDS commands, retries external calls, cleans temporary
files, and returns no structured result that the tile builder can aggregate.

The result is a pipeline that is hard to reason about and hard to extend:

- DDS encoder command construction is embedded inside image preparation.
- Conversion failures can be logged by workers without a structured tile-level
  summary.
- The current worker model is custom `threading.Thread` plus sentinels instead
  of the `concurrent.futures` boundary requested by TODO-018.
- Future CUDA or Vulkan encoders would have to thread through legacy conversion
  code unless a backend seam is created first.

The first deliverable should make the native CPU encoder path explicit and
testable while preserving current user-visible behavior.

## Current Context

Step 3 texture work is split across `src/O4_Tile_Utils.py` and
`src/O4_Imagery_Utils.py`.

`src/O4_Tile_Utils.py` currently:

- starts `DSF.build_dsf()` to enqueue texture attributes;
- starts `download_textures()` to build or reuse JPEG orthophotos;
- pushes successful downloads into a conversion queue;
- launches `IMG.convert_texture()` workers through
  `O4_Parallel_Utils.parallel_launch()`;
- waits for workers by pushing `"quit"` sentinels and joining threads.

`src/O4_Imagery_Utils.py::convert_texture()` currently:

- determines DDS or GeoTIFF output names;
- applies masks directly to DDS inputs when configured;
- combines local provider layers when needed;
- applies optional neighbor color normalization;
- applies provider color filters;
- writes temporary PNG/TIFF inputs;
- builds `nvcompress`, `DDSTool`, `gdal_translate`, or `gdalwarp` commands;
- retries failed external conversions up to ten times;
- removes temporary files.

External tool execution has already been centralized in
`src/O4_Subprocess_Utils.py`. New encoder work should continue routing external
commands through that helper so structured command logging remains consistent.

The current user-facing app setting is `max_convert_slots`, defined in
`src/O4_Cfg_Vars.py` and assigned to `src/O4_Tile_Utils.py`. That setting
should remain the CPU conversion concurrency control.

## Goals

- Introduce a dedicated texture encoder backend boundary.
- Preserve the current native DDS encoder behavior for Windows, Linux, and
  macOS.
- Replace the Step 3 DDS conversion worker launch with bounded
  `concurrent.futures` scheduling.
- Return structured per-texture and batch conversion results.
- Aggregate conversion failures at the tile-build level.
- Route all DDS encoder calls through the shared subprocess helper.
- Define extension points for future CUDA and Vulkan backends without exposing
  unfinished GPU options to users.
- Add deterministic `unittest` coverage for command planning, task scheduling,
  and failure aggregation.

## Non-Goals

- Do not implement CUDA or Vulkan encoding in TODO-018.
- Do not add a user-facing `texture_encoder_backend` setting until at least one
  non-native backend exists and has a validated availability story.
- Do not change source imagery cache formats.
- Do not rewrite the entire download, preprocessing, mask, GeoTIFF, or DSF
  generation pipeline.
- Do not add OpenCV, rasterio, GDAL Python bindings, or new runtime
  dependencies for this task.
- Do not require X-Plane installs, real imagery providers, GDAL tools, or real
  DDS encoders in tests.

## Recommended Approach

Use a native backend boundary plus a futures scheduler.

This is the best fit for the project because it follows current modernization
patterns: keep legacy runtime behavior stable, extract a small testable
contract, and then migrate the call site through that contract. It also matches
issue #13 exactly: `concurrent.futures`, bounded CPU parallelism, subprocess
helper usage, backend extension points, and tests for planning and failure
aggregation.

Broader alternatives are intentionally deferred:

- A full texture work DAG would be stronger long term, but it would mix TODO-018
  with download orchestration, normalization, masking, GeoTIFF export, and DSF
  scheduling.
- User-facing backend selection would be premature until CUDA or Vulkan support
  can report device availability, encoder availability, quality settings, and
  actionable fallback behavior.

## Design

Add `src/O4_Texture_Encoder.py` as the texture encoding boundary.

The module should define data objects that keep encoder inputs and outputs
explicit:

```python
from dataclasses import dataclass
from typing import Literal

TextureCodec = Literal["bc1", "bc3"]


@dataclass(frozen=True)
class TextureEncodeRequest:
    source_path: str
    output_path: str
    codec: TextureCodec
    display_name: str
    max_attempts: int = 10


@dataclass(frozen=True)
class TextureEncodeResult:
    request: TextureEncodeRequest
    ok: bool
    attempts: int
    tool_name: str
    returncode: int | None
    error_summary: str
```

The module should also define an encoder interface shape:

```python
class TextureEncoderBackend:
    name = "abstract"

    def build_command(self, request: TextureEncodeRequest) -> list[str]:
        raise NotImplementedError

    def encode(self, request: TextureEncodeRequest) -> TextureEncodeResult:
        raise NotImplementedError
```

The first concrete backend is `NativeTextureEncoderBackend`. It owns the current
platform-specific native DDS encoder behavior:

- macOS: `DDSTool --png2dxt1` for BC1 and `DDSTool --png2dxt5` for BC3.
- Windows/Linux: `nvcompress -bc1 -fast` for BC1 and `nvcompress -bc3 -fast`
  for BC3.

The backend should call `O4_Subprocess_Utils.run_external_tool()` or
`run_external_command()` for every external encoder invocation. It should not
call `subprocess` directly.

`TextureEncodeRequest.codec` maps current `convert_texture()` behavior:

- BC1 when `type == "dds"` and no alpha mask is imprinted.
- BC3 when `type == "dds"` and an alpha mask is imprinted.

GeoTIFF conversion stays in `O4_Imagery_Utils.py` for TODO-018. It uses GDAL
commands, not a DDS texture encoder, and should not be forced into the DDS
backend boundary in this task.

## Conversion Integration

Refactor `src/O4_Imagery_Utils.py::convert_texture()` conservatively.

The function should still prepare the image input exactly as it does today:

- resolve cached JPEG paths;
- combine local provider layers;
- apply color normalization;
- apply provider color filters;
- apply mask alpha when `imprint_masks_to_dds` requires it;
- write temporary PNG inputs;
- remove temporary PNG and TIFF files.

For DDS output, the final external encoder loop should move behind the native
backend:

1. Determine `out_file_name`, `file_to_convert`, and whether BC1 or BC3 is
   required.
2. Build a `TextureEncodeRequest`.
3. Call the active encoder backend.
4. Return a structured conversion result to the caller.
5. Clean temporary files in a `finally`-style path so failed encoder calls do
   not strand routine temporary PNGs.

The first implementation may keep the public function name `convert_texture()`
to reduce blast radius. Its return value should become meaningful:

- successful DDS conversion returns a successful conversion result;
- failed DDS conversion returns a failed conversion result;
- GeoTIFF conversion returns a compatible result object or a small conversion
  result wrapper with the same `ok` and `error_summary` fields.

Existing call sites that ignore the return value should continue to work, but
the Step 3 scheduler should use it.

## Futures Scheduler

Replace the DDS conversion worker launch in `src/O4_Tile_Utils.py` with a small
`concurrent.futures.ThreadPoolExecutor` scheduler.

The scheduler should:

- accept conversion jobs from the existing producer queue;
- submit at most `max_convert_slots` running conversion tasks;
- use `IMG.convert_texture()` or a narrow wrapper as the callable;
- update the existing progress bar as futures complete;
- stop scheduling new work when `UI.red_flag` is set;
- return a `TextureConversionBatchResult` containing completed, failed, and
  interrupted counts plus failed texture summaries.

The producer/consumer relationship still matters. `DSF.build_dsf()` produces
texture attributes, `download_textures()` downloads them, and conversion can
begin before all downloads finish. The scheduler therefore should keep the
streaming behavior instead of waiting for a full list of textures.

A practical design is:

```python
@dataclass(frozen=True)
class TextureConversionJob:
    tile: object
    til_x_left: int
    til_y_top: int
    zoomlevel: int
    provider_code: str


@dataclass(frozen=True)
class TextureConversionBatchResult:
    completed: int
    failed: int
    interrupted: bool
    failures: tuple[TextureEncodeResult, ...]
```

The queue sentinel can remain internal at the boundary between
`download_textures()` and the scheduler, but sentinel handling should be
localized. `O4_Tile_Utils.build_tile()` should no longer directly manage a
list of custom conversion threads.

## Failure Handling

Failures should be observable at the tile-build level.

Each failed DDS conversion result should include:

- texture display name or output file name;
- provider code where available;
- codec;
- encoder backend name;
- attempts;
- return code when available;
- short error summary from the shared subprocess result.

`O4_Tile_Utils.build_tile()` should emit one concise conversion summary after
conversion workers finish. For example:

```text
DDS conversion summary: 3 failed texture(s) for tile +12-123. Providers: BI=2, GO2=1.
```

Full command arguments, return codes, and stderr summaries remain in
`Ortho4XP.log.json` through `O4_Subprocess_Utils`.

The current retry behavior is ten attempts with a one-second sleep between
failed external conversions. TODO-018 should preserve that default for native
encoding unless tests expose a reason to change it. The retry loop should live
inside the backend or a small helper owned by the encoder boundary.

If conversion failures occur, the tile builder should not silently claim that
DDS conversion completed normally. Whether Step 3 should hard-fail the tile on
any DDS conversion failure should be decided during implementation after
checking current behavior. At minimum, the result must be tracked and reported.

## Future GPU Path

The native backend boundary is deliberately shaped for a future XP12 scenery
studio rather than a one-off speed patch.

Future CUDA and Vulkan work should plug in behind the same request/result
contract:

```python
class CudaTextureEncoderBackend(TextureEncoderBackend):
    name = "cuda"


class VulkanTextureEncoderBackend(TextureEncoderBackend):
    name = "vulkan"
```

Future backend selection should be based on explicit capability reporting:

- encoder executable or library availability;
- device availability and driver support;
- supported formats, including BC1 and BC3;
- batching support;
- deterministic fallback to the native backend;
- quality or validation mode for compression output.

The future scenery-studio direction should treat texture encoding as one stage
in a larger asset compilation pipeline. CUDA or Vulkan should be able to batch
texture work, report device-level diagnostics, and participate in future
imagery QA without reaching into `O4_Tile_Utils.py` or
`O4_Imagery_Utils.py` internals.

TODO-018 should document these extension points but should not expose
unfinished backend choices in the GUI or config file.

## Testing

Add deterministic `unittest` coverage.

`tests/test_texture_encoder.py` should cover:

- Windows/Linux native BC1 command planning.
- Windows/Linux native BC3 command planning.
- macOS native BC1 command planning.
- macOS native BC3 command planning.
- native backend success converts a shared subprocess result into a successful
  `TextureEncodeResult`.
- native backend failure preserves attempts, return code, and error summary.
- failed native backend retries up to the configured attempt limit.

`tests/test_texture_conversion_scheduler.py` should cover:

- the futures scheduler honors the configured worker limit;
- successful jobs produce a completed batch result;
- failed jobs are aggregated with texture summaries;
- `UI.red_flag` interrupts scheduling cleanly;
- progress accounting is based on completed futures, not queue guesses.

Existing conversion tests should be extended so DDS conversion paths assert that
`IMG.convert_texture()` delegates DDS execution to the encoder backend instead
of constructing and running raw encoder commands locally.

Existing regression coverage in `tests/test_subprocess_regression.py` should
continue to pass. No active source file should introduce direct
`subprocess.call`, `subprocess.Popen`, or `subprocess.run` usage outside the
shared subprocess runtime.

## Documentation

Update user-facing documentation only for behavior that users can observe:

- `max_convert_slots` remains the CPU texture conversion concurrency setting.
- native DDS conversion still uses bundled or resolved `nvcompress`/`DDSTool`.
- conversion failures are summarized more clearly at the end of Step 3.

Do not document CUDA or Vulkan as available backends in user docs for
TODO-018. The design/spec can describe them as future extension points.

## Acceptance Criteria

- `src/O4_Texture_Encoder.py` defines explicit texture encode request/result
  data and a native backend.
- Native DDS encoding preserves current `nvcompress` and `DDSTool` command
  semantics for BC1 and BC3.
- DDS encoder calls route through `O4_Subprocess_Utils`.
- Step 3 DDS conversion scheduling uses `concurrent.futures` with bounded CPU
  parallelism controlled by `max_convert_slots`.
- Conversion workers return structured results rather than only printing from
  worker threads.
- Failed texture conversions are aggregated and reported at tile-build level.
- Future CUDA/Vulkan backends can be added behind the same request/result
  contract without rewriting Step 3 orchestration.
- Deterministic `unittest` coverage verifies command planning, backend result
  mapping, scheduler concurrency, interruption, and failure aggregation.
- No new runtime dependency is added.
- Relevant focused tests, Ruff, ty on changed Python files, and the repository
  quality check pass before closing TODO-018.
