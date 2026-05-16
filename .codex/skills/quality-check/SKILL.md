---
name: quality-check
description: Run Ortho4XP's full repository quality verification. Use when the user asks to check, validate, verify, run quality checks, pre-merge, pre-push, prepare to commit, or confirm quality for current changes.
---

# Quality Check

## Overview

Run one coherent quality gate for Ortho4XP changes. Collect deterministic evidence from tests, lint, formatting, type checks, and native build checks where relevant.

## Workflow

1. Inspect the workspace:

   ```powershell
   git status --short --branch
   git diff --stat
   git diff --cached --stat
   git diff --name-only --diff-filter=ACMRTUXB HEAD -- "*.py"
   ```

2. Run the Python baseline:

   ```powershell
   uv run python -m unittest discover -s tests
   uv run ruff check Ortho4XP.py src tests
   uv run ty check tests src/O4_Geo_Utils.py src/O4_File_Names.py
   ```

3. For changed Python files, also run:

   ```powershell
   uv run ruff format --check <changed-python-files>
   uv run ty check <changed-python-files>
   ```

4. For docs, workflow, or config changes, run:

   ```powershell
   git diff --check
   ```

5. For native C/CMake changes, run:

   ```powershell
   clang-tidy --verify-config
   cmake --preset llvm-release -S Utils
   cmake --build Utils/build/llvm-release --target Triangle4XP
   ```

## Rules

- Use `uv`, Ruff, ty, and `unittest`; do not introduce alternate test runners or dependency managers.
- Format only changed Python files unless the user explicitly asks for repo-wide formatting.
- Do not copy build outputs into bundled platform tool directories unless the user is intentionally refreshing release tools.
- Report skipped checks clearly with the reason.

## Evidence

In the final response, list:

- Commands run.
- Pass/fail result.
- Any warnings that remain.
- Any checks not run and why.
