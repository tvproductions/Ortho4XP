# Superpowers Brownfield Workflow Design

## Problem

Ortho4XP has a strong repo policy, a detailed TODO queue, issue-backed work,
and quality gates, but architectural work still risks becoming a sequence of
patches instead of a product-development loop. Superpowers should provide that
loop without fighting Ortho4XP's existing constraints.

## Goals

- Make Superpowers the normal process for meaningful design and development
  work in this brownfield repo.
- Let Superpowers absorb active TODO work into specs and plans.
- Keep Ortho4XP's existing technical rules authoritative for implementation
  and verification.
- Make design intent, execution tasks, and completion evidence easy to trace.
- Allow lightweight handling for tiny mechanical edits while preserving the
  rule that agents check for applicable skills before acting.

## Non-Goals

- Redesign Ortho4XP's mesh, DSF, mask, imagery, GUI, or packaging architecture
  in this spec.
- Convert every historical or completed TODO into Superpowers artifacts.
- Require git worktrees or branches for every change.
- Replace GitHub Issues as external project tracking.

## Current Context

Relevant repo surfaces:

- `AGENTS.md` defines ownership, DO IT RIGHT, toolchain, testing, native build,
  TODO/GitHub Issue, and release rules.
- `.agents/skills/superpowers/` vendors Superpowers skills directly in the repo.
- `TODO.md` currently contains the executable backlog and many GitHub Issue
  links.
- `ROADMAP.md` contains strategic direction, including XP12Max mesh, mask,
  imagery, and hardware modernization.
- `.codex/skills/quality-check` provides the full repository quality gate.
- The repo has large legacy modules where changes need prior design:
  `O4_GUI_Utils.py`, `O4_Imagery_Utils.py`, `O4_Config_Utils.py`,
  `O4_DSF_Utils.py`, `O4_Mask_Utils.py`, `O4_Mesh_Utils.py`, and related
  utility modules.

## Superpowers Operating Model

### Skill Check First

For every non-trivial task, the agent checks whether a Superpowers skill applies
before asking clarifying questions, exploring files, editing code, or claiming a
result. If a skill applies, the agent announces which skill is being used and
why, then follows it.

Tiny mechanical edits may use the normal Ortho4XP workflow after this check, but
the agent must still verify the edit before claiming completion.

### Work Classification

Each task is classified before execution:

- **Exploratory or design-heavy work:** use `brainstorming`.
- **Bug, regression, or unexpected behavior:** use `systematic-debugging`.
- **Approved multi-step implementation:** use `writing-plans`, then
  `executing-plans` or `subagent-driven-development` when parallel agents are
  appropriate and available.
- **Behavior changes:** use `test-driven-development` where deterministic
  testing is feasible.
- **Review or handoff:** use `requesting-code-review`,
  `receiving-code-review`, and `verification-before-completion` as applicable.
- **Branch or worktree cleanup:** use `finishing-a-development-branch` when the
  work actually used branches or worktrees.

### Ortho4XP Constraints Still Govern Outputs

Superpowers controls the development process. Ortho4XP rules control the
implementation envelope:

- Python 3.13+, `uv`, Ruff, ty, and standard-library `unittest`.
- Native C/C++ changes use LLVM/Clang, CMake presets, `.clang-format`, and
  `.clang-tidy`.
- Full quality-check is required before closing TODO-backed work when practical.
- GitHub Issue evidence comments and TODO completion updates remain required
  until that tracking model is deliberately replaced.
- Work happens on `master` by default unless a branch or worktree is justified.

## Artifact Model

### Specs

Specs live under:

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
```

A spec owns intent and design. It should include:

- problem statement
- current repo context
- goals and non-goals
- proposed architecture or behavior
- affected modules and boundaries
- data flow and error handling
- testing and verification strategy
- risks, tradeoffs, and tracking links

Specs are written after design approval from the user. They are self-reviewed
for placeholders, contradictions, excessive scope, and ambiguity before the user
is asked to review the written file.

### Plans

Plans live under:

```text
docs/superpowers/plans/YYYY-MM-DD-<topic>-plan.md
```

A plan owns execution. It should break approved specs into small tasks with:

- exact files or modules to inspect or edit
- expected behavior changes
- tests to add or update
- verification commands
- review checkpoints
- issue evidence and closeout steps when applicable

Implementation starts only after the plan is approved or the user explicitly
directs execution from an approved plan.

## TODO And Issue Integration

Superpowers is the natural execution system for active work. `TODO.md` may
remain as legacy intake while the repo transitions.

Recommended migration:

1. Leave completed TODOs as historical records.
2. When a queued TODO becomes active, convert it into a Superpowers spec.
3. Replace detailed active TODO implementation notes with links to the spec,
   plan, GitHub Issue, and final evidence.
4. Let GitHub Issues track external state and discussion, with comments linking
   to specs, plans, and verification.
5. Once enough active work uses Superpowers artifacts, reduce `TODO.md` to a
   concise intake/index or deprecate it in favor of `docs/superpowers/`.

This avoids a forced big-bang migration while letting Superpowers absorb the
work that matters.

## Verification And Completion

Before any completion claim, the agent uses `verification-before-completion`:

1. Identify which command proves the claim.
2. Run the command fresh.
3. Read the output and exit code.
4. Report the actual result.

For Ortho4XP, common verification commands include:

```bash
uv run python -m unittest discover -s tests
uv run ruff check Ortho4XP.py src tests
uv run ty check <changed-python-files>
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Native changes also require the relevant LLVM/CMake checks from `AGENTS.md`.

## Risks And Tradeoffs

- **Risk: process overhead for small edits.** Mitigation: classify tiny
  mechanical edits separately while still requiring skill check and verification.
- **Risk: duplicate tracking between TODO, specs, plans, and issues.**
  Mitigation: make specs/plans authoritative for active work and shrink TODO
  entries as they are migrated.
- **Risk: Superpowers conflicts with existing repo rules.** Mitigation:
  `AGENTS.md` and explicit user instructions remain higher priority than
  generic skill guidance.
- **Risk: broad architecture specs become too large to execute.** Mitigation:
  decompose into smaller specs before planning implementation.

## First Application

Use this workflow on the next meaningful Ortho4XP architecture task. The likely
first candidate is TODO-014, requiring valid bathymetry inputs for XP12 physical
water meshes. That task should begin with `brainstorming`, produce a focused
design spec, then transition to `writing-plans`.
