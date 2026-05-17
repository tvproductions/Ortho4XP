---
name: quality-check
description: Run Ortho4XP's full repository quality verification. Use when the user asks to check, validate, verify, run quality checks, pre-merge, pre-push, prepare to commit, or confirm quality for current changes.
---

# Quality Check

## Overview

Run one coherent quality gate for Ortho4XP changes. Collect deterministic evidence from tests, lint, formatting, type checks, and native build checks where relevant.

## Workflow

1. Run the full quality check:

   ```powershell
   uv run python .codex/skills/quality-check/scripts/quality_check.py
   ```

2. Refresh the complexity baseline only after intentionally accepting the current legacy envelope:

   ```powershell
   uv run python .codex/skills/quality-check/scripts/quality_check.py --complexity-only --scope all --write-complexity-baseline
   ```

3. For Python-only iteration, run:

   ```powershell
   uv run python .codex/skills/quality-check/scripts/quality_check.py --skip-native
   ```

## Rules

- Use `uv`, Ruff, ty, and `unittest`; do not introduce alternate test runners or dependency managers.
- The full quality check runs repo-wide Ruff lint, Ruff format checks for changed Python files and skill scripts, ty baseline, changed-file ty, unittest, whitespace checks, Xenon/Radon/Lizard/Cohesion complexity checks, and LLVM/CMake native checks.
- Complexity thresholds live in `complexity-thresholds.json`; accepted legacy findings live in `complexity-baseline.json`.
- Xenon uses the gzkit-style `C/C/C` gate on the modern quality target set; legacy Ortho4XP modules remain governed by the Radon/Lizard/Cohesion baseline comparison.
- Complexity regressions fail the quality check when a finding becomes worse than baseline or a new block-level finding appears.
- Native clang-tidy runs against repo native files represented in the CMake compile database, not changed-file scope.
- Native compiler and clang-tidy output is captured on successful runs to keep legacy Triangle warnings from burying actionable results; captured output is printed when a native command fails.
- Do not copy build outputs into bundled platform tool directories unless the user is intentionally refreshing release tools.
- Report skipped checks clearly with the reason.

## Evidence

In the final response, list:

- Commands run.
- Pass/fail result.
- Any warnings that remain.
- Any checks not run and why.
