# Task 3 Report: Sand-Mask Width and Shape Validation

## Implementation summary

- Added the pure `O4_Mask_Validation` module with immutable `SandMaskGeometry`
  and `validate_sand_mask()`.
- Sand builds now validate meter width, scale, and the expected working image
  geometry before creating a mask destination or deleting old masks.
- Sand convolution now uses validated geometry against the actual array shape.
- Invalid scalar or non-finite/negative widths, invalid shapes (including
  `None` and scalars), and over-sized kernels raise user-readable `ValueError`s.

## TDD evidence

1. RED: `uv run python -m unittest tests.test_mask_validation -v` before the
   module existed failed with `ModuleNotFoundError: No module named
   'O4_Mask_Validation'`.
2. GREEN: after implementation, the same command passed all 4 tests.
3. Review RED: the independent reviewer identified malformed scalar shapes;
   adding `None` and `0` shape cases made the focused test fail with the
   expected pre-fix `TypeError` at `len(image_shape)`.
4. Review GREEN: catching that `TypeError` and raising `ValueError` made all
   validation tests pass.

## Commands and results

- `uv run python -m unittest tests.test_mask_validation tests.test_mask_alpha tests.test_config_models -v` — PASS, 28 tests.
- `uv run ruff check src/O4_Mask_Validation.py src/O4_Mask_Utils.py tests/test_mask_validation.py` — PASS, `All checks passed!`.
- `uv run ty check src/O4_Mask_Validation.py src/O4_Mask_Utils.py` — PASS, `All checks passed!`.
- `uv run python -m unittest discover -s tests` — PASS, 442 tests (fresh final run).
- `git diff --check` — PASS before commit and amend.

## Files changed

- `src/O4_Mask_Validation.py`
- `src/O4_Mask_Utils.py`
- `tests/test_mask_validation.py`

## Self-review

The sand preflight is after the mesh prerequisite and before both destination
creation and `delete_old_masks_in_tile()`. `blur_mask()` validates the actual
input shape before kernel construction, retains the existing hat-kernel math,
and only affects XP12 sand-mask flow. Independent review found and this change
fixed the malformed-shape exception-type gap; no remaining findings.

## Concerns

None. Test output includes expected fixture diagnostics from existing CLI and
configuration tests, while unittest completed successfully.

## Independent-review follow-up

Addressed every Important review finding in a follow-up commit:

- `_is_finite_real()` now catches `OverflowError` from conversion of an
  oversized numeric input, preserving the documented user-readable `ValueError`
  for both width and pixel scale.
- Pixel-scale validation now has deterministic coverage for zero, negative,
  boolean, non-numeric, `NaN`, and both infinities.
- Overflow regressions cover a huge integer width and a huge integer pixel
  scale, asserting `ValueError` rather than an uncaught `OverflowError`.

### Follow-up TDD evidence

RED command:

```powershell
uv run python -m unittest tests.test_mask_validation -v
```

Result: `test_rejects_width_and_pixel_scale_overflow` failed before the fix
with `OverflowError: int too large to convert to float` at the width conversion.

GREEN command:

```powershell
uv run python -m unittest tests.test_mask_validation -v
```

Result: 6 tests passed.

### Follow-up verification

```powershell
uv run python -m unittest tests.test_mask_validation tests.test_mask_alpha tests.test_config_models -v
uv run ruff check src/O4_Mask_Validation.py tests/test_mask_validation.py
uv run ty check src/O4_Mask_Validation.py
```

Results: 30 tests passed; Ruff and ty both reported `All checks passed!`.
