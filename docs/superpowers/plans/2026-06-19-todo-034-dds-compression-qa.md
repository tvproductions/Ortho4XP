# TODO-034 DDS Compression QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional DDS compression QA that decodes the generated DDS, compares it with the source PNG, and warns when PSNR falls below a configurable threshold.

**Architecture:** Add a focused `O4_DDS_Quality.py` module for decode, metric computation, and warning policy. Wire it into `O4_Texture_Conversion_Utils.convert_dds_texture()` after successful native encoding and before temporary PNG cleanup so cached, filtered, masked, and in-memory DDS conversions share the same QA path.

**Tech Stack:** Python 3.13, Pillow, NumPy, standard-library `unittest`, existing `uv`, Ruff, ty, and repository quality-check.

## Global Constraints

- Use `unittest` only.
- Keep network, X-Plane installs, GDAL command-line tools, and native DDS encoder execution out of tests.
- `dds_qa_enabled` defaults to `False`.
- `dds_qa_psnr_threshold` defaults to `30.0` dB and controls the warning gate.
- Use Pillow to decode DDS to PNG where supported; report decode/metric failures as warnings without failing conversion.
- Work on `master` by default per repository AGENTS.md.

---

### Task 1: DDS QA Metrics And Decode Helper

**Files:**
- Create: `src/O4_DDS_Quality.py`
- Test: `tests/test_dds_quality.py`

**Interfaces:**
- Produces: `compute_quality_metrics(source_path: str, decoded_path: str) -> DdsQualityMetrics`
- Produces: `decode_dds_to_png(dds_path: str, decoded_png_path: str) -> None`
- Produces: `run_dds_quality_check(source_png_path: str, dds_path: str, decoded_png_path: str, threshold: float, display_name: str) -> DdsQualityMetrics | None`

- [x] **Step 1: Write failing metric and warning tests**

Run: `uv run python -m unittest tests.test_dds_quality -q`

Expected: fail because `O4_DDS_Quality` does not exist.

- [x] **Step 2: Implement the helper module**

Create a frozen metrics dataclass with `mse`, `psnr`, `width`, and `height`. Compare RGB/RGBA arrays using NumPy, return infinite PSNR for identical images, save decoded DDS output through Pillow, and print `WARNING: DDS QA quality below threshold` through `UI.vprint(1, ...)` when PSNR is below threshold.

- [x] **Step 3: Verify focused helper tests**

Run: `uv run python -m unittest tests.test_dds_quality -q`

Expected: pass.

### Task 2: Config Surface

**Files:**
- Modify: `src/O4_Cfg_Vars.py`
- Test: `tests/test_dds_quality.py`

**Interfaces:**
- Produces tile/global settings: `dds_qa_enabled`, `dds_qa_psnr_threshold`, `global_dds_qa_enabled`, `global_dds_qa_psnr_threshold`

- [x] **Step 1: Write failing config test**

Run: `uv run python -m unittest tests.test_dds_quality_config -q`

Expected: fail because the config keys are absent.

- [x] **Step 2: Add config definitions**

Add `dds_qa_enabled` and `dds_qa_psnr_threshold` to `cfg_tile_vars` near `cog_export`, and include both in `list_other_vars` so tile and global config files expose them.

- [x] **Step 3: Verify config test**

Run: `uv run python -m unittest tests.test_dds_quality_config -q`

Expected: pass.

### Task 3: DDS Conversion Integration

**Files:**
- Modify: `src/O4_Texture_Conversion_Utils.py`
- Test: `tests/test_dds_quality.py`

**Interfaces:**
- Consumes: `O4_DDS_Quality.run_dds_quality_check`
- Consumes: tile attributes `dds_qa_enabled` and `dds_qa_psnr_threshold`
- Produces: unchanged `TextureConversionResult` conversion success/failure semantics

- [x] **Step 1: Write failing integration tests**

Run: `uv run python -m unittest tests.test_dds_quality_conversion -q`

Expected: fail because `convert_dds_texture()` does not call DDS QA.

- [x] **Step 2: Wire QA after successful encode**

In `convert_dds_texture()`, after `TEX.encode_texture(request)`, call DDS QA only when the encode succeeds and `tile.dds_qa_enabled` is true. Use a decoded PNG path in `tmp` derived from the output DDS filename. Always run temp cleanup in the existing `finally`.

- [x] **Step 3: Verify integration tests**

Run: `uv run python -m unittest tests.test_dds_quality_conversion -q`

Expected: pass.

### Task 4: Documentation And TODO Closeout

**Files:**
- Modify: `README.md`
- Modify: `TODO.md`

**Interfaces:**
- Produces documented opt-in settings and completion evidence.

- [x] **Step 1: Document DDS QA**

Add a short `DDS compression QA` subsection under texture conversion scheduling describing `dds_qa_enabled=True`, `dds_qa_psnr_threshold`, decode-to-PNG comparison, and warning behavior.

- [x] **Step 2: Mark TODO-034 done**

Update TODO-034 status to `Done (2026-06-19)` and add completion evidence with commands actually run.

- [x] **Step 3: Run verification**

Run:

```powershell
uv run python -m unittest tests.test_dds_quality tests.test_dds_quality_config tests.test_dds_quality_conversion tests.test_texture_encoder tests.test_cog_geotiff_export -q
uv run python -m unittest discover -s tests
uv run ruff check src/O4_DDS_Quality.py src/O4_Texture_Conversion_Utils.py src/O4_Cfg_Vars.py tests/test_dds_quality.py tests/test_dds_quality_config.py tests/test_dds_quality_conversion.py
uv run ruff format --check src/O4_DDS_Quality.py src/O4_Texture_Conversion_Utils.py src/O4_Cfg_Vars.py tests/test_dds_quality.py tests/test_dds_quality_config.py tests/test_dds_quality_conversion.py
uv run ty check src/O4_DDS_Quality.py src/O4_Texture_Conversion_Utils.py src/O4_Cfg_Vars.py tests/test_dds_quality.py tests/test_dds_quality_config.py tests/test_dds_quality_conversion.py
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected: all commands pass, or any blocker is recorded with exact output and tracking.

## Self-Review

- Spec coverage: config flag, DDS decode-to-PNG, PSNR/MSE metrics, configurable threshold warning, metric tests, docs, and TODO evidence are covered.
- Placeholder scan: no placeholder steps remain.
- Type consistency: helper names match the integration call surface.
