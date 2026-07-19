# Superpowers Hygiene Refresh Design

## Goal

Keep the repository's vendored Superpowers release current through a
repeatable, non-mutating hygiene check and an explicit, reproducible updater.
Refresh the current `v6.0.3` vendor tree to the latest verified stable release,
`v6.1.1`.

## Scope

This change covers the Superpowers tree vendored at
`.agents/skills/superpowers`, its source metadata, repository hygiene
integration, deterministic tests, and the immediate release refresh. It does
not install Superpowers globally, track unreleased upstream `main`, mutate the
vendor tree during a hygiene check, or remove branches or worktrees.

## Architecture

Add a focused vendor-management script beside the existing repository hygiene
script. The tool owns four related operations:

1. Parse the upstream repository and pinned commit from
   `.agents/skills/superpowers/SOURCE.md`.
2. Validate that the local package and plugin manifests agree on one semantic
   version.
3. Discover the newest stable `vMAJOR.MINOR.PATCH` upstream tag and resolve its
   peeled commit with `git ls-remote`.
4. On an explicit update request, stage that exact release in a temporary
   directory, preserve the documented local adaptations, replace the vendor
   payload, and update `SOURCE.md`.

The existing `hygiene.py` entry point invokes the check in both `--quick` and
`--full` modes. It never invokes update mode.

## Interfaces and Behavior

The command surface is:

```powershell
uv run python .codex/skills/repo-hygiene/scripts/superpowers_vendor.py --check
uv run python .codex/skills/repo-hygiene/scripts/superpowers_vendor.py --update
```

`--check` has these outcomes:

- Current stable release: exit 0 and print the version and pinned commit.
- Confirmed stale release: exit nonzero and print the exact `--update` command.
- Upstream unavailable: exit 0 with a visible warning, preserving offline
  development while making the unverifiable state explicit.
- Missing, malformed, or internally inconsistent local metadata: exit
  nonzero with the defective files and values.

`--update` first performs the same metadata and upstream checks. It then clones
the exact latest stable tag into a temporary staging directory. Before
replacement, it refuses to proceed when the vendored path has uncommitted
changes. It excludes upstream Git metadata, retains `SOURCE.md`, applies the
documented whitespace and Python hygiene adaptations, updates the pinned tag,
version, and commit, and leaves the working tree changes uncommitted for normal
review and repository verification.

The updater must restore the previous vendor directory if replacement fails.
Temporary staging and backup directories must be removed after success; a
failed cleanup must be reported rather than hidden.

## Release Selection

The tool selects the highest stable semantic-version tag matching
`vMAJOR.MINOR.PATCH`. Pre-release tags, malformed tags, and unreleased commits
on `main` are ignored. Annotated tags are compared using their peeled commit so
`SOURCE.md` records the source tree commit rather than the tag-object commit.

For this implementation, the observed upstream release is `v6.1.1`, tag
commit `d884ae04edebef577e82ff7c4e143debd0bbec99`, published on 2026-07-02.

## Local Adaptations

The existing vendor metadata documents three repository-specific adaptations:

- remove trailing whitespace from `README.md` and `RELEASE-NOTES.md`;
- format `tests/claude-code/analyze-token-usage.py` with Ruff;
- retain explicit `TypedDict` annotations in that Python test utility when
  required by the repository type gate.

The updater applies these transformations deterministically after staging the
upstream release. If the newer upstream already satisfies an adaptation, the
operation is a no-op. `SOURCE.md` remains the authoritative record of both the
upstream pin and retained adaptations.

## Hygiene Integration

`hygiene.py` runs the Superpowers check before dependency synchronization and
the longer Python/native gates. Confirmed drift therefore fails quickly and
prints the repair command. Network failure warns and allows later hygiene
stages to run.

The check is part of both quick and full hygiene. Consequently, a dirty-tree
`git-sync --apply` also runs it through the existing quick hygiene gate before
creating or pushing an automatic sync commit.

## Testing

Tests use standard-library `unittest`, `unittest.mock`, and temporary local Git
repositories. They do not contact GitHub. Coverage includes:

- stable semantic-version tag selection and annotated-tag peeling;
- current, stale, unavailable-upstream, and malformed-metadata check outcomes;
- disagreement between package/plugin manifest versions;
- update refusal when the vendor tree is dirty;
- exact-tag staging, source-pin update, local adaptation preservation, and
  rollback after replacement failure;
- quick and full hygiene invoking the check before longer gates.

After the deterministic tests pass, perform one live check against
`https://github.com/obra/superpowers`, update to `v6.1.1`, run the upstream
Superpowers tests that are portable on Windows, and run the complete Ortho4XP
quality gate.

## Error Handling and Safety

- Hygiene checks never modify files.
- Updates require the explicit `--update` flag.
- The updater never changes Git branches, worktrees, remotes, or history.
- The updater never deletes a dirty vendor tree.
- Replacement targets are resolved and verified beneath the repository's
  `.agents/skills` directory before any rename or removal.
- No force push, reset, or repository-wide clean operation is used.
- All failures identify whether the local tree was preserved or restored.

## Completion Criteria

- Branch/worktree audit remains clean: only the intended `master` checkout and
  no stale linked worktrees.
- Vendored manifests and `SOURCE.md` identify `v6.1.1` at
  `d884ae04edebef577e82ff7c4e143debd0bbec99`.
- Quick and full hygiene enforce confirmed release freshness without failing
  solely because the network is unavailable.
- Deterministic unit tests and the full repository quality gate pass.
- The refresh and hygiene automation are committed and synchronized to
  `origin/master` through the guarded git-sync workflow.
