# Task 3 Report: Upgrade Seam Detection and Optional Neighbor Context

## Scope

Implemented Task 3 from `.superpowers/sdd/task-3-brief.md` in:

- `src/O4_Provider_Score_Seams.py`
- `src/O4_Provider_Score_Edges.py`
- `src/O4_Provider_Score_Metrics.py`
- `src/O4_Provider_Scoring.py`
- `tests/test_provider_scoring.py`

Left `TODO.md` unchanged. Task 3 is only part of `TODO-041`, and the full repo
quality gate did not reach a clean pass state.

## TDD Evidence

### RED: added failing seam tests first

Added the three required tests to `ProviderScoringTests`:

- `test_single_problematic_edge_increases_seam_risk_and_identifies_edge`
- `test_abrupt_border_gradient_increases_seam_risk`
- `test_neighbor_edge_mismatch_increases_seam_risk_when_context_is_supplied`

Also added the required `numpy` import.

### RED command

```powershell
uv run python -m unittest tests.test_provider_scoring.ProviderScoringTests.test_single_problematic_edge_increases_seam_risk_and_identifies_edge tests.test_provider_scoring.ProviderScoringTests.test_abrupt_border_gradient_increases_seam_risk tests.test_provider_scoring.ProviderScoringTests.test_neighbor_edge_mismatch_increases_seam_risk_when_context_is_supplied
```

Sandbox note: `uv.exe` was blocked in the sandbox (`Access is denied`), so I
reran the exact same command with escalation as instructed.

RED result summary:

- `test_single_problematic_edge_increases_seam_risk_and_identifies_edge`
  errored with `KeyError: 'seam_risk'`
- `test_abrupt_border_gradient_increases_seam_risk`
  errored with `KeyError: 'seam_risk'`
- `test_neighbor_edge_mismatch_increases_seam_risk_when_context_is_supplied`
  errored with
  `AttributeError: module 'O4_Provider_Scoring' has no attribute 'ProviderScoreContext'`

This matched the expected missing seam details and missing scoring-context
plumbing.

### GREEN command

```powershell
uv run python -m unittest tests.test_provider_scoring.ProviderScoringTests.test_single_problematic_edge_increases_seam_risk_and_identifies_edge tests.test_provider_scoring.ProviderScoringTests.test_abrupt_border_gradient_increases_seam_risk tests.test_provider_scoring.ProviderScoringTests.test_neighbor_edge_mismatch_increases_seam_risk_when_context_is_supplied
```

GREEN result summary:

- Ran 3 tests
- `OK`

## Implementation Summary

### `src/O4_Provider_Score_Seams.py`

- Replaced the old single-score heuristic with
  `seam_risk_score_details(sample, scoring_context=None)`.
- Computes seam metrics independently for `left`, `right`, `top`, and `bottom`.
- Records per-edge:
  - `risk`
  - `luminance_drift`
  - `rgb_drift`
  - `border_gradient`
  - `neighbor_drift`
- Returns:
  - `worst_edge`
  - `edges`
  - `neighbor_compared`
- Uses optional `ProviderScoreContext.neighbor_edges` without adding any new
  runtime dependency or non-deterministic behavior.
- Preserved the simple `seam_risk_score()` wrapper for existing callers.

Boundary selection for border gradients uses the sampled edge band against the
immediately adjacent interior row/column. I verified that the right and bottom
checks compare the correct boundary (`width - band` vs `width - band - 1`,
`height - band` vs `height - band - 1`) rather than flipping edge direction.

### `src/O4_Provider_Score_Edges.py`

- Exported `seam_risk_score_details` through the compatibility facade.

### `src/O4_Provider_Score_Metrics.py`

- Switched seam scoring to `EDGE.seam_risk_score_details(sample, scoring_context)`.
- Stored seam detail payload under `details["seam_risk"]`.

### `src/O4_Provider_Scoring.py`

- Added optional `scoring_context` to:
  - `score_provider_image(...)`
  - `score_and_log_provider_image(...)`
- Imported `ProviderScoreContext` into the module so the tests and external
  callers can access `SCORE.ProviderScoreContext`.

### `tests/test_provider_scoring.py`

- Added the three seam-behavior tests from the plan.
- Refactored repeated score/image setup into small test helpers while keeping
  the required seam assertions in `ProviderScoringTests`.

## Verification

### Passed checks

```powershell
uv run python -m unittest tests.test_provider_scoring -q
```

- Ran 12 tests
- `OK`

```powershell
uv run ruff check src/O4_Provider_Score_Seams.py src/O4_Provider_Score_Edges.py src/O4_Provider_Score_Metrics.py src/O4_Provider_Scoring.py tests/test_provider_scoring.py
```

- `All checks passed!`

```powershell
uv run ruff format --check src/O4_Provider_Score_Seams.py src/O4_Provider_Score_Edges.py src/O4_Provider_Score_Metrics.py src/O4_Provider_Scoring.py tests/test_provider_scoring.py
```

- `5 files already formatted`

```powershell
uv run ty check src/O4_Provider_Score_Seams.py src/O4_Provider_Score_Edges.py src/O4_Provider_Score_Metrics.py src/O4_Provider_Scoring.py tests/test_provider_scoring.py
```

