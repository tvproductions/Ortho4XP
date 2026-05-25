# Logarithmic Alpha Mask Design

## Problem

TODO-015 calls for logarithmic BC3 coastline blending, but its current wording
is too loose to implement directly. It mentions "distance-field paths" even
though the recent bathymetry work intentionally stopped treating mask-derived
distance data as a bathymetry input.

The implementation should therefore improve texture alpha masks only. It should
not reintroduce bathymetry behavior through `distance_masks_too`, and it should
not rewrite all mask modes without visual evidence.

## Current Context

Mask generation lives in `src/O4_Mask_Utils.py`.

`build_masks()` creates a water pre-mask, optionally merges DEM and custom
extent masks, then calls `blur_mask()` to build the grayscale alpha mask saved
as the legacy mask PNG. When `tile.distance_masks_too` is enabled, it also
writes a separate distance mask file after the alpha mask is saved.

`blur_mask()` supports three modes:

- `sand`, which applies a hat-kernel blur.
- `rocks`, which applies a nonlinear transform after Gaussian blur.
- `3steps`, which builds a shore-to-water alpha transition in three phases.

The clearest linear alpha path is the final `3steps` phase. It currently fades
from `sea_level` to transparent water with:

```python
value = sea_level * (1 - transition_profile((i + 1) / stepsout, "linear"))
```

That is the correct initial target because it is a texture-alpha transition,
is deterministic, and does not overlap with the bathymetry boundary.

## Goals

- Replace the final linear `3steps` sea fade with a tested progressive
  logarithmic alpha curve.
- Preserve the existing mask topology, file names, image modes, and byte-range
  alpha output.
- Keep BC3/DXT5 suitability by continuing to produce clean `uint8` grayscale
  alpha masks in the `0..255` range.
- Add deterministic `unittest` coverage for the alpha mapping helper.
- Keep `distance_masks_too` unchanged unless a current non-bathymetry consumer
  requires a separate follow-up.

## Non-Goals

- Do not change bathymetry input or DSF bathymetry raster behavior.
- Do not use distance masks as bathymetry evidence.
- Do not rewrite `sand` or `rocks` mask behavior in this task.
- Do not introduce visual tuning dependencies, external imagery fixtures, or
  full tile builds into tests.
- Do not change texture compressor selection in this task.

## Design

Add a small pure helper in `src/O4_Mask_Alpha.py` and use it from
`src/O4_Mask_Utils.py`:

```python
def progressive_log_alpha_ratio(ratio):
    ...
```

The helper accepts normalized transition progress and returns normalized alpha
reduction:

- `0.0` means no reduction.
- `1.0` means fully reduced to transparent water.
- Inputs below `0.0` clamp to `0.0`.
- Inputs above `1.0` clamp to `1.0`.
- Outputs are monotonic and stay in `0.0..1.0`.
- Endpoints are exact: `0.0 -> 0.0` and `1.0 -> 1.0`.

The curve should preserve more alpha near the coast and then taper more
progressively toward open water. The alpha-reduction curve should therefore be
slower than linear in the first half of the transition and exact at both
endpoints. A practical formula is:

```python
1 - (
    math.log1p(curve_strength * (1 - ratio))
    / math.log1p(curve_strength)
)
```

used as the alpha-reduction ratio, with a fixed positive strength chosen in the
helper. With `curve_strength = 9`, the midpoint reduction is about `0.26`,
which means alpha remains higher than the previous linear fade near the coast
and then drops more quickly near open water. The contract is the important
surface: endpoints, monotonicity, bounded output, and a non-linear midpoint
below `0.5`.

Update only the final `3steps` fade:

```python
value = sea_level * (1 - progressive_log_alpha_ratio((i + 1) / stepsout))
```

The implementation should preserve existing zero-step transition behavior. When
a configured width produces `stepsin == 0` or `stepsout == 0`, Python's
`range(0)` skips the loop body, so the division inside the loop is not
evaluated. Adding explicit guard branches would only increase complexity in an
already-large legacy function.

## Data Flow

The data flow remains:

1. `build_masks()` builds or combines pre-mask sources.
2. `blur_mask()` maps the pre-mask into a grayscale alpha image.
3. The legacy mask PNG is saved for the texture pipeline.
4. Optional `distance_masks_too` output is generated separately and unchanged.

No new files, schemas, or configuration values are needed.

## Error Handling

The helper should be total for numeric inputs and clamp out-of-range values.
It should not raise for ordinary ratio drift caused by float arithmetic.

`blur_mask()` already avoids zero-step division by keeping the division inside
the skipped loop body. This task should not add extra branching for that case.

## Testing

Add focused `unittest` coverage, likely in a new `tests/test_mask_alpha.py`
file or an existing mask-related test file if one exists by implementation
time.

Tests should cover:

- Exact endpoint behavior for `progressive_log_alpha_ratio()`.
- Clamping below `0.0` and above `1.0`.
- Monotonic output over representative sample ratios.
- A midpoint assertion proving the curve is not linear.
- A source-level `3steps` regression showing the final fade uses the
  helper-derived values without full tile setup.

The tests should import real production code and avoid network, X-Plane,
external compressors, imagery providers, and full tile builds.

## Acceptance Criteria

- `src/O4_Mask_Alpha.py` exposes a tested progressive logarithmic alpha helper.
- `src/O4_Mask_Utils.py` uses that helper for the final `3steps` sea fade.
- The final `3steps` sea fade uses that helper instead of the linear profile.
- Existing `distance_masks_too` behavior is not changed.
- Mask alpha output remains `uint8` grayscale data bounded to `0..255`.
- Deterministic `unittest` coverage verifies the curve contract.
- The relevant focused tests and repository quality checks pass before closing
  TODO-015.
