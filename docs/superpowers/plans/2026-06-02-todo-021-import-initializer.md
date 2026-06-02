# TODO-021 Import Initializer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `O4_Config_Utils` config file I/O and cross-module mutation out of import time and behind an explicit runtime initializer.

**Architecture:** `O4_Config_Utils` will define an idempotent `initialize_global_config()` function that owns default assignment, global config file loading, config file creation, and existing logging behavior. `CFG.Tile` calls the initializer lazily because tile construction is config-dependent, and tests can import the module without config side effects.

**Tech Stack:** Python 3.13, stdlib `unittest`, existing `O4_UI_Utils` structured logging, existing `uv`/Ruff/ty toolchain.

---

### Task 1: Add Red Import-Initializer Tests

**Files:**
- Modify: `tests/test_config_import_safety.py`

- [ ] **Step 1: Replace the env-var-only import test with plain-import safety coverage.**

The test must remove `O4_Config_Utils` from `sys.modules`, patch `builtins.open`, import the module, and assert no config file I/O occurred and pre-set `UI`/`IMG` globals were preserved.

- [ ] **Step 2: Add explicit initializer coverage.**

The test must patch `CFG.global_cfg_file` to a temporary path, call `CFG.initialize_global_config(force=True)`, and assert defaults are applied and a missing config file is created only when the initializer runs.

- [ ] **Step 3: Run the focused test and observe failure.**

Run:

```powershell
uv run python -m unittest tests.test_config_import_safety -q
```

Expected before implementation: failures because importing `O4_Config_Utils` still performs config I/O and mutates globals, and because `initialize_global_config` does not exist.

### Task 2: Extract Explicit Config Initialization

**Files:**
- Modify: `src/O4_Config_Utils.py`

- [ ] **Step 1: Move import-time initialization into `initialize_global_config()`.**

Create an idempotent function with a `force=False` argument. Preserve the exact existing default assignment, config parsing, missing-file creation, and `UI.log_event` / `UI.log_exception` behavior.

- [ ] **Step 2: Keep import side effects removed.**

Do not call `initialize_global_config()` at module import time. Keep `validate_config_registry(cfg_vars)` at import time because it validates static registry definitions and does not read or write runtime files.

- [ ] **Step 3: Run the focused test and observe pass.**

Run:

```powershell
uv run python -m unittest tests.test_config_import_safety -q
```

Expected after implementation: all tests in `tests.test_config_import_safety` pass.

### Task 3: Wire Runtime Boundaries

**Files:**
- Modify: `src/O4_Config_Utils.py`
- Test: `tests/test_config_loading.py`

- [ ] **Step 1: Call `CFG.initialize_global_config()` at config-dependent boundaries.**

`CFG.Tile.__init__()` should call it lazily before reading config-backed globals.

- [ ] **Step 2: Preserve existing runtime tests.**

Existing config-loading tests should continue to construct `CFG.Tile` directly without `KeyError`, proving the lazy boundary preserves compatibility.

- [ ] **Step 3: Run launcher, batch, and config-loading tests.**

Run:

```powershell
uv run python -m unittest tests.test_config_loading tests.test_launcher_core tests.test_build_core tests.test_cli_jobs -q
```

Expected: all tests pass and headless validation still avoids importing `O4_Config_Utils`.

### Task 4: Update Docs and Tracker

**Files:**
- Modify: `docs/development.md`
- Modify: `docs/superpowers/specs/2026-06-01-todo-021-minimize-import-time-side-effects-design.md`
- Modify: `TODO.md`

- [ ] **Step 1: Replace env-var guidance with initializer guidance.**

Document that `O4_Config_Utils` is import-safe by default and `CFG.Tile` initializes lazily.

- [ ] **Step 2: Mark TODO-021 done with completion evidence.**

Add `Status: Done` and summarize the initializer, tests, and runtime wiring.

- [ ] **Step 3: Run quality checks.**

Run focused tests, `ruff check` for changed Python files, `ruff format --check` for changed Python files, and `ty check` for changed Python files.

- [ ] **Step 4: Comment and close GitHub issue #16.**

Include changed surfaces and verification commands in the issue comment before closing.