- `All checks passed!`

### Full quality gate

```powershell
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Result summary:

- Full unittest suite passed: `Ran 423 tests` / `OK`
- Repo-wide Ruff passed
- Changed-file Ruff format check passed
- Changed-file ty check passed
- Quality gate still exited non-zero on complexity baseline regressions

Reported blockers:

- `src/O4_Provider_Score_Clouds.py`
  - `BLOCK radon_mi=42.8558 ... <module> - new block-level complexity finding`
- `src/O4_Provider_Score_Seams.py`
  - `BLOCK lizard_nesting_depth=4 ... _border_pair(...)`
  - `BLOCK lizard_param_count=7 ... _edge_detail(...)`
  - `BLOCK radon_mi=34.2285 ... <module>`
- `tests/test_provider_scoring.py`
  - `BLOCK radon_mi=40.8053 ... <module>`

The cloud-module blocker is outside this task's changed-file set. The seam
module and scoring test file remain functional and clean under unittest, Ruff,
format, and ty, but they still trip the repo's complexity baseline.

## Files Changed

- `src/O4_Provider_Score_Seams.py`
- `src/O4_Provider_Score_Edges.py`
- `src/O4_Provider_Score_Metrics.py`
- `src/O4_Provider_Scoring.py`
- `tests/test_provider_scoring.py`
- `.superpowers/sdd/task-3-report.md`

## Self-Review

- Followed TDD in order: wrote tests, captured RED, implemented, captured GREEN.
- Kept the implementation deterministic and local-only.
- Added no optional ML/runtime dependencies.
- Did not modify `TODO.md` because Task 3 does not complete `TODO-041` and the
  full repository quality gate still reports complexity baseline regressions.
- Did not revert or overwrite unrelated work.

## Task 3 complexity fix

Refined the Task 3 scoring implementation to clear the repo complexity gate
without changing the public scoring interfaces.

### Refactor summary

- Reduced seam-module complexity by moving edge extraction and seam-stat helpers
  into focused internal modules:
  - `src/O4_Provider_Score_Edge_Data.py`
  - `src/O4_Provider_Score_Seam_Stats.py`
- Reduced cloud-module complexity by extracting cloud channel/mask helpers into:
  - `src/O4_Provider_Score_Channel_Data.py`
  - `src/O4_Provider_Score_Cloud_Data.py`
- Reduced test-module complexity by moving image fixtures and score helpers into:
  - `tests/_provider_scoring_helpers.py`
  - `tests/_provider_scoring_images.py`
- Preserved the Task 3 public surface:
  - `seam_risk_score_details(sample, scoring_context=None)`
  - `seam_risk_score(sample)`
  - `ProviderScoreContext`
  - optional `scoring_context` on scoring entry points

### Required verification commands

```powershell
uv run python -m unittest tests.test_provider_scoring -q
```

Result:

- `Ran 12 tests`
- `OK`

```powershell
uv run ruff check src/O4_Provider_Score_Channel_Data.py src/O4_Provider_Score_Cloud_Data.py src/O4_Provider_Score_Clouds.py src/O4_Provider_Score_Edge_Data.py src/O4_Provider_Score_Sampling.py src/O4_Provider_Score_Seam_Stats.py src/O4_Provider_Score_Seams.py tests/_provider_scoring_helpers.py tests/_provider_scoring_images.py tests/test_provider_scoring.py
```

Result:

- `All checks passed!`

```powershell
uv run ruff format --check src/O4_Provider_Score_Channel_Data.py src/O4_Provider_Score_Cloud_Data.py src/O4_Provider_Score_Clouds.py src/O4_Provider_Score_Edge_Data.py src/O4_Provider_Score_Sampling.py src/O4_Provider_Score_Seam_Stats.py src/O4_Provider_Score_Seams.py tests/_provider_scoring_helpers.py tests/_provider_scoring_images.py tests/test_provider_scoring.py
```

Result:

- `10 files already formatted`

```powershell
uv run ty check src/O4_Provider_Score_Channel_Data.py src/O4_Provider_Score_Cloud_Data.py src/O4_Provider_Score_Clouds.py src/O4_Provider_Score_Edge_Data.py src/O4_Provider_Score_Sampling.py src/O4_Provider_Score_Seam_Stats.py src/O4_Provider_Score_Seams.py tests/_provider_scoring_helpers.py tests/_provider_scoring_images.py tests/test_provider_scoring.py
```

Result:

- `All checks passed!`

```powershell
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Result summary:

- Full unittest suite passed: `Ran 423 tests` / `OK`
- Repo-wide Ruff passed
- Changed-file Ruff format check passed
- Changed-file ty check passed
- Complexity baseline check passed
- Native LLVM/CMake verification ran cleanly

### Outcome

- Cleared the Task 3 seam/test complexity regressions.
- Cleared the previously noted cloud-module complexity regression encountered
  during full-gate verification.
- Left `TODO.md` unchanged; this pass fixed the quality gate but did not close
  `TODO-041` on its own.
