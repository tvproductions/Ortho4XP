# Repository Guidelines

## PRIME DIRECTIVE (OWNERSHIP)

1. **YOU OWN THE WORK COMPLETELY.** No deferral, no rationalized incompleteness.
2. **COMPLETE ALL WORK FULLY.** Fix broken/misaligned things immediately.
   - Code change with output format change -> update ALL doc examples; commit together.
   - Documentation references a feature -> examples show real CLI output where practical.
   - Tests pass but unrelated lint error found -> fix it before declaring complete.
   - Markdown invalid in a file you did not edit -> fix it; code quality is shared.
3. **NEVER SAY:** "out of scope", "skip for now", "someone else's problem", "leave as TODO".
4. **SCOPE EXPANSION IS NOT SCOPE CREEP.** If fixing requires updating three docs, do it.
5. **FLAG DEFECTS, NEVER EXCUSE THEM.** Anti-rationalizations:
   - "Pre-existing" -> still a defect.
   - "Not in scope" -> flag and expand, or file a GitHub Issue.
   - "Template has drifted" -> drift is a defect.
   - "Evidence unavailable" -> missing evidence is a verification-chain defect.
6. **EVERY DEFECT MUST BE TRACKABLE.** In-scope -> fix immediately. Out-of-scope -> file a GitHub Issue and reference it from `TODO.md`, or record the defect in the active work evidence. Untrackable defect = nonexistent defect.

## DO IT RIGHT (CRAFTSMANSHIP MAXIM)

**The most thorough and comprehensive fix is preferred.**

1. **Fix the class of failure, not just the instance.** Identify the failure
   family and remove the reason it can recur.
2. **Keep coupled surfaces coherent.** When a change touches data another
   surface reads or validates, run or update the consumer check in the same
   change.
3. **No vibe coding.** Do not write plausible-looking code or manifests without
   reading the relevant surface, tracing the data flow, and verifying observed
   behavior.
4. **Prefer the more thorough fix.** Smaller diffs and faster landing are not
   meaningful wins if they leave known drift or incomplete verification.
5. **Verify observed behavior, not assumed behavior.** Run the command, inspect
   the output, and report what actually happened.
6. **Read before changing.** Read the local code, docs, manifests, and reference
   material that govern the surface before editing it.
7. **Tests assert semantics, not incidental strings.** Expected values should
   come from requirements and documented behavior, not from copying whatever a
   first run happened to print.
8. **Verify runtime surfaces before recommending incantations.** If a command,
   script, deploy path, or X-Plane layout is part of the recommendation, run or
   inspect the real surface first.
9. **Quote conflicting directives verbatim when rules collide.** Do not hand-wave
   competing instructions; name the conflict and resolve it explicitly.

## Superpowers Workflow

Superpowers skills are vendored under `.agents/skills/superpowers/skills/`.
Use them as mandatory workflow guidance when their trigger conditions apply.

Core workflow:

1. **Check for relevant skills before acting.** If a Superpowers skill may apply,
   read and follow that skill before responding, asking clarifying questions, or
   editing files.
2. **Brainstorm before design-heavy implementation.** For rough ideas, ambiguous
   features, or broad changes, use `brainstorming` to clarify goals and present
   design choices in reviewable chunks before implementation.
3. **Use isolated worktrees only when appropriate.** For risky or parallel branch
   work, use `using-git-worktrees`; otherwise follow this repo's normal `master`
   workflow.
4. **Write plans for approved designs.** Use `writing-plans` when implementation
   needs multiple coordinated steps. Plans should name exact files, verification
   commands, and small executable tasks.
5. **Execute plans with discipline.** Use `subagent-driven-development` when
   explicit parallel agent work is appropriate and available; otherwise use
   `executing-plans` with checkpoints.
6. **Use TDD for behavior changes.** Use `test-driven-development` to write or
   update failing tests first, confirm the failure, implement the minimum fix,
   and confirm the pass.
7. **Review before declaring completion.** Use `requesting-code-review` or a
   local review pass between substantial tasks, and use
   `verification-before-completion` before any completion claim.
8. **Finish branches deliberately.** Use `finishing-a-development-branch` when
   branch/worktree cleanup, merge, PR, or handoff decisions are needed.

