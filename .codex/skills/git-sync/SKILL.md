---
name: git-sync
description: Run the guarded Ortho4XP repository sync ritual. Use when the user says "git sync", asks to sync local work with origin, wants local/origin branch reconciliation, or needs a gzkit-style commit/pull/push routine for this repo.
---

# Git Sync

## Overview

Run the guarded repository sync ritual. This is the project-local version of the gzkit `git-sync` pattern: dry-run first, apply second, report evidence, and stop on unsafe states.

## Workflow

1. Preview planned actions:
   `uv run python .codex/skills/git-sync/scripts/git_sync.py --branch master`
2. Execute the standard ritual:
   `uv run python .codex/skills/git-sync/scripts/git_sync.py --branch master --apply`
3. Skip push only when explicitly requested:
   `uv run python .codex/skills/git-sync/scripts/git_sync.py --branch master --apply --no-push`

The command fetches with prune before computing ahead/behind state. Apply mode auto-adds changes, runs the project hygiene quick gate, creates a sync commit when staged changes exist, pulls with fast-forward or rebase as needed, pushes when ahead, and prints blockers or warnings.

## Constraints

- Never force-push.
- Never use `--no-verify`.
- Never bypass a failed hygiene gate.
- Never delete branches as part of this routine.
- Stop on detached HEAD, missing remote branch, merge commit at HEAD, or unresolved conflicts.
- Use `master` unless the user explicitly asks to sync another branch.

## Red Flags

- Force push appears anywhere in the routine.
- Hygiene failure is treated as cosmetic.
- Divergence is resolved by reset or force instead of the guarded pull step.
- Dry-run completes but apply is skipped when the user asked to sync.
- Sync runs while generated local data is staged unintentionally.

## Validation

After successful apply, run the dry-run command again. The expected end state is `ahead=0`, `behind=0`, no blockers, and no unintended staged or unstaged files.
