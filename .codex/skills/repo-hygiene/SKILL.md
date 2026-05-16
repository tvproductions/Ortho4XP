---
name: repo-hygiene
description: Run repository hygiene workflows for Ortho4XP build readiness, workspace tidiness, and modern-toolchain validation. Use when asked to clean up, prepare, audit generated artifacts, check TODO/ROADMAP sequencing, or validate Python, CMake, CI, or native utility changes.
---

# Repo Hygiene

## Core Policy

Use this skill only inside the Ortho4XP repository. Keep the workflow modern and project-local:

- Python 3.13+ through `uv`.
- `unittest` only for tests.
- `ruff check` and `ruff format`.
- `ty` for type checking changed Python files and the current baseline.
- LLVM/Clang CMake presets for native C builds.
- `clang-format` and `clang-tidy` for changed native C/C++ lines.
- No gzkit dependency.

Never introduce alternate test runners, legacy `pip`/manual-venv setup, or MSVC-first native build instructions.

## Default Workflow

1. Inspect state:
   - `git status --short --branch`
   - `git diff --stat`
   - `git diff --cached --stat`
2. Identify changed Python files:
   - Prefer `git diff --name-only --diff-filter=ACMRTUXB HEAD -- "*.py"`.
3. Run hygiene checks:
   - `uv sync --dev`
   - `uv run python -m unittest discover -s tests`
   - `uv run ruff check Ortho4XP.py src`
   - `uv run ruff format --check <changed-python-files>`
   - `uv run ty check tests src/O4_Geo_Utils.py src/O4_File_Names.py`
   - Also run `uv run ty check <changed-python-files>` when changed Python files exist.
4. For native build work, run:
   - `clang-format` on changed native C/C++ lines.
   - `clang-tidy --verify-config`.
   - `clang-tidy` on changed native C/C++ lines when a compile database exists.
   - `cmake --fresh --preset llvm-release -S Utils`
   - `cmake --build Utils/build/llvm-release --target Triangle4XP`
5. Check for forbidden or stale patterns:
   - No non-unittest test runner references.
   - No `requirements.txt`, manual `venv`, or `pip install` setup instructions.
   - No generated data staged for commit.

## Project Hygiene Script

Prefer the bundled script for repeatable checks:

```powershell
uv run python .codex/skills/repo-hygiene/scripts/hygiene.py --quick
uv run python .codex/skills/repo-hygiene/scripts/hygiene.py --full
```

Use `--quick` for normal code changes. Use `--full` before commits, syncs, or native build changes. The script enforces formatting on changed Python files to avoid mass-formatting unrelated legacy modules during phased modernization.

## Workspace Tidiness

Generated local data must remain uncommitted: `.venv/`, `Utils/build/`, `OSM_data/`, `Masks/`, `Orthophotos/`, `Elevation_data/`, `Geotiffs/`, `Tiles/`, `tmp/`, `yOrtho4XP_Overlays/`, and `Ortho4XP.cfg`.

Do not delete user data automatically. If generated files appear untracked, report them and confirm before removal unless they are known throwaway outputs created during the current task.

## TODO and ROADMAP Discipline

Use `TODO.md` as the executable queue and `ROADMAP.md` as rationale. If a task reveals missing prerequisites, reorder or split `TODO.md` before proceeding. Preserve completed statuses when renumbering.
