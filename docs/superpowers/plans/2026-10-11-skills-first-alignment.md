# Skills-first Alignment Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development with bounded tasks and independent review. Do not commit or publish during implementation.

**Goal:** Implement the approved staged design in `docs/superpowers/specs/2026-10-11-skills-first-alignment-design.md`.

**Architecture:** Project-local immutable catalogs point to native-manager-owned upstream plugins. Python and native domain dependencies remain application-owned. Routine verification and explicitly requested deeper hygiene have separate commands and evidence.

**Tech Stack:** Python 3.14.8, uv 0.13.0, native Codex plugins, Ruff, ty, unittest, LLVM/CMake.

## Global Constraints

- Preserve all scientific/geospatial runtime capabilities and project operational skills.
- Preserve TODO identifiers, GitHub links, native release tools, and generated-data boundaries.
- Keep Superpowers Backplane disabled; do not modify other projects or enable plugins globally.
- Pin exact published component SHAs and keep both catalogs and bundle record coherent.
- Native installation is verified separately from configuration; fresh-session discovery cannot be inferred.
- Do not loosen quality rules or silently waive failures; retain comparable legacy evidence.
- Use unittest and TDD for consequential workflow changes. Generated locks belong to their package managers.

## Task 1: Runtime and dependency compatibility

Owner: runtime implementer. Files: `.python-version`, `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`, `install_mac.sh`, `CONTRIBUTING.md`, runtime portions of README.md, `Utils/*/*.whl`, runtime metadata tests.

- [x] Verify current Python 3.14 release metadata, download matching GDAL/NumPy assets, and verify hashes.
- [x] Probe scikit-fmm's released source on Python 3.14.8 in temporary storage; confirm finite signed-distance output on a small deterministic NumPy mask.
- [x] Add failing unittest assertions for the selected runtime/targets and platform wheel references before editing those surfaces.
- [x] Advance metadata to `>=3.14,<3.15`, `.python-version` to 3.14.8, Ruff to py314, and all installer/CI Python selections coherently.
- [x] Add the quality implementer's requested development tools to an explicit hygiene group, with current supported versions. Add pre-commit and any directly used testing utility to dev.
- [x] Resolve/sync all groups through uv and verify repeated resolution is stable. Run runtime metadata tests, core imports, GDAL MEM GeoTIFF operations, and scikit-fmm distance calculation.
- [x] Record Linux native-library constraints precisely; reconcile a supported native source before claiming compatibility.

## Task 2: Quality workflow and on-demand hygiene

Owner: quality implementer. Files: `.codex/skills/quality-check/**`, `.codex/skills/maintenance-qa/**`, `.codex/skills/repo-hygiene/**`, `.pre-commit-config.yaml`, quality/maintenance tests, project Python engineering documentation.

- [x] Read existing consumers and approved starter Python/complexity contracts. Send exact tool requirements to the runtime implementer before metadata resolution.
- [x] Add failing unittest cases that routine verification omits deep analyzers, retains lint/format/ty/unittest and native checks, and explicit hygiene refuses missing tools or measurement errors.
- [x] Make routine checks and pre-commit use only Ruff check/format, ty, and unittest; retain project structural/whitespace and native/packaging checks where required.
- [x] Implement explicit Ruff C901, complexipy, and Lizard assessment using the reviewed 20/15 and lizard-functions-v1 contracts. Preserve existing stricter Lizard regression evidence and archive final Radon/Xenon measurements before retirement.
- [x] Replace mutation integration with a compatibility-proven Cosmic Ray unittest path. Add explicit Bandit, deptry, pip-audit, and reviewed Import Linter integration alongside coverage/docstrings/dead code.
- [x] Keep deep checks opt-in; report legacy absolute failures as failures with tracking evidence, never a baseline-waived pass.
- [x] Update all affected skill instructions and examples; run meaningful focused tests, Ruff, and ty on changed Python files.

## Task 3: Native stack migration and authority

Owner: root. Files: `.skills-first/bundle.lock.json`, `.agents/plugins/marketplace.json`, `.claude-plugin/marketplace.json`, `.codex/config.toml`, `.agents/skills/skills-first-start/SKILL.md`, `AGENTS.skills-first.md`, AGENTS.md, stack adoption documentation, retired `.agents/skills/superpowers/**`.

- [x] Prepare matching catalogs and source record from the reviewed starter, with current Superpowers 7.0.0 and gz-skills 0.5.0.
- [x] Inventory native manager state, register the project catalog, and install the selected pair through the supported manager. Ensure new user-level entries remain disabled while project overrides enable the pair.
- [x] Verify installed source bytes and identities, preserve a recoverable vendored snapshot, and remove the obsolete discovery source only after replacement verification.
- [x] Add the unchanged starter front door and instructions fragment; reconcile AGENTS links and runtime/quality guidance without losing invariants.
- [x] Validate source coherence and duplicate-discovery prevention with deterministic unittest cases.

## Task 4: Review and final verification

Owner: root plus independent reviewer. Files: dependency/adoption evidence, SECURITY.md, coupled documentation.

- [x] Review runtime and quality tasks independently against the approved design, then inspect the integrated diff.
- [x] Run the complete resulting routine quality command, packaging build, runtime/native smoke checks, lock/outdated/audit checks, and explicitly requested migration hygiene.
- [x] Fix regressions and rerun from the affected check. Record absolute legacy debt and external-platform/discovery limits precisely.
- [x] Run `git diff --check`, verify no unrelated changes or generated data are tracked, and hand off the uncommitted maintenance change with evidence.

## Execution receipt

Implemented and independently reviewed without committing or publishing. See
[dependency and alignment evidence](../../dependency-refresh-2026-10-11.md),
[native adoption receipt](../../agents/skills-adoption.md), and
[quality migration receipt](../../evidence/2026-10-11-quality-migration.md).

Checked tasks mean their implementation and stated assessment were performed.
They do not assert clean deep hygiene or verified foreign-platform execution:
deep hygiene remains FAIL, Linux native compilation and macOS execution remain
unverified, and native-asset provenance and packaging-boundary defects remain
tracked in the evidence. Routine/native Windows verification, the final four
pre-commit hooks, packaging startup probes, lock consistency and advisory checks
passed. Final independent review found no introduced implementation regressions.
