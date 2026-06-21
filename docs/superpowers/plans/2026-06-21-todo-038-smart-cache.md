# Smart Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SHA256 tile parameter caching for full tile builds.

**Architecture:** Introduce a focused `O4_Build_Cache` helper that owns
canonical parameter snapshots and hit/miss decisions, with
`O4_Build_Cache_IO` owning low-level JSON, SHA256, and atomic-write mechanics.
`O4_Build_Core` stays responsible for build policy: checking the helper before
full-build orchestration, publishing `CACHE_HIT`, and writing metadata only
after successful full builds.

**Tech Stack:** Python 3.13, stdlib `json`, `hashlib`, `os`, `tempfile`,
`unittest`, existing `O4_Event_Bus` events.

## Global Constraints

- Use `unittest` only.
- Run TDD: write failing tests first and verify the expected failure.
- Apply cache skipping only to complete `vector, mesh, masks, tile` builds.
- Treat malformed or missing metadata as a cache miss.
- Log metadata write failures without failing a successful tile build.

---

### Task 1: Cache Helper

**Files:**
- Create: `src/O4_Build_Cache.py`
- Create: `src/O4_Build_Cache_IO.py`
- Create: `tests/test_build_cache.py`

**Interfaces:**
- Produces: `tile_meta_path(tile) -> str`
- Produces: `parameter_snapshot(tile) -> dict[str, object]`
- Produces: `parameter_hash(tile) -> str`
- Produces: `read_cache_hit(tile) -> CacheHit | None`
- Produces: `write_cache_metadata(tile) -> None`

- [ ] Write failing tests for deterministic hash, hash changes, cache hit,
      stale hash miss, malformed metadata miss, and metadata write shape.
- [ ] Run `uv run python -m unittest tests.test_build_cache -v` and confirm
      the tests fail because `O4_Build_Cache` is missing.
- [ ] Implement `O4_Build_Cache` with canonical JSON hashing and atomic writes.
- [ ] Re-run `uv run python -m unittest tests.test_build_cache -v` and confirm
      the tests pass.

### Task 2: Build Core Integration

**Files:**
- Modify: `src/O4_Build_Core.py`
- Modify: `tests/test_build_core.py`
- Modify: `tests/test_build_events.py`
- Create: `tests/test_build_core_cache.py`
- Create: `tests/test_build_cache_events.py`

**Interfaces:**
- Consumes: `O4_Build_Cache.read_cache_hit(tile)`
- Consumes: `O4_Build_Cache.write_cache_metadata(tile)`
- Produces: `CACHE_HIT` event payload with `lat`, `lon`, `mode`,
  `metadata_path`, and `parameter_hash`.

- [ ] Write failing all-in-one tests proving matching metadata skips all build
      step functions and stale metadata runs them.
- [ ] Write failing batch tests proving a full default batch skips, while a
      partial batch does not skip.
- [ ] Run focused build tests and confirm expected failures.
- [ ] Add cache checks before full-build execution and metadata writes after
      full-build success.
- [ ] Re-run focused build tests and confirm they pass.

### Task 3: Backlog Evidence and Verification

**Files:**
- Modify: `TODO.md`

**Interfaces:**
- Consumes: verification command output.
- Produces: completion evidence for `TODO-038`.

- [ ] Update `TODO-038` status and completion evidence.
- [ ] Run focused tests:
      `uv run python -m unittest tests.test_build_cache tests.test_build_core tests.test_build_events -v`
- [ ] Run full tests:
      `uv run python -m unittest discover -s tests`
- [ ] Run quality gate:
      `uv run python .codex/skills/quality-check/scripts/quality_check.py`
