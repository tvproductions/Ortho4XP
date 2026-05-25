# Logarithmic Alpha Mask Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the final linear `3steps` coastline alpha fade with a tested progressive logarithmic curve while leaving bathymetry distance masks unchanged.

**Architecture:** Add a small pure helper in `src/O4_Mask_Utils.py` for normalized alpha reduction, then use it only in the final `3steps` sea fade inside `blur_mask()`. Tests live in a focused `unittest` module and exercise the helper contract plus source-level integration so no full tile build, imagery provider, compressor, or X-Plane install is required.

**Tech Stack:** Python 3.13, `unittest`, `numpy`, `Pillow`, existing Ortho4XP mask utilities, `uv`, Ruff, ty.

---

## File Structure

- Create `src/O4_Mask_Alpha.py`
  - Add the pure `progressive_log_alpha_ratio(ratio)` helper.
- Modify `src/O4_Mask_Utils.py`
  - Import `progressive_log_alpha_ratio` from `O4_Mask_Alpha`.
  - Replace only the final `3steps` sea fade formula with the helper.
- Create `tests/test_mask_alpha.py`
  - Add deterministic `unittest` coverage for the helper.
  - Add source-level regression tests that verify `blur_mask()` uses the helper in the final fade and keeps `distance_masks_too` out of the alpha helper surface.

## Task 1: Add Failing Alpha Helper Tests

**Files:**
- Create: `tests/test_mask_alpha.py`
- Modify: none
- Test: `tests/test_mask_alpha.py`

- [ ] **Step 1: Write the failing helper contract tests**

Create `tests/test_mask_alpha.py` with this content:

```python
import inspect
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Mask_Utils as MASK


class ProgressiveLogAlphaRatioTests(unittest.TestCase):
    def test_progressive_log_alpha_ratio_has_exact_clamped_endpoints(self):
        self.assertEqual(MASK.progressive_log_alpha_ratio(-0.25), 0.0)
        self.assertEqual(MASK.progressive_log_alpha_ratio(0.0), 0.0)
        self.assertEqual(MASK.progressive_log_alpha_ratio(1.0), 1.0)
        self.assertEqual(MASK.progressive_log_alpha_ratio(1.25), 1.0)

    def test_progressive_log_alpha_ratio_is_monotonic_and_bounded(self):
        samples = [
            MASK.progressive_log_alpha_ratio(ratio)
            for ratio in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)
        ]

        self.assertEqual(samples, sorted(samples))
        for value in samples:
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_progressive_log_alpha_ratio_preserves_more_alpha_than_linear_near_shore(self):
        self.assertLess(MASK.progressive_log_alpha_ratio(0.25), 0.25)
        self.assertLess(MASK.progressive_log_alpha_ratio(0.5), 0.5)
        self.assertGreater(MASK.progressive_log_alpha_ratio(0.75), 0.5)

    def test_blur_mask_final_sea_fade_uses_progressive_log_alpha_ratio(self):
        source = inspect.getsource(MASK.blur_mask)

        self.assertIn(
            "sea_level * (1 - progressive_log_alpha_ratio((i + 1) / stepsout))",
            source,
        )
        self.assertNotIn(
            'sea_level * (1 - transition_profile((i + 1) / stepsout, "linear"))',
            source,
        )

    def test_progressive_alpha_helper_does_not_consume_distance_masks(self):
        source = inspect.getsource(MASK.progressive_log_alpha_ratio)

        self.assertNotIn("distance_masks_too", source)
        self.assertNotIn("distance_mask", source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused tests and verify they fail for the missing helper**

Run:

```powershell
uv run python -m unittest tests.test_mask_alpha -q
```

Expected result: failure or error because `O4_Mask_Utils.progressive_log_alpha_ratio` does not exist yet.

## Task 2: Implement the Alpha Helper

**Files:**
- Create: `src/O4_Mask_Alpha.py`
- Modify: `src/O4_Mask_Utils.py`
- Test: `tests/test_mask_alpha.py`

- [ ] **Step 1: Add the logarithmic helper**

Create `src/O4_Mask_Alpha.py` with this content:

```python
from math import log1p


