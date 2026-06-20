# TODO-037 Pipeline Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable named-step pipeline orchestrator and route existing build step loops through it.

**Architecture:** `src/O4_Pipeline.py` owns generic step execution, timing, status records, and `PIPELINE_STEP` event publication. `src/O4_Build_Core.py` keeps tile lifecycle events and result mapping while delegating all-in-one and batch step execution to `Pipeline`.

**Tech Stack:** Python 3.13.x, stdlib `dataclasses`, `enum.StrEnum`, `time.perf_counter`, `unittest`, `unittest.mock`. No new runtime or development dependencies.

## Global Constraints

- Python 3.13.x is required.
- Use `unittest` only; do not introduce `pytest`.
- Preserve `BuildResult`, `BuildTileResult`, and `BuildBatchResult` contracts.
- Preserve CLI and GUI visible behavior.
- Keep `TILE_*` event ownership in `O4_Build_Core`.
- Use `PIPELINE_STEP` statuses `running`, `complete`, and `error`.
- Leave smart cache behavior to TODO-038.

---

## File Structure

- **Create:** `src/O4_Pipeline.py` - generic named-step pipeline runner.
- **Create:** `tests/test_pipeline.py` - generic pipeline unit tests.
- **Modify:** `src/O4_Build_Core.py` - replace inline step loops with `Pipeline`.
- **Modify:** `tests/test_build_events.py` - require orchestrator status payloads.
- **Modify:** `docs/superpowers/specs/2026-06-20-todo-036-event-bus-design.md` - update old event status example.
- **Modify:** `docs/superpowers/plans/2026-06-20-todo-036-event-bus.md` - update old event status examples.
- **Modify:** `TODO.md` - mark TODO-037 complete with evidence after verification.

## Tasks

- [x] Write failing `tests/test_pipeline.py` tests for named execution, timing,
  failure stopping, and exception conversion.
- [x] Verify red state with
  `uv run python -m unittest tests.test_pipeline -v`.
- [x] Implement `src/O4_Pipeline.py`.
- [x] Verify green state with
  `uv run python -m unittest tests.test_pipeline -v`.
- [x] Update build event tests to require `running`, `complete`, and `error`
  statuses plus pipeline identity.
- [x] Verify red state with
  `uv run python -m unittest tests.test_build_events -v`.
- [x] Refactor `src/O4_Build_Core.py` all-in-one and batch step loops to use
  `Pipeline`.
- [x] Verify focused integration with
  `uv run python -m unittest tests.test_pipeline tests.test_build_events -v`.
- [x] Verify build regressions with
  `uv run python -m unittest tests.test_build_core tests.test_build_context tests.test_build_core_interrupts -v`.
- [x] Run focused lint/type checks for changed Python files.
- [x] Run full `unittest` discovery.
- [x] Run the repository quality gate.
- [x] Update `TODO.md` completion evidence.
