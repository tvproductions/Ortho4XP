---
name: quality-check
description: Run Ortho4XP routine repository verification for validation, pre-merge, pre-push, or commit preparation. Deep hygiene requires an explicit request.
---

# Quality Check

Run the routine repository command:

```powershell
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

It runs unittest, project-locked Ruff check, Ruff format checks on changed Python
files and maintained skill scripts, ty on the reviewed baseline and changed files,
whitespace and structural audits, and LLVM/CMake verification. Native checks
cover source represented in the compile database and retain failure output.
Use `--skip-native` for a Python-only iteration and report that omission.

Structural audits retain the existing module/class size policy, ty-ignore rules
and unittest-only test policy. Never weaken these policies to make a gate pass.
Build artifacts remain in `Utils/build`; copying release binaries is a separate
authorized operation.

Deep analyzers do not run through this command, hooks, or CI. When explicitly
requested, use:

```powershell
uv run --group hygiene python .codex/skills/quality-check/scripts/quality_check.py --complexity-only --scope all
```

This runs independent Ruff C901 (20), complexipy cognitive/script (15), and
Lizard `lizard-functions-v1` (function/module/overall ceilings 20), then the
existing stricter Lizard regression ratchet and retained Cohesion measurements.
Cohesion's historical LCOM4 policy is unverified and fails explicitly; its actual
percentages cannot be interpreted as LCOM4. All absolute failures
remain failures even when unchanged from the baseline. A missing analyzer,
invalid source, or AST/Lizard function-discovery mismatch fails measurement.
Receipts go to a new `tmp/complexity-hygiene-*` directory.

The active `complexity-baseline.json` retains old Lizard identities and
scores. `--write-complexity-baseline` requires complete full-scope measurements,
no errors, no new finding identities and no increased scores; it can only shrink
the existing baseline and cannot turn absolute ceiling failures into success.
Preserve historical comparisons in `docs/evidence/2026-10-11-legacy-*`.

See [project Python engineering](../../../docs/agents/python-engineering.md)
for tool interpretation, archived metrics, explicit hygiene, and mutation proof.
Report actual commands, results, debt evidence and unverified checks.