def progressive_log_alpha_ratio(ratio):
    ratio = max(0.0, min(1.0, float(ratio)))
    if ratio == 0.0 or ratio == 1.0:
        return ratio

    curve_strength = 9.0
    return 1 - (log1p(curve_strength * (1 - ratio)) / log1p(curve_strength))
```

In `src/O4_Mask_Utils.py`, add this import with the other local imports:

```python
from O4_Mask_Alpha import progressive_log_alpha_ratio
```

- [ ] **Step 2: Run the focused tests and verify only the integration assertion still fails**

Run:

```powershell
uv run python -m unittest tests.test_mask_alpha -q
```

Expected result: helper tests pass, and the source-level integration test still fails because `blur_mask()` still uses the linear transition.

## Task 3: Apply the Helper to the Final 3-Step Fade

**Files:**
- Modify: `src/O4_Mask_Utils.py`
- Test: `tests/test_mask_alpha.py`

- [ ] **Step 1: Replace the final linear sea fade**

In the final `3steps` loop inside `blur_mask()`, replace:

```python
stepsout = int(transout / 3)
for i in range(stepsout):
    value = sea_level * (1 - transition_profile((i + 1) / stepsout, "linear"))
```

with:

```python
stepsout = int(transout / 3)
for i in range(stepsout):
    value = sea_level * (1 - progressive_log_alpha_ratio((i + 1) / stepsout))
```

- [ ] **Step 2: Run the focused tests and verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_mask_alpha -q
```

Expected result: all tests in `tests.test_mask_alpha` pass.

## Task 4: Quality Verification and TODO Closure

**Files:**
- Modify: `TODO.md`
- Test: repository quality checks

- [ ] **Step 1: Run formatting on changed files**

Run:

```powershell
uv run ruff format src\O4_Mask_Alpha.py src\O4_Mask_Utils.py tests\test_mask_alpha.py
```

Expected result: Ruff formats the changed files or reports they are already formatted.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
uv run python -m unittest tests.test_mask_alpha -q
```

Expected result: all focused mask alpha tests pass.

- [ ] **Step 3: Run the full unittest suite**

Run:

```powershell
uv run python -m unittest discover -s tests
```

Expected result: the full `unittest` suite passes.

- [ ] **Step 4: Run lint and type checks for changed Python files**

Run:

```powershell
uv run ruff check Ortho4XP.py src
uv run ty check src\O4_Mask_Alpha.py src\O4_Mask_Utils.py tests\test_mask_alpha.py
```

Expected result: Ruff and ty complete without errors for the changed surfaces.

- [ ] **Step 5: Run the repository quality check when practical**

Run:

```powershell
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected result: the full repository quality check passes. If it fails, fix actionable defects before completion or record any external blocker with evidence.

- [ ] **Step 6: Mark TODO-015 done after verification**

In `TODO.md`, update the TODO-015 block from:

```markdown
### TODO-015: Rewrite Alpha Masking for Logarithmic BC3 Blending

GitHub Issue: #10
```

to:

```markdown
### TODO-015: Rewrite Alpha Masking for Logarithmic BC3 Blending

Status: Done

GitHub Issue: #10
```

- [ ] **Step 7: Commit implementation**

Run:

```powershell
git status --short
git add src\O4_Mask_Alpha.py src\O4_Mask_Utils.py tests\test_mask_alpha.py TODO.md docs\superpowers\specs\2026-05-25-logarithmic-alpha-mask-design.md docs\superpowers\plans\2026-05-25-logarithmic-alpha-mask-plan.md
git commit -m "Implement logarithmic alpha mask blending"
```

Expected result: implementation commit is created after tests and quality checks pass.

## Self-Review

- Spec coverage: helper contract, final `3steps` fade replacement, existing zero-step loop behavior, `distance_masks_too` non-interference, byte-range output preservation, focused tests, and quality checks are covered.
- Placeholder scan: this plan contains no placeholder tasks or deferred implementation notes.
- Type consistency: the planned function name is consistently `progressive_log_alpha_ratio(ratio)`, imported into `O4_Mask_Utils`, and all commands use `unittest` per repo policy.
