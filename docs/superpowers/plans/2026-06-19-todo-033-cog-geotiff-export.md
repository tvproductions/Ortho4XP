# TODO-033 COG-Style GeoTIFF Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional COG-style GeoTIFF export with tiled JPEG GeoTIFF creation options and internal overview pyramids.

**Architecture:** `cog_export` is a tile/global-tile boolean config key because GeoTIFF export is tile output behavior. `O4_Texture_Conversion_Utils` derives GDAL creation options from `tile.cog_export` and builds overviews only after a successful final GeoTIFF write.

**Tech Stack:** Python 3.13, `unittest`, `osgeo.gdal`, existing Ortho4XP config registry.

## Global Constraints

- Use `unittest` only.
- Use `uv`, Ruff, ty, and the repository quality-check script for verification.
- Preserve current GeoTIFF output when `cog_export` is false.
- Do not change generated GeoTIFF filenames.
- Do not add runtime dependencies.

---

### Task 1: Config Boundary

**Files:**
- Modify: `src/O4_Cfg_Vars.py`
- Test: `tests/test_config_models.py`

**Interfaces:**
- Produces: `tile.cog_export: bool`, default `False`
- Produces: `global_cog_export` through existing global tile config expansion

- [ ] **Step 1: Write the failing test**

Add a test asserting `cog_export` is a bool tile/global-tile setting with default `False` and validates legacy config values.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_config_models -q`
Expected: failure because `cfg_tile_vars["cog_export"]` does not exist.

- [ ] **Step 3: Implement config key**

Add `cog_export` to `cfg_tile_vars` near imagery output settings and include it in `list_dsf_vars`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_config_models -q`
Expected: pass.

### Task 2: GDAL COG Options and Overviews

**Files:**
- Modify: `src/O4_Texture_Conversion_Utils.py`
- Test: `tests/test_gdal_geotiff.py`

**Interfaces:**
- Consumes: `tile.cog_export: bool`
- Produces: final GeoTIFF creation options `["COMPRESS=JPEG"]` by default
- Produces: final COG creation options `["COMPRESS=JPEG", "TILED=YES", "BLOCKXSIZE=512", "BLOCKYSIZE=512"]`
- Produces: `gdal.Open(output_path, gdal.GA_Update).BuildOverviews("AVERAGE", [2, 4, 8, 16])` only when `cog_export` is true

- [ ] **Step 1: Write failing tests**

Add tests for small-tile Translate options, large-tile Warp options, no overview when disabled, and overview build when enabled.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_gdal_geotiff -q`
Expected: failure because COG creation options and overview build are not implemented.

- [ ] **Step 3: Implement minimal converter changes**

Add helper functions for final GeoTIFF creation options and COG overview generation, then call them from the successful conversion path.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_gdal_geotiff -q`
Expected: pass.

### Task 3: Docs and Backlog Evidence

**Files:**
- Modify: `README.md`
- Modify: `TODO.md`

**Interfaces:**
- Documents: `cog_export` default-off behavior and COG benefits
- Records: TODO-033 completion evidence

- [ ] **Step 1: Document the setting**

Add a short GeoTIFF export section explaining tiled COG-style output and overviews.

- [ ] **Step 2: Update TODO evidence**

Mark TODO-033 done and include verification evidence.

- [ ] **Step 3: Verify docs formatting**

Run focused Ruff/check commands as part of the final verification gate.

### Task 4: Final Verification

**Files:**
- Verify changed Python and docs.

**Interfaces:**
- Confirms TODO-033 acceptance criteria.

- [ ] **Step 1: Run focused tests**

Run: `uv run python -m unittest tests.test_config_models tests.test_gdal_geotiff -q`

- [ ] **Step 2: Run full unittest discovery**

Run: `uv run python -m unittest discover -s tests`

- [ ] **Step 3: Run changed-file lint/type checks**

Run: `uv run ruff check src/O4_Cfg_Vars.py src/O4_Texture_Conversion_Utils.py tests/test_config_models.py tests/test_gdal_geotiff.py`
Run: `uv run ty check src/O4_Cfg_Vars.py src/O4_Texture_Conversion_Utils.py tests/test_config_models.py tests/test_gdal_geotiff.py`

- [ ] **Step 4: Run repository quality gate**

Run: `uv run python .codex/skills/quality-check/scripts/quality_check.py`
