# Provider Failover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic provider failover with temporary blacklisting for concrete imagery texture downloads.

**Architecture:** Introduce `O4_Provider_Failover` as a focused, thread-safe provider health registry and selection helper. Integrate it into `O4_Texture_Download_Scheduler`, which already owns texture retry and queueing, so failed provider attempts can be recorded and blacklisted providers can be replaced without changing HTTP internals or DSF terrain generation.

**Tech Stack:** Python 3.13, stdlib `threading`, `time`, `dataclasses`, `unittest`, existing async texture scheduler, existing `O4_UI_Utils` logging.

## Global Constraints

- Use `unittest` only.
- Run TDD: write failing tests first and verify the expected failure.
- Apply failover only to concrete providers in `providers_dict`.
- Blacklist a provider after 3 consecutive failed texture attempts.
- Use a 300 second blacklist timeout.
- Keep combined providers out of this first failover surface.
- Do not change tile coordinates or zoom level during failover.

---

### Task 1: Provider Failover Registry

**Files:**
- Create: `src/O4_Provider_Failover.py`
- Create: `tests/test_provider_failover.py`

**Interfaces:**
- Produces: `ProviderFailoverRegistry(failure_threshold=3, timeout_seconds=300, clock=time.monotonic)`
- Produces: `record_failure(provider_code: str) -> ProviderHealthState`
- Produces: `record_success(provider_code: str) -> None`
- Produces: `is_blacklisted(provider_code: str) -> bool`
- Produces: `select_replacement(failed_provider: str, providers: dict[str, dict]) -> str | None`
- Produces: `reset() -> None`

- [ ] Write failing tests for success reset, third-failure blacklist, timeout expiry, and deterministic replacement selection.
- [ ] Run `uv run python -m unittest tests.test_provider_failover -v` and confirm failure because the module is missing.
- [ ] Implement `O4_Provider_Failover` with a locked registry, monotonic timeout handling, and deterministic provider ordering.
- [ ] Re-run `uv run python -m unittest tests.test_provider_failover -v` and confirm the tests pass.

### Task 2: Download Scheduler Integration

**Files:**
- Modify: `src/O4_Texture_Download_Scheduler.py`
- Modify: `tests/test_texture_async_downloads.py`

**Interfaces:**
- Consumes: `O4_Provider_Failover.default_registry`
- Produces: failed provider attempts recorded after failed texture builds.
- Produces: successful provider attempts resetting failure state.
- Produces: replacement provider attributes requeued when a provider becomes blacklisted and another provider is eligible.

- [ ] Write a failing scheduler test where three failed `BI` attempts blacklist `BI`, requeue the same texture with `Arc`, and enqueue the successful `Arc` source for conversion.
- [ ] Run `uv run python -m unittest tests.test_texture_async_downloads -v` and confirm the new test fails because failover is not integrated.
- [ ] Add scheduler hooks that record success/failure and choose a replacement before ordinary same-provider retry.
- [ ] Re-run `uv run python -m unittest tests.test_texture_async_downloads tests.test_provider_failover -v` and confirm the tests pass.

### Task 3: Backlog Evidence and Verification

**Files:**
- Modify: `TODO.md`

**Interfaces:**
- Consumes: verification command output.
- Produces: completion evidence for `TODO-040`.

- [ ] Update `TODO-040` status and completion evidence.
- [ ] Run focused tests:
      `uv run python -m unittest tests.test_provider_failover tests.test_texture_async_downloads tests.test_imagery_failures -v`
- [ ] Run changed-file Ruff:
      `uv run ruff check src/O4_Provider_Failover.py src/O4_Texture_Download_Scheduler.py tests/test_provider_failover.py tests/test_texture_async_downloads.py`
- [ ] Run changed-file format check:
      `uv run ruff format --check src/O4_Provider_Failover.py src/O4_Texture_Download_Scheduler.py tests/test_provider_failover.py tests/test_texture_async_downloads.py`
- [ ] Run changed-file ty:
      `uv run ty check src/O4_Provider_Failover.py src/O4_Texture_Download_Scheduler.py tests/test_provider_failover.py tests/test_texture_async_downloads.py`
- [ ] Run full tests:
      `uv run python -m unittest discover -s tests`
- [ ] Run full quality gate:
      `uv run python .codex/skills/quality-check/scripts/quality_check.py`
