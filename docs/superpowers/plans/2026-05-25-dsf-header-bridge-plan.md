# DSF Header Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a non-destructive DSFTool bridge that copies allowlisted native XP12 DSF header text features into generated Ortho4XP DSFs.

**Architecture:** Keep `O4_DSF_Utils.build_dsf` as the Step 4 DSF build entry point and preserve its binary mesh writer. Add a focused bridge module that finds the default Global Scenery DSF, converts default and generated DSFs to text through `O4_Subprocess_Utils.run_external_tool`, extracts only allowlisted header lines, writes a spliced text staging file, and replaces the generated `.dsf.tmp` only after `DSFTool --text2dsf` succeeds.

**Tech Stack:** Python 3.13, standard-library `unittest`, existing Ortho4XP subprocess helper, bundled `DSFTool` and `7z` tool resolution.

---

### Task 1: Parser Tests

**Files:**
- Create: `tests/test_dsf_header_bridge.py`
- Create: `src/O4_DSF_Header_Bridge.py`

- [ ] Write failing tests for extracting season, vegetation, sound, and runway friction header lines from fixture DSF text.
- [ ] Run `uv run python -m unittest tests.test_dsf_header_bridge -q` and verify the import/function failure.
- [ ] Implement the minimal parser and splice helpers.
- [ ] Re-run the focused test and verify it passes.

### Task 2: DSFTool Loop Tests

**Files:**
- Modify: `tests/test_dsf_header_bridge.py`
- Modify: `src/O4_DSF_Header_Bridge.py`

- [ ] Write failing tests that assert `--dsf2text` is used for default and generated DSFs and `--text2dsf` is used for the spliced text.
- [ ] Write failing tests that assert missing default DSFs, failed DSFTool calls, and empty unsupported headers leave the generated DSF unchanged.
- [ ] Implement staged text/binary file handling with cleanup.
- [ ] Re-run the focused test and verify it passes.

### Task 3: Step 4 Integration

**Files:**
- Modify: `src/O4_DSF_Utils.py`
- Modify: `tests/test_bathymetry_gate.py` or `tests/test_dsf_header_bridge.py`

- [ ] Write a failing integration assertion that `build_dsf` invokes the bridge after the generated `.dsf.tmp` is complete.
- [ ] Call the bridge from `build_dsf` after checksum writing and before returning success.
- [ ] Keep bathymetry extraction before the bridge unchanged.
- [ ] Re-run focused DSF tests and bathymetry gate tests.

### Task 4: Verification and Tracking

**Files:**
- Modify: `TODO.md`

- [ ] Run focused tests.
- [ ] Run `uv run python -m unittest discover -s tests`.
- [ ] Run practical broader checks for changed Python files.
- [ ] Add evidence to GitHub Issue #12 and update TODO tracking if the issue is closed or remains open.