The Superpowers README summarizes the philosophy as test-driven development,
systematic process over guessing, complexity reduction, and evidence over
claims. These reinforce this repo's PRIME DIRECTIVE and DO IT RIGHT rules.

## Project Structure & Module Organization

`Ortho4XP.py` is the launcher. Core Python modules live in `src/` and follow the existing `O4_*` module naming pattern. Unit tests live in `tests/` and use standard-library `unittest` only. Native C utility sources and CMake files live in `Utils/`; bundled platform tools are staged in `Utils/win`, `Utils/mac`, and `Utils/lin`. Provider and asset data live in `Providers/`, `Filters/`, `Extents/`, `Patches/`, `Previews/`, and `Licence/`.

## Modern Toolchain

Windows 11 is the primary development environment for now. Keep choices portable to current Apple Silicon macOS and Ubuntu. Python 3.13.x is required; `.python-version` pins local `uv` environments to Python 3.13. `uv.lock` is committed and authoritative.

Use:

- `uv sync --dev`
- `uv run python -m unittest discover -s tests`
- `uv run ruff check Ortho4XP.py src`
- `uv run ruff format .`
- `uv run ty check <changed-python-files>`
- `uv run python .codex/skills/quality-check/scripts/quality_check.py`

Run `ty` on changed Python files and expand the checked baseline as files are modernized.
Run the full quality check before commit or sync when practical; it includes
unittest, Ruff, ty, whitespace checks, Radon/Lizard/Cohesion complexity checks,
and native LLVM/CMake verification.

## Native Builds

Native C utilities should use LLVM/Clang through the CMake presets for a uniform Windows/macOS/Linux posture. Any LLVM install is acceptable if CMake can find `clang`, `llvm-rc` on Windows, and lld.

Build `Triangle4XP` with:

```bash
clang-tidy --verify-config
cmake --preset llvm-release -S Utils
cmake --build Utils/build/llvm-release --target Triangle4XP
```

Use `.clang-format` and `.clang-tidy` for changed native C/C++ code. The project hygiene script checks changed native lines to avoid reformatting the legacy Triangle baseline all at once.

Build artifacts stay in `Utils/build/...`. Copy into `Utils/win`, `Utils/mac`, or `Utils/lin` only when intentionally refreshing bundled release tools.

## Testing Rules

Use `unittest` only. Name files `tests/test_*.py` and classes `*Tests`. Keep tests deterministic and independent of network access, X-Plane installs, GDAL command-line tools, or imagery providers. Reuse `tests/_path.py` for import-path setup.

## Generated Data

Generated scenery/cache data is local-only and must not be committed: `OSM_data/`, `Masks/`, `Orthophotos/`, `Elevation_data/`, `Geotiffs/`, `Tiles/`, `tmp/`, and `yOrtho4XP_Overlays/`. Provider definitions, filters, patches, previews, and bundled utilities are source assets unless explicitly generated.

## Workflow & Priorities

Work on `master` by default for this fork. Use short-lived branches only for risky, experimental, or externally reviewed changes. Keep commits scoped and use concise imperative messages.

Use `TODO.md` as the actionable queue. Use `ROADMAP.md` for direction and rationale. If TODO ordering blocks practical implementation, reorder or phase `TODO.md` before proceeding so the next item is genuinely executable.

When answering "next backlog item" or similar queue-selection prompts, cite the
TODO identifier, such as `TODO-037`, instead of exposing `TODO.md` line numbers.

Keep GitHub Issues current for TODO-backed work. When a TODO item maps to a GHI, add an implementation/evidence comment before final handoff and close the issue when acceptance criteria and repository quality checks have passed. If the issue should remain open, comment with the remaining blocker and reference that tracking state from the active work evidence.

## Releases

Releases are PyInstaller onedir bundles built per target OS/architecture; do not assume cross-packaging. Target Windows 11, current Apple Silicon macOS, and Ubuntu. Package data should include `Utils`, `Extents`, `Filters`, `Licence`, `Patches`, `Previews`, `Providers`, and `community_server.txt`; trim platform-inapplicable utility folders before distribution.
