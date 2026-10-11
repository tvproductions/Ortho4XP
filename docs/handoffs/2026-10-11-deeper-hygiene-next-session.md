# Ortho4XP next-session handoff — 2026-10-11

Observed at 2026-10-11 23:00 UTC. Branch: `master`. HEAD before this save point:
`dc6ee33559c51b7e986a961bcc014e0a43d6829f`, aligned with `origin/master` after
a fresh fetch. The new work is the deeper-hygiene review/evidence and this handoff.
This document will be committed and synced with that evidence; verify current
HEAD/worktree on resume rather than treating the captured SHA as current forever.

## Resume point

The next recommended Ortho4XP task is **DH-001: repair streamed-subprocess
deadlock**, from the [review](../evidence/2026-10-11-deeper-hygiene-review.md#high-priority-findings).
The review's bounded witness completed in 0.033 seconds through captured
execution but hit a two-second child watchdog through streamed execution when
the child wrote substantial stderr before stdout. Mesh and overlay callers use
the affected runner.

First permissible action: read DH-001, `src/O4_Subprocess_Runtime.py` and
`tests/test_subprocess_utils.py`; check current Git state and the existing tests.
If the next user request authorizes this repair, use Superpowers design/TDD
guidance and add a deterministic, bounded real-child regression in the repository
tests. Preserve separate stdout/stderr, stdout callbacks, exit status and cleanup.
Expected result: the large-stderr child completes normally without waiting for
the watchdog, and existing streamed/captured consumer tests still pass.
Do not implement the recommendation merely because this handoff names it.
Stop for a conflicting contract or missing authorization; never weaken the test
or merge stderr into stdout simply to avoid the blocking condition.

## Settled work and evidence

- Skills-first adoption and dependency updates are committed in `dc6ee33`.
  [Initial evidence](../dependency-refresh-2026-10-11.md) and
  [follow-up evidence](../dependency-refresh-2026-10-11-follow-up.md) record the
  approved design and reviewed versions: starter 0.1.0, Superpowers 7.0.0,
  gz-skills 0.6.0. Native source pins are in `.skills-first/bundle.lock.json`.
- The default project `.venv` was subsequently recreated by **uv itself** from
  `uv.lock`, using the existing persistent uv-managed Python 3.14.8 installation.
  All 93 installed packages passed `uv pip check`; scientific/geospatial imports,
  GDAL 3.13.3 and Tk 9.0 passed. The full unittest suite passed **590 tests** in
  this actual `.venv`. The commit hook now references `.venv/Scripts/python.exe`.
  `.venv` and the host interpreter are local-only; another checkout must sync its
  own environment. Use uv's normal persistent interpreter/cache locations.
- The user reported that the 14 plugin warnings appeared to be gone.
  [Diagnostic record](../evidence/2026-10-11-plugin-warning-analysis.md) preserves
  the missing-cache-file report and successful fresh discovery; the original
  transient cause was not proved.
- [Fresh deeper-hygiene review](../evidence/2026-10-11-deeper-hygiene-review.md)
  and its committed-with-this-handoff receipts are the authority for DH-001
  through DH-009. No application fix was implemented during that review.
  Deep hygiene still fails; passing routine checks do not make it clean.

## Decisions and authorization

The user approved full starter alignment while preserving Ortho4XP's additional
dependencies and project rules. AGENTS.md remains binding: `unittest`, project
operational skills, native LLVM/CMake, TODO/GitHub links and generated-data
boundaries remain intact. Work uses `master` under the project's stated policy.
Backplane remains deferred and disabled; installation inventory is not readiness.

Current explicit request: **create a handoff and git sync**. It authorizes this
documentation/evidence save point and ordinary guarded commit/push. The previous
deeper-hygiene request authorized review, not wholesale implementation. The
listed repairs remain recommendations until a subsequent request authorizes
their execution. No additional merge/release/deployment/profile activation is
authorized by this document.

The user explicitly supports uv managing the repo environment. An earlier
automatic-review rejection misinterpreted an objection to scratch-file work as
an objection to uv; the user clarified authorization, and the normal uv rebuild
then succeeded. That obsolete rejection is not a standing restriction on uv.

The user rejected the ad hoc scratch-script approach and requested cleanup.
All 11 authored scratch/diagnostic fixture scripts were removed. Use the normal
project `.venv` and established commands; put consequential regression coverage
in `tests/`. Do not recreate temporary scripts/environments as the primary
maintenance workflow. Archived diagnostic source copies are evidence, not an
instruction to reinstate the removed scratch workflow. The gz-skills ownership
discussion belongs in its own repository; it did not authorize plugin redesign
or changes to other projects here.

## Follow-on order and limits

After an authorized DH-001 fix, the review recommends DH-002 provider refresh
recovery, DH-003 data-only airport caches, and DH-004/005 analyzer-contract
repairs. Add meaningful tests with each fix; clarify coverage semantics before
using its totals to prioritize broader work. Retain thresholds and actual failed
measurements. The review provides each finding's exact location, acceptance
shape and evidence; do not duplicate that backlog here or invent TODO IDs.

Linux/macOS execution, release packaging boundaries and older native-asset
provenance remain limited as recorded in the dependency evidence. This handoff
does not certify those surfaces. No GitHub Issue/PR was created for this review;
follow project issue/TODO conventions when implementation is selected.

Suggested workflow: `gzs-session-handoff` to resume; project `quality-check` and
`git-sync` for their owned operations; applicable Superpowers design, debugging,
TDD and verification skills for an authorized fix. Deeper assessments remain
explicit maintenance actions, outside routine hooks and CI.

## Environment and verification on resume

While preparing this save point, the full routine quality gate and required
quick hygiene gate passed in the normal repository environment: 590 tests,
Ruff/format/ty, stack-source validation, structural/whitespace checks, native
clang-tidy/LLVM/CMake verification and distribution builds. Existing structural
warnings remain documented; deeper-hygiene findings were not waived.

```powershell
uv sync --locked --all-groups
uv run --locked --all-groups python -c "import sys; print(sys.executable); print(sys.version)"
uv pip check --python .venv/Scripts/python.exe
uv run --locked --all-groups python -m unittest discover -s tests
uv run --locked --all-groups python .codex/skills/quality-check/scripts/quality_check.py
```

The project quick-sync gate uses dev-only synchronization internally. After it
finishes, restore the requested all-group environment with
`uv sync --locked --all-groups`; do not hand off a silently pruned environment.
Keep hooks enabled. Sync evidence is the resulting commit and actual final
local/remote SHA, ahead/behind counts and worktree state, verified separately
from this pre-commit observation.
