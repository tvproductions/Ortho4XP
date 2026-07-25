# TODO-041-2 XP12 Coastal Mask and Texture Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one early XP12 coastal-artifact decision govern DSF coordinate layout, provider-extent precedence, mask ownership, DDS cleanup, and resolved-provider texture references.

**Architecture:** A pure coastal-policy module classifies each water texture requirement before DSF pool allocation, while a pure mask-validation module protects sand convolution. The existing `TextureSource` pipeline preserves requested and resolved identities, typed cleanup keeps imprinted masks until encoder success, and a post-conversion finalizer rewrites `.ter` texture references before the temporary DSF is activated.

**Tech Stack:** Python 3.13, standard-library `dataclasses`, `enum`, `pathlib`, and `unittest`; Pillow and NumPy already present in the project; existing Ruff, ty, complexity, and repository quality tooling.

## Global Constraints

- The active Ortho4XP repository remains strictly X-Plane 12 only.
- Do not restore `XP11+bathy` behavior or add an XP11 compatibility branch.
- Do not import the sister project's `O4_Sea_Texture` or `O4_Coastal_Manager`.
- Do not add a JPG-patch generator or a second sea-texture architecture.
- Use Python 3.13.x through `uv`; add no runtime dependency.
- Use standard-library `unittest` only.
- Tests require no network, X-Plane installation, imagery provider, DDS encoder, or GDAL executable.
- Compute mask disposition before `is_overlay`, DSF pool, or vertex-coordinate selection.
- A `BORDER_TEX` mask is a retained scenery resource and is never conversion cleanup.
- An imprinted mask is removed only after a confirmed successful DDS encode.
- Explicit provider extents take precedence over inferred coastal fill in both mask modes.
- Provider failover may not change the explicit-versus-global extent class selected during DSF planning.
- Generated DDS and provider-derived patch-style names use the resolved
  `TextureSource` provider, never `tile.default_website`.
- Existing scenery is not activated when required conversion or terrain-reference finalization fails.

---

## File Map

- Create `src/O4_Coastal_Artifact_Policy.py`: pure extent classification, coastal dispositions, and water-coordinate semantics.
- Create `src/O4_Mask_Validation.py`: pure sand width, shape, and kernel validation.
- Create `src/O4_Texture_Artifact_Finalizer.py`: validate conversion resolutions and atomically rewrite `.ter` DDS references.
- Modify `src/O4_DSF_Utils.py`: decide coastal disposition before terrain/pool creation, validate external masks, and restrict land decals.
- Modify `src/O4_Mask_Utils.py`: validate sand configuration before deletion and convolution.
- Modify `src/O4_Imagery_Utils.py`: expose provider-extent classification, preserve mask inputs, and construct typed DDS cleanup.
- Modify `src/O4_Texture_Models.py`: add typed DDS cleanup and requested/resolved conversion metadata.
- Modify `src/O4_Texture_Conversion_Utils.py`: split always-cleaned temporaries from success-only mask cleanup.
- Modify `src/O4_Texture_Source.py`: preserve stable requested attributes alongside resolved source attributes.
- Modify `src/O4_Texture_Download_Scheduler.py`: carry requested and active attributes through retries.
- Modify `src/O4_Texture_Download_Failover.py`: select only extent-compatible replacement providers.
- Modify `src/O4_Texture_Conversion_Scheduler.py`: expose all conversion results in batch output.
- Modify `src/O4_Texture_Conversion_Runner.py`: retain successful results for finalization.
- Modify `src/O4_Tile_Texture_Conversion.py`: validate conversion completion and run terrain-reference finalization.
- Modify `src/O4_Tile_Utils.py`: finalize texture references before `.dsf.tmp` activation.
- Create `tests/test_coastal_artifact_policy.py`: pure disposition, extent, and coordinate-contract tests.
- Create `tests/test_dsf_coastal_artifacts.py`: generated `.ter`, missing-resource, and decal tests.
- Create `tests/test_mask_validation.py`: sand width, shape, and boundary tests.
- Create `tests/test_texture_mask_lifecycle.py`: success, returned failure, exception, and external-mask retention tests.
- Create `tests/test_texture_artifact_finalizer.py`: resolved naming, conflicting mapping, rewrite, and failure tests.
- Modify `tests/test_provider_failover_scheduler.py`: requested/resolved identity and extent-compatible failover coverage.
- Modify `tests/test_texture_source.py`: requested identity and resolved output naming.
- Modify `tests/test_texture_conversion_scheduler.py`: successful-result aggregation.
- Modify `tests/test_tile_texture_conversion.py`: finalization failure prevents activation.
- Modify `tests/test_dds_quality_conversion.py`: typed cleanup ordering.
- Modify `tests/test_imagery_convert_color_normalization.py`: mask retention and resolved DDS naming.
- Modify `TODO.md`: record completion evidence without adding XP11 or sister-subsystem requirements.

### Task 1: Pure Coastal Artifact and Extent Policy

**Files:**
- Create: `src/O4_Coastal_Artifact_Policy.py`
- Create: `tests/test_coastal_artifact_policy.py`

**Interfaces:**
- Produces: `CoastalMaskDisposition`, `CoastalMaskDecision`,
  `provider_uses_explicit_extent()`, `decide_coastal_mask()`, and
  `water_texture_coordinates()`.
- `decide_coastal_mask()` consumes only primitive decision inputs; it performs no
  filesystem access.
- `water_texture_coordinates()` returns the exact four post-normal coordinates
  required by the selected custom-water terrain.

- [ ] **Step 1: Write failing policy tests**

Create `tests/test_coastal_artifact_policy.py`:

```python
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Coastal_Artifact_Policy as CAP


class CoastalArtifactPolicyTests(unittest.TestCase):
    def test_missing_ocean_mask_selects_native_water_before_pool_selection(self):
        decision = CAP.decide_coastal_mask(
            tri_type=2,
            imprint_masks_to_dds=False,
            mask_file_name=None,
            mask_available=False,
            explicit_provider_extent=False,
        )
        self.assertEqual(
            decision.disposition,
            CAP.CoastalMaskDisposition.NATIVE_WATER,
        )
        self.assertFalse(decision.creates_custom_terrain)
        self.assertFalse(decision.is_overlay)

    def test_external_mask_is_retained_border_resource(self):
        decision = CAP.decide_coastal_mask(
            tri_type=2,
            imprint_masks_to_dds=False,
            mask_file_name="48_32_ZL16.png",
            mask_available=True,
            explicit_provider_extent=False,
        )
        self.assertEqual(
            decision.disposition,
            CAP.CoastalMaskDisposition.EXTERNAL_BORDER,
        )
        self.assertTrue(decision.creates_custom_terrain)
        self.assertTrue(decision.is_overlay)
        self.assertFalse(decision.cleanup_after_conversion)

    def test_imprinted_mask_is_success_only_conversion_input(self):
        decision = CAP.decide_coastal_mask(
            tri_type=2,
            imprint_masks_to_dds=True,
            mask_file_name="48_32_ZL16.png",
            mask_available=True,
            explicit_provider_extent=False,
        )
        self.assertEqual(
            decision.disposition,
            CAP.CoastalMaskDisposition.IMPRINTED_ALPHA,
        )
        self.assertTrue(decision.creates_custom_terrain)
        self.assertFalse(decision.is_overlay)
        self.assertTrue(decision.cleanup_after_conversion)

    def test_explicit_extent_suppresses_inferred_mask_in_both_modes(self):
        for imprint in (False, True):
            with self.subTest(imprint=imprint):
                decision = CAP.decide_coastal_mask(
                    tri_type=2,
                    imprint_masks_to_dds=imprint,
                    mask_file_name="48_32_ZL16.png",
                    mask_available=True,
                    explicit_provider_extent=True,
                )
                self.assertEqual(
                    decision.disposition,
                    CAP.CoastalMaskDisposition.NATIVE_WATER,
                )

    def test_provider_extent_classifier_handles_simple_and_combined_providers(self):
        providers = {
            "BI": {"extent": "global"},
            "LOCAL": {"extent": "county"},
        }
        combined = {
            "COMB": [
                {"layer_code": "BI", "extent_code": "global"},
                {"layer_code": "LOCAL", "extent_code": "!county"},
            ]
        }
        self.assertFalse(
            CAP.provider_uses_explicit_extent("BI", providers, combined)
        )
        self.assertTrue(
            CAP.provider_uses_explicit_extent("LOCAL", providers, combined)
        )
        self.assertTrue(
            CAP.provider_uses_explicit_extent("COMB", providers, combined)
        )

    def test_coordinate_contract_distinguishes_border_and_imprinted_water(self):
        external = CAP.CoastalMaskDecision.external_border("mask.png")
        imprinted = CAP.CoastalMaskDecision.imprinted_alpha("mask.png")
        self.assertEqual(
            CAP.water_texture_coordinates(external, 0.2, 0.3, 1.0, 0.4),
            (0.2, 0.3, 0.2, 0.3),
        )
        self.assertEqual(
            CAP.water_texture_coordinates(imprinted, 0.2, 0.3, 1.0, 0.4),
            (1.0, 0.4, 0.2, 0.3),
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the policy tests and verify the missing module failure**

Run:

```powershell
uv run python -m unittest tests.test_coastal_artifact_policy -v
```

Expected: `ModuleNotFoundError: No module named 'O4_Coastal_Artifact_Policy'`.

- [ ] **Step 3: Implement the pure policy**

Create `src/O4_Coastal_Artifact_Policy.py`:

```python
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CoastalMaskDisposition(StrEnum):
    NATIVE_WATER = "native_water"
    EXTERNAL_BORDER = "external_border"
    IMPRINTED_ALPHA = "imprinted_alpha"
    UNMASKED_LAND = "unmasked_land"


@dataclass(frozen=True)
class CoastalMaskDecision:
    disposition: CoastalMaskDisposition
    mask_file_name: str | None = None
    reason: str = ""

    @classmethod
    def external_border(cls, mask_file_name: str):
        return cls(CoastalMaskDisposition.EXTERNAL_BORDER, mask_file_name)

    @classmethod
    def imprinted_alpha(cls, mask_file_name: str):
        return cls(CoastalMaskDisposition.IMPRINTED_ALPHA, mask_file_name)

    @property
    def creates_custom_terrain(self) -> bool:
        return self.disposition in {
            CoastalMaskDisposition.EXTERNAL_BORDER,
            CoastalMaskDisposition.IMPRINTED_ALPHA,
        }

    @property
    def is_overlay(self) -> bool:
        return self.disposition == CoastalMaskDisposition.EXTERNAL_BORDER

    @property
    def cleanup_after_conversion(self) -> bool:
        return self.disposition == CoastalMaskDisposition.IMPRINTED_ALPHA


def provider_uses_explicit_extent(
    provider_code: str,
    providers: dict[str, dict[str, Any]],
    combined_providers: dict[str, list[dict[str, Any]]],
) -> bool:
    layers = combined_providers.get(provider_code)
    if layers is not None:
        return any(
            _is_explicit_extent(layer.get("extent_code", "global"))
            for layer in layers
        )
    return _is_explicit_extent(providers.get(provider_code, {}).get("extent", "global"))


def _is_explicit_extent(extent_code: object) -> bool:
    normalized = str(extent_code or "global").removeprefix("!")
    return normalized != "global"


def decide_coastal_mask(
    *,
    tri_type: int,
    imprint_masks_to_dds: bool,
    mask_file_name: str | None,
    mask_available: bool,
    explicit_provider_extent: bool,
) -> CoastalMaskDecision:
    if tri_type not in (1, 2):
        return CoastalMaskDecision(CoastalMaskDisposition.UNMASKED_LAND)
    if explicit_provider_extent:
        return CoastalMaskDecision(
            CoastalMaskDisposition.NATIVE_WATER,
            reason="explicit provider extent",
        )
    if not mask_available:
        return CoastalMaskDecision(
            CoastalMaskDisposition.NATIVE_WATER,
            reason="coastal mask unavailable",
        )
    if not mask_file_name:
        raise ValueError("available coastal mask requires a file name")
    if imprint_masks_to_dds:
        return CoastalMaskDecision.imprinted_alpha(mask_file_name)
    return CoastalMaskDecision.external_border(mask_file_name)


def water_texture_coordinates(
    decision: CoastalMaskDecision,
    s: float,
    t: float,
    ratio_fetch: float,
    ratio_bathy: float,
) -> tuple[float, float, float, float]:
    if decision.disposition == CoastalMaskDisposition.EXTERNAL_BORDER:
        return s, t, s, t
    if decision.disposition == CoastalMaskDisposition.IMPRINTED_ALPHA:
        return ratio_fetch, ratio_bathy, s, t
    raise ValueError(f"{decision.disposition} has no custom water coordinates")
```

- [ ] **Step 4: Run focused tests, Ruff, and ty**

Run:

```powershell
uv run python -m unittest tests.test_coastal_artifact_policy -v
uv run ruff check src/O4_Coastal_Artifact_Policy.py tests/test_coastal_artifact_policy.py
uv run ty check src/O4_Coastal_Artifact_Policy.py
```

Expected: all six tests pass; Ruff and ty exit `0`.

- [ ] **Step 5: Commit the policy contract**

```powershell
git add src/O4_Coastal_Artifact_Policy.py tests/test_coastal_artifact_policy.py
git commit -m "feat: add XP12 coastal artifact policy"
```

### Task 2: Early DSF Decision, Resource Validation, and Land-Only Decals

**Files:**
- Modify: `src/O4_DSF_Utils.py:267-355`
- Modify: `src/O4_DSF_Utils.py:580-760`
- Create: `tests/test_dsf_coastal_artifacts.py`
- Modify: `tests/test_coastal_artifact_policy.py`

**Interfaces:**
- Consumes: Task 1 `CoastalMaskDecision`, `CoastalMaskDisposition`,
  `provider_uses_explicit_extent()`, `decide_coastal_mask()`, and
  `water_texture_coordinates()`.
- Produces: `O4_DSF_Utils.provider_uses_explicit_extent()` as the production
  resolver and a `coastal_decision` argument on `create_terrain_file()`.
- Invariant: `create_terrain_file()` validates an external resource but never
  changes the already-selected disposition.

- [ ] **Step 1: Add failing generated-terrain tests**

Create `tests/test_dsf_coastal_artifacts.py` with a temporary tile fixture and
tests for existing/missing external masks plus land/ocean decals:

```python
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Coastal_Artifact_Policy as CAP
import O4_DSF_Utils as DSF


class DsfCoastalArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        build_dir = Path(self.temp_dir.name)
        (build_dir / "textures").mkdir()
        self.tile = SimpleNamespace(
            build_dir=str(build_dir),
            mask_zl=14,
            imprint_masks_to_dds=False,
            use_decal_on_terrain=True,
            terrain_casts_shadows=True,
        )

    def _terrain_text(self, tri_type, decision=None):
        with mock.patch.object(
            DSF.GEO,
            "gtile_to_wgs84",
            return_value=(45.0, -90.0),
        ), mock.patch.object(
            DSF.GEO,
            "webmercator_pixel_size",
            return_value=2.0,
        ):
            name = DSF.create_terrain_file(
                self.tile,
                "48_32_BI16.dds",
                32,
                48,
                16,
                "BI",
                tri_type,
                bool(decision and decision.is_overlay),
                coastal_decision=decision,
            )
        return (Path(self.tile.build_dir) / "terrain" / name).read_text()

    def test_existing_external_mask_emits_border_reference(self):
        mask_name = "48_32_ZL16.png"
        (Path(self.tile.build_dir) / "textures" / mask_name).write_bytes(b"mask")
        text = self._terrain_text(
            2,
            CAP.CoastalMaskDecision.external_border(mask_name),
        )
        self.assertIn(f"BORDER_TEX ../textures/{mask_name}\n", text)
        self.assertNotIn("WATER_COLOR_MASK\n", text)

    def test_disappeared_external_mask_fails_instead_of_changing_directive(self):
        with self.assertRaises(FileNotFoundError):
            self._terrain_text(
                2,
                CAP.CoastalMaskDecision.external_border("missing.png"),
            )

    def test_land_decal_is_never_emitted_for_ocean(self):
        ocean = self._terrain_text(
            2,
            CAP.CoastalMaskDecision.imprinted_alpha("mask.png"),
        )
        land = self._terrain_text(0)
        self.assertNotIn("DECAL_LIB", ocean)
        self.assertIn("DECAL_LIB", land)


if __name__ == "__main__":
    unittest.main()
```

Extend `tests/test_coastal_artifact_policy.py` with a test that a missing mask
decision cannot produce custom water coordinates:

```python
    def test_native_water_has_no_custom_water_coordinate_contract(self):
        decision = CAP.decide_coastal_mask(
            tri_type=2,
            imprint_masks_to_dds=False,
            mask_file_name=None,
            mask_available=False,
            explicit_provider_extent=False,
        )
        with self.assertRaises(ValueError):
            CAP.water_texture_coordinates(decision, 0.2, 0.3, 1.0, 0.4)
```

- [ ] **Step 2: Run tests and verify interface failures**

Run:

```powershell
uv run python -m unittest tests.test_dsf_coastal_artifacts tests.test_coastal_artifact_policy -v
```

Expected: failures show that `create_terrain_file()` does not accept
`coastal_decision`, does not validate the external file, and still emits an
ocean decal.

- [ ] **Step 3: Integrate the decision before custom terrain allocation**

In `src/O4_DSF_Utils.py`, import the policy:

```python
import O4_Coastal_Artifact_Policy as CAP
```

Add a lazy extent resolver so import-time cycles are not expanded:

```python
def provider_uses_explicit_extent(provider_code):
    import O4_Imagery_Utils as IMG

    return CAP.provider_uses_explicit_extent(
        provider_code,
        IMG.providers_dict,
        IMG.local_combined_providers_dict,
    )
```

In the first potentially-masked-water loop, replace the implicit
`needs_new_terrain` branch with:

```python
mask_name = FNAMES.mask_file(*texture_attributes)
explicit_extent = provider_uses_explicit_extent(texture_attributes[3])
mask_im = (
    False
    if explicit_extent
    else MASK.needs_mask(tile, *texture_attributes)
)
coastal_decision = CAP.decide_coastal_mask(
    tri_type=tri_type,
    imprint_masks_to_dds=tile.imprint_masks_to_dds,
    mask_file_name=mask_name if mask_im else None,
    mask_available=bool(mask_im),
    explicit_provider_extent=explicit_extent,
)
coastal_decisions[terrain_attributes] = coastal_decision
if not coastal_decision.creates_custom_terrain:
    skipped_terrains_for_masking.add(terrain_attributes)
    terrain_idx = 0
else:
    needs_new_terrain = True
    is_overlay = coastal_decision.is_overlay
```

Initialize `coastal_decisions = {}` beside `dico_terrains`, reuse the stored
decision for repeated terrain attributes, and remove the old eager deletion of
`FNAMES.mask_file(...)`. Save the mask only for a decision that creates custom
terrain. Pass `coastal_decision` into `create_terrain_file()`.

Replace the first-loop inline coordinate tuple with:

```python
coords = CAP.water_texture_coordinates(
    coastal_decision,
    s,
    t,
    ratio_fetch,
    ratio_bathy,
)
dsf_pools[idx_dsfpool].extend(
    int(round(value * 65535)) for value in coords
)
```

Leave the second-loop constant-transparency inland-water behavior unchanged.

- [ ] **Step 4: Make `.ter` writing assert the decision and restrict decals**

Extend `create_terrain_file()` with keyword-only
`coastal_decision: CAP.CoastalMaskDecision | None = None`. Before opening the
terrain file, validate an external mask:

```python
if (
    coastal_decision is not None
    and coastal_decision.disposition
    == CAP.CoastalMaskDisposition.EXTERNAL_BORDER
):
    mask_path = os.path.join(
        tile.build_dir,
        "textures",
        coastal_decision.mask_file_name,
    )
    if not os.path.isfile(mask_path):
        raise FileNotFoundError(f"Missing BORDER_TEX mask: {mask_path}")
```

Replace the ocean overlay branch with:

```python
elif (
    coastal_decision is not None
    and coastal_decision.disposition
    == CAP.CoastalMaskDisposition.EXTERNAL_BORDER
):
    f.write(
        "LOAD_CENTER_BORDER "
        f"{lat_med:.5f} {lon_med:.5f} {texture_approx_size} "
        f"{4096 // 2 ** (zoomlevel - tile.mask_zl)}\n"
    )
    f.write(
        "BORDER_TEX ../textures/"
        + coastal_decision.mask_file_name
        + "\n"
    )
```

Do not add a late `WATER_COLOR_MASK` fallback. Change the decal predicate to:

```python
if tri_type == 0 and tile.use_decal_on_terrain:
    f.write("DECAL_LIB lib/g10/decals/maquify_2_green_key.dcl\n")
```

- [ ] **Step 5: Run DSF tests and relevant regressions**

Run:

```powershell
uv run python -m unittest tests.test_dsf_coastal_artifacts tests.test_coastal_artifact_policy tests.test_bathymetry_gate -v
uv run ruff check src/O4_DSF_Utils.py tests/test_dsf_coastal_artifacts.py tests/test_coastal_artifact_policy.py
uv run ty check src/O4_DSF_Utils.py src/O4_Coastal_Artifact_Policy.py
```

Expected: focused tests pass; existing XP12 bathymetry-gate tests pass; Ruff and
ty exit `0`.

- [ ] **Step 6: Commit early DSF policy integration**

```powershell
git add src/O4_DSF_Utils.py tests/test_dsf_coastal_artifacts.py tests/test_coastal_artifact_policy.py
git commit -m "fix: select coastal artifacts before DSF layout"
```

### Task 3: Sand-Mask Width and Shape Validation

**Files:**
- Create: `src/O4_Mask_Validation.py`
- Modify: `src/O4_Mask_Utils.py:75-130`
- Modify: `src/O4_Mask_Utils.py:660-690`
- Create: `tests/test_mask_validation.py`

**Interfaces:**
- Produces: `SandMaskGeometry` and `validate_sand_mask()`.
- `validate_sand_mask()` accepts meter width, meter-per-pixel scale, and actual
  image shape; it returns integer pixel width and kernel size or raises
  `ValueError` with a user-readable message.

- [ ] **Step 1: Write failing validation tests**

Create `tests/test_mask_validation.py`:

```python
import math
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Mask_Validation as MV


class SandMaskValidationTests(unittest.TestCase):
    def test_zero_and_valid_widths_produce_safe_geometry(self):
        self.assertEqual(
            MV.validate_sand_mask(0, 2.0, (6144, 6144)),
            MV.SandMaskGeometry(0, 0),
        )
        self.assertEqual(
            MV.validate_sand_mask(100, 2.0, (6144, 6144)),
            MV.SandMaskGeometry(50, 99),
        )

    def test_rejects_non_scalar_non_finite_and_negative_widths(self):
        for width in ([10, 20, 30], "100", math.inf, math.nan, -1, True):
            with self.subTest(width=width):
                with self.assertRaises(ValueError):
                    MV.validate_sand_mask(width, 2.0, (6144, 6144))

    def test_rejects_invalid_image_shapes(self):
        for shape in ((), (6144,), (0, 6144), (2, 3, 4)):
            with self.subTest(shape=shape):
                with self.assertRaises(ValueError):
                    MV.validate_sand_mask(100, 2.0, shape)

    def test_rejects_kernel_larger_than_working_image(self):
        with self.assertRaisesRegex(ValueError, "kernel"):
            MV.validate_sand_mask(7000, 2.0, (6144, 6144))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify the missing module failure**

Run:

```powershell
uv run python -m unittest tests.test_mask_validation -v
```

Expected: `ModuleNotFoundError: No module named 'O4_Mask_Validation'`.

- [ ] **Step 3: Implement pure sand geometry validation**

Create `src/O4_Mask_Validation.py`:

```python
import math
from dataclasses import dataclass
from numbers import Real


@dataclass(frozen=True)
class SandMaskGeometry:
    width_pixels: int
    kernel_size: int


def validate_sand_mask(width_meters, pixel_size, image_shape):
    if (
        isinstance(width_meters, bool)
        or not isinstance(width_meters, Real)
        or not math.isfinite(float(width_meters))
        or width_meters < 0
    ):
        raise ValueError("sand masks_width must be one finite non-negative number")
    if (
        isinstance(pixel_size, bool)
        or not isinstance(pixel_size, Real)
        or not math.isfinite(float(pixel_size))
        or pixel_size <= 0
    ):
        raise ValueError("sand mask pixel size must be finite and positive")
    if len(image_shape) != 2 or any(
        isinstance(size, bool) or not isinstance(size, int) or size <= 0
        for size in image_shape
    ):
        raise ValueError("sand mask input must be a non-empty 2D array")
    width_pixels = int(width_meters / pixel_size)
    kernel_size = 0 if width_pixels == 0 else 2 * width_pixels - 1
    if kernel_size > min(image_shape):
        raise ValueError(
            f"sand mask kernel {kernel_size} exceeds image shape {image_shape}"
        )
    return SandMaskGeometry(width_pixels, kernel_size)
```

- [ ] **Step 4: Validate before deleting old masks and before convolution**

Import `O4_Mask_Validation as MV` in `src/O4_Mask_Utils.py`. In
`build_masks()`, before destination creation or `delete_old_masks_in_tile()`,
add:

```python
if tile.masking_mode == "sand":
    pixel_size = GEO.webmercator_pixel_size(tile.lat + 0.5, tile.mask_zl)
    try:
        MV.validate_sand_mask(
            tile.masks_width,
            pixel_size,
            (4096 + 2 * 1024, 4096 + 2 * 1024),
        )
    except ValueError as exc:
        UI.lvprint(0, f"ERROR: Invalid sand mask configuration: {exc}")
        UI.exit_message_and_bottom_line("")
        return 0
```

In the sand branch of `blur_mask()`, replace direct width calculation with:

```python
geometry = MV.validate_sand_mask(tile.masks_width, pxscal, img_array.shape)
blur_width = geometry.width_pixels
```

Keep the existing hat-kernel mathematics unchanged after validation.

- [ ] **Step 5: Run validation, alpha, and config regressions**

Run:

```powershell
uv run python -m unittest tests.test_mask_validation tests.test_mask_alpha tests.test_config_models -v
uv run ruff check src/O4_Mask_Validation.py src/O4_Mask_Utils.py tests/test_mask_validation.py
uv run ty check src/O4_Mask_Validation.py src/O4_Mask_Utils.py
```

Expected: all tests pass; Ruff and ty exit `0`.

- [ ] **Step 6: Commit sand validation**

```powershell
git add src/O4_Mask_Validation.py src/O4_Mask_Utils.py tests/test_mask_validation.py
git commit -m "fix: validate sand mask geometry before use"
```

### Task 4: Typed DDS Cleanup and Success-Only Mask Removal

**Files:**
- Modify: `src/O4_Texture_Models.py:1-70`
- Modify: `src/O4_Texture_Conversion_Utils.py:16-52`
- Modify: `src/O4_Imagery_Utils.py:2299-2518`
- Create: `tests/test_texture_mask_lifecycle.py`
- Modify: `tests/test_dds_quality_conversion.py`
- Modify: `tests/test_imagery_convert_color_normalization.py`

**Interfaces:**
- Produces: `TextureCleanupPlan(always_paths, success_paths)`.
- `convert_dds_texture()` accepts a `TextureCleanupPlan`.
- Imprinted masks appear only in `success_paths`; temporary conversion rasters
  appear only in `always_paths`.

- [ ] **Step 1: Write failing cleanup lifecycle tests**

Create `tests/test_texture_mask_lifecycle.py`:

```python
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Conversion_Utils as TCU
from O4_Texture_Models import TextureCleanupPlan


def encode_result(request, ok):
    return TCU.TEX.TextureEncodeResult(
        request=request,
        ok=ok,
        attempts=1,
        backend_name="test",
        tool_name="test",
        returncode=0 if ok else 7,
        error_summary="" if ok else "failed",
    )


class TextureMaskLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.temp_png = root / "source.png"
        self.mask_png = root / "mask.png"
        self.temp_png.write_bytes(b"temporary")
        self.mask_png.write_bytes(b"mask")
        self.tile = SimpleNamespace(
            build_dir=str(root),
            dds_qa_enabled=False,
            dds_qa_psnr_threshold=0,
        )
        self.cleanup = TextureCleanupPlan(
            always_paths=(str(self.temp_png),),
            success_paths=(str(self.mask_png),),
        )

    def _convert(self, encoder):
        with mock.patch.object(TCU.TEX, "encode_texture", side_effect=encoder):
            return TCU.convert_dds_texture(
                self.tile,
                (32, 48, 16, "BI"),
                (str(self.temp_png), "out.dds", True),
                self.cleanup,
            )

    def test_success_removes_temporary_and_imprinted_mask(self):
        result = self._convert(lambda request: encode_result(request, True))
        self.assertTrue(result.ok)
        self.assertFalse(self.temp_png.exists())
        self.assertFalse(self.mask_png.exists())

    def test_returned_failure_removes_temporary_but_retains_mask(self):
        result = self._convert(lambda request: encode_result(request, False))
        self.assertFalse(result.ok)
        self.assertFalse(self.temp_png.exists())
        self.assertTrue(self.mask_png.exists())

    def test_encoder_exception_removes_temporary_but_retains_mask(self):
        with self.assertRaisesRegex(RuntimeError, "encoder exploded"):
            self._convert(lambda _request: (_ for _ in ()).throw(
                RuntimeError("encoder exploded")
            ))
        self.assertFalse(self.temp_png.exists())
        self.assertTrue(self.mask_png.exists())


if __name__ == "__main__":
    unittest.main()
```

Add an imagery-level test proving `imprint_masks_to_dds=False` never places the
external mask in a cleanup plan:

```python
    def test_external_border_mask_is_not_conversion_cleanup(self):
        tile = self._tile_for_conversion()
        tile.imprint_masks_to_dds = False
        source = TextureSource(
            tile,
            (32, 48, 16, "STREAM"),
            Image.new("RGB", (16, 16), (1, 2, 3)),
        )
        with self._convert_texture_patches("STREAM") as conversion:
            IMG.convert_texture_source(source)
        cleanup_plan = conversion.convert_dds_texture.call_args.args[3]
        self.assertEqual(cleanup_plan.success_paths, ())
```

- [ ] **Step 2: Run lifecycle tests and verify contract failures**

Run:

```powershell
uv run python -m unittest tests.test_texture_mask_lifecycle tests.test_dds_quality_conversion tests.test_imagery_convert_color_normalization -v
```

Expected: import/signature failures because `TextureCleanupPlan` does not exist
and imagery still deletes masks before conversion.

- [ ] **Step 3: Add the typed cleanup model and conversion semantics**

Add to `src/O4_Texture_Models.py`:

```python
@dataclass(frozen=True)
class TextureCleanupPlan:
    always_paths: tuple[str, ...] = ()
    success_paths: tuple[str, ...] = ()
```

Export it through `O4_Texture_Encoder` only if callers already import texture
models through that facade; direct imports from `O4_Texture_Models` are
preferred.

In `src/O4_Texture_Conversion_Utils.py`, add:

```python
from O4_Texture_Models import TextureCleanupPlan


def cleanup_conversion_paths(paths):
    for path in paths:
        _remove_conversion_temp(path)
```

Replace `convert_dds_texture()` with:

```python
def convert_dds_texture(tile, texture_attrs, conversion_input, cleanup_plan):
    request = texture_encode_request(tile, texture_attrs, conversion_input)
    try:
        encode_result = TEX.encode_texture(request)
        DQA.run_enabled_dds_quality_check(tile, encode_result)
        result = TEX.TextureConversionResult.from_encode_result(encode_result)
        if result.ok:
            cleanup_conversion_paths(cleanup_plan.success_paths)
        return result
    finally:
        cleanup_conversion_paths(cleanup_plan.always_paths)
```

Keep `cleanup_conversion_temps()` for GeoTIFF callers; do not route scenery
masks through it.

- [ ] **Step 4: Stop imagery preparation from deleting masks**

In `src/O4_Imagery_Utils.py`, represent a loaded DDS mask with:

```python
@dataclass(frozen=True)
class DdsMaskInput:
    image: Image.Image
    path: str
```

Make `_dds_texture_mask()` return `DdsMaskInput | None`, loading under a context
manager:

```python
def _dds_texture_mask(tile, texture_attrs):
    if not tile.imprint_masks_to_dds:
        return None
    mask_path = _dds_mask_path(tile, texture_attrs)
    if not os.path.exists(mask_path):
        return None
    with Image.open(mask_path) as mask_image:
        return DdsMaskInput(mask_image.convert("L"), mask_path)
```

Remove all calls to `_remove_dds_mask_file()`. Build cleanup plans with full
paths:

```python
cleanup_plan = TextureCleanupPlan(
    always_paths=(file_to_convert,) if erase_tmp_png else (),
    success_paths=(mask_input.path,) if mask_input is not None else (),
)
```

Apply `mask_input.image` before conversion. External-border mode returns no
`DdsMaskInput`, so it cannot enter `success_paths`.

- [ ] **Step 5: Update existing cleanup assertions**

In `tests/test_dds_quality_conversion.py`, construct `TextureCleanupPlan` and
assert QA occurs before `success_paths` cleanup. In
`tests/test_imagery_convert_color_normalization.py`, assert the temporary PNG is
removed on success and the copied mask remains until the mocked encoder result
reports success.

Use semantic assertions on `always_paths` and `success_paths`; do not assert the
old `(erase_tmp_png, png_file_name)` tuple.

- [ ] **Step 6: Run focused conversion tests, Ruff, and ty**

Run:

```powershell
uv run python -m unittest tests.test_texture_mask_lifecycle tests.test_dds_quality_conversion tests.test_imagery_convert_color_normalization tests.test_texture_encoder -v
uv run ruff check src/O4_Texture_Models.py src/O4_Texture_Conversion_Utils.py src/O4_Imagery_Utils.py tests/test_texture_mask_lifecycle.py tests/test_dds_quality_conversion.py tests/test_imagery_convert_color_normalization.py
uv run ty check src/O4_Texture_Models.py src/O4_Texture_Conversion_Utils.py src/O4_Imagery_Utils.py
```

Expected: all focused tests pass; Ruff and ty exit `0`.

- [ ] **Step 7: Commit mask ownership and cleanup**

```powershell
git add src/O4_Texture_Models.py src/O4_Texture_Conversion_Utils.py src/O4_Imagery_Utils.py tests/test_texture_mask_lifecycle.py tests/test_dds_quality_conversion.py tests/test_imagery_convert_color_normalization.py
git commit -m "fix: retain imprinted masks until DDS success"
```

### Task 5: Requested/Resolved Texture Identity and Extent-Compatible Failover

**Files:**
- Modify: `src/O4_Texture_Source.py:1-35`
- Modify: `src/O4_Imagery_Utils.py:600-790`
- Modify: `src/O4_Texture_Download_Scheduler.py:15-150`
- Modify: `src/O4_Texture_Download_Failover.py:9-61`
- Modify: `tests/test_texture_source.py`
- Modify: `tests/test_provider_failover_scheduler.py`
- Modify: `tests/test_provider_failover.py`

**Interfaces:**
- Produces: `TextureSource.requested_attrs`, `TextureSource.terrain_attrs`,
  `TextureSource.with_requested_attrs()`, `TextureSource.output_name()`, and
  `TextureDownloadRequest`.
- A request carries immutable `requested_attrs` and mutable-by-replacement
  `active_attrs`.
- Replacement candidates must match the requested provider's explicit/global
  extent class.

- [ ] **Step 1: Add failing identity and compatibility tests**

In `tests/test_texture_source.py`, add:

```python
    def test_source_preserves_requested_identity_after_provider_resolution(self):
        source = TextureSource(
            object(),
            (32, 48, 16, "Arc"),
            Image.new("RGB", (4, 4)),
        ).with_requested_attrs((32, 48, 16, "BI"))
        self.assertEqual(source.provider_code, "Arc")
        self.assertEqual(source.terrain_attrs, (32, 48, 16, "BI"))
        self.assertEqual(source.output_name(), "48_32_Arc16.dds")
        self.assertEqual(source.output_name("jpg"), "48_32_Arc16.jpg")
```

In `tests/test_provider_failover_scheduler.py`, change the test providers to
include `extent`, add a third incompatible provider, and assert the queued Arc
source retains BI as its terrain identity:

```python
def _providers():
    return {
        "BI": {"code": "BI", "in_GUI": True, "extent": "global"},
        "Arc": {"code": "Arc", "in_GUI": True, "extent": "global"},
        "LOCAL": {"code": "LOCAL", "in_GUI": True, "extent": "county"},
    }


def _assert_arc_conversion(test_case, tile, convert_queue):
    queued_tile, queued_source = convert_queue.get_nowait()
    test_case.assertIs(queued_tile, tile)
    test_case.assertEqual(queued_source.attrs, (1, 2, 16, "Arc"))
    test_case.assertEqual(queued_source.terrain_attrs, (1, 2, 16, "BI"))
```

Add a test where only an extent-incompatible replacement is available and
assert no LOCAL request is attempted.

- [ ] **Step 2: Run tests and verify missing identity failures**

Run:

```powershell
uv run python -m unittest tests.test_texture_source tests.test_provider_failover tests.test_provider_failover_scheduler -v
```

Expected: failures show missing `with_requested_attrs`, `terrain_attrs`, and
extent filtering.

- [ ] **Step 3: Extend `TextureSource` without breaking positional callers**

Append `requested_attrs` to `TextureSource` and add helpers. Route every
provider-derived output extension through the same resolved-identity helper so
DDS and any patch-style filename cannot diverge:

```python
from dataclasses import dataclass, replace

import O4_File_Names as FNAMES


@dataclass(frozen=True)
class TextureSource:
    tile: object
    attrs: TextureAttributes
    image: Image.Image
    cache_path: str | None = None
    wrote_cache: bool = False
    requested_attrs: TextureAttributes | None = None

    @property
    def terrain_attrs(self) -> TextureAttributes:
        return self.requested_attrs or self.attrs

    def with_requested_attrs(self, attrs: TextureAttributes):
        return replace(self, requested_attrs=attrs)

    def output_name(self, file_ext: str = "dds") -> str:
        return FNAMES.dds_file_name_from_attributes(
            *self.attrs,
            file_ext=file_ext,
        )
```

Existing five-positional-argument constructors remain valid.

- [ ] **Step 4: Introduce an immutable download request**

In `src/O4_Texture_Download_Scheduler.py`, add:

```python
@dataclass(frozen=True)
class TextureDownloadRequest:
    requested_attrs: tuple
    active_attrs: tuple

    @classmethod
    def initial(cls, attrs):
        attrs = tuple(attrs)
        return cls(attrs, attrs)

    def with_active_attrs(self, attrs):
        return TextureDownloadRequest(self.requested_attrs, tuple(attrs))
```

Normalize legacy queue tuples to `TextureDownloadRequest.initial()` in
`_run_ready_tasks()`. Make `_download_task()` consume a request and build from
`request.active_attrs`. On successful download, queue:

```python
source = result.source.with_requested_attrs(request.requested_attrs)
runtime.convert_queue.put((runtime.tile, source))
```

Key retry counts by `request.active_attrs`, while retaining
`request.requested_attrs` across retries.

- [ ] **Step 5: Filter failover candidates by extent class**

Expose this wrapper in `src/O4_Imagery_Utils.py`:

```python
def provider_uses_explicit_extent(provider_code):
    return CAP.provider_uses_explicit_extent(
        provider_code,
        providers_dict,
        local_combined_providers_dict,
    )
```

Add `provider_extent_resolver=IMG.provider_uses_explicit_extent` to
`DownloadTextureRuntime`. In `src/O4_Texture_Download_Failover.py`, filter the
inventory before `select_replacement()`:

```python
def _extent_compatible_providers(runtime, request, providers):
    requested_explicit = runtime.provider_extent_resolver(
        request.requested_attrs[3]
    )
    return {
        code: provider
        for code, provider in providers.items()
        if runtime.provider_extent_resolver(code) == requested_explicit
    }
```

Pass the filtered inventory to `select_replacement()`, and return
`request.with_active_attrs((*request.active_attrs[:3], replacement))`.
Failover logging records the failed active provider, replacement provider, and
requested texture coordinates.

- [ ] **Step 6: Run source and failover tests**

Run:

```powershell
uv run python -m unittest tests.test_texture_source tests.test_provider_failover tests.test_provider_failover_scheduler tests.test_texture_async_downloads -v
uv run ruff check src/O4_Texture_Source.py src/O4_Imagery_Utils.py src/O4_Texture_Download_Scheduler.py src/O4_Texture_Download_Failover.py tests/test_texture_source.py tests/test_provider_failover.py tests/test_provider_failover_scheduler.py
uv run ty check src/O4_Texture_Source.py src/O4_Texture_Download_Scheduler.py src/O4_Texture_Download_Failover.py
```

Expected: failover selects Arc, never crosses into LOCAL, queued source is
resolved Arc with requested BI identity, and all commands exit `0`.

- [ ] **Step 7: Commit identity-preserving failover**

```powershell
git add src/O4_Texture_Source.py src/O4_Imagery_Utils.py src/O4_Texture_Download_Scheduler.py src/O4_Texture_Download_Failover.py tests/test_texture_source.py tests/test_provider_failover.py tests/test_provider_failover_scheduler.py tests/test_texture_async_downloads.py
git commit -m "fix: preserve texture identity through provider failover"
```

### Task 6: Resolved DDS Naming and Pre-Activation Terrain Finalization

**Files:**
- Modify: `src/O4_Texture_Models.py:35-70`
- Modify: `src/O4_Imagery_Utils.py:2299-2327`
- Modify: `src/O4_Texture_Conversion_Scheduler.py:54-60`
- Modify: `src/O4_Texture_Conversion_Runner.py:21-55`
- Create: `src/O4_Texture_Artifact_Finalizer.py`
- Modify: `src/O4_Tile_Texture_Conversion.py:27-55`
- Modify: `src/O4_Tile_Utils.py:168-195`
- Create: `tests/test_texture_artifact_finalizer.py`
- Modify: `tests/test_texture_conversion_scheduler.py`
- Modify: `tests/test_tile_texture_conversion.py`
- Modify: `tests/test_imagery_convert_color_normalization.py`

**Interfaces:**
- Produces: optional `requested_attrs` and `resolved_attrs` metadata on
  `TextureConversionResult`, `TextureConversionBatchResult.results`, and
  `finalize_terrain_texture_references()`.
- Canonical DDS output uses `TextureSource.output_name()`; the stable `.ter`
  filename may retain requested identity, but its `BASE_TEX_NOWRAP` line is
  finalized to the resolved DDS before DSF activation.

- [ ] **Step 1: Write failing finalizer tests**

Create `tests/test_texture_artifact_finalizer.py`:

```python
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Texture_Artifact_Finalizer as TAF
from O4_Texture_Models import TextureConversionResult


def resolved_result(requested_provider="BI", resolved_provider="Arc", ok=True):
    return TextureConversionResult(
        ok=ok,
        display_name=f"48_32_{resolved_provider}16.dds",
        provider_code=resolved_provider,
        error_summary="" if ok else "failed",
        requested_attrs=(32, 48, 16, requested_provider),
        resolved_attrs=(32, 48, 16, resolved_provider),
    )


class TextureArtifactFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.terrain = self.root / "terrain"
        self.terrain.mkdir()
        self.tile = SimpleNamespace(build_dir=str(self.root))

    def test_rewrites_requested_reference_to_resolved_dds(self):
        terrain_file = self.terrain / "48_32_BI16_sea.ter"
        terrain_file.write_text(
            "A\n800\nTERRAIN\n\n"
            "BASE_TEX_NOWRAP ../textures/48_32_BI16.dds\n"
        )
        TAF.finalize_terrain_texture_references(
            self.tile,
            (resolved_result(),),
        )
        self.assertIn(
            "BASE_TEX_NOWRAP ../textures/48_32_Arc16.dds\n",
            terrain_file.read_text(),
        )

    def test_rejects_failed_conversion_without_rewriting(self):
        terrain_file = self.terrain / "48_32_BI16.ter"
        original = "BASE_TEX_NOWRAP ../textures/48_32_BI16.dds\n"
        terrain_file.write_text(original)
        with self.assertRaises(TAF.TextureFinalizationError):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result(ok=False),),
            )
        self.assertEqual(terrain_file.read_text(), original)

    def test_rejects_conflicting_resolutions_for_one_requested_texture(self):
        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "conflicting",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (
                    resolved_result(resolved_provider="Arc"),
                    resolved_result(resolved_provider="EOX"),
                ),
            )

    def test_rejects_resolution_with_no_matching_terrain_reference(self):
        with self.assertRaisesRegex(
            TAF.TextureFinalizationError,
            "not referenced",
        ):
            TAF.finalize_terrain_texture_references(
                self.tile,
                (resolved_result(),),
            )


if __name__ == "__main__":
    unittest.main()
```

Add a scheduler test asserting successful results are exposed in
`TextureConversionBatchResult.results`. Add an imagery test asserting a
`TextureSource` resolved to Arc produces `48_32_Arc16.dds` and returns BI/Arc
resolution metadata. The Task 5 source test already establishes that the same
resolved-provider helper produces `48_32_Arc16.jpg` for patch-style naming.

- [ ] **Step 2: Run tests and verify missing finalization contracts**

Run:

```powershell
uv run python -m unittest tests.test_texture_artifact_finalizer tests.test_texture_conversion_scheduler tests.test_imagery_convert_color_normalization tests.test_tile_texture_conversion -v
```

Expected: missing-module and missing-field failures.

- [ ] **Step 3: Add conversion resolution metadata**

Append fields to `TextureConversionResult` in `src/O4_Texture_Models.py` so
existing positional construction remains compatible:

```python
    requested_attrs: tuple[int, int, int, str] | None = None
    resolved_attrs: tuple[int, int, int, str] | None = None

    def with_texture_resolution(self, requested_attrs, resolved_attrs):
        return replace(
            self,
            requested_attrs=tuple(requested_attrs),
            resolved_attrs=tuple(resolved_attrs),
        )
```

Import `replace` from `dataclasses`. In `convert_texture_source()`, derive the
canonical output with `out_file_name = texture_source.output_name()`, then
return:

```python
result = convert_dds_texture(
    tile,
    texture_attrs,
    (file_to_convert, out_file_name, dxt5),
    cleanup_plan,
)
return result.with_texture_resolution(
    texture_source.terrain_attrs,
    texture_source.attrs,
)
```

This is the sole canonical naming path; do not consult
`tile.default_website`.

- [ ] **Step 4: Aggregate all conversion results**

Append `results: tuple = ()` to `TextureConversionBatchResult`. Add
`results: list = field(init=False, default_factory=list)` to
`TextureConversionQueueRunner`, append every completed result before checking
`result.ok`, and pass `tuple(self.results)` into the batch result.

Update positional test constructions only where they need explicit result
metadata; the default keeps older callers valid.

- [ ] **Step 5: Implement transactional validation and per-file atomic rewrite**

Create `src/O4_Texture_Artifact_Finalizer.py`:

```python
import os
from pathlib import Path

import O4_File_Names as FNAMES


class TextureFinalizationError(RuntimeError):
    pass


def finalize_terrain_texture_references(tile, results):
    mappings = _validated_mappings(results)
    if not mappings:
        return 0
    terrain_dir = Path(tile.build_dir) / "terrain"
    terrain_files = sorted(terrain_dir.glob("*.ter"))
    updated_files = {}
    matched = {requested: 0 for requested in mappings}
    for terrain_file in terrain_files:
        original = terrain_file.read_text(encoding="utf-8")
        updated = original
        for requested_name, resolved_name in mappings.items():
            old_line = f"BASE_TEX_NOWRAP ../textures/{requested_name}"
            new_line = f"BASE_TEX_NOWRAP ../textures/{resolved_name}"
            count = updated.count(old_line)
            if count:
                matched[requested_name] += count
                updated = updated.replace(old_line, new_line)
        if updated != original:
            updated_files[terrain_file] = updated
    missing = [name for name, count in matched.items() if count == 0]
    if missing:
        raise TextureFinalizationError(
            "resolved DDS not referenced by terrain: " + ", ".join(missing)
        )
    for terrain_file, updated in updated_files.items():
        temp_path = terrain_file.with_suffix(terrain_file.suffix + ".finalizing")
        temp_path.write_text(updated, encoding="utf-8", newline="\n")
        os.replace(temp_path, terrain_file)
    return len(updated_files)


def _validated_mappings(results):
    mappings = {}
    for result in results:
        if not result.ok:
            raise TextureFinalizationError(
                f"texture conversion failed: {result.display_name}"
            )
        if result.requested_attrs is None or result.resolved_attrs is None:
            continue
        requested_name = FNAMES.dds_file_name_from_attributes(
            *result.requested_attrs
        )
        resolved_name = FNAMES.dds_file_name_from_attributes(
            *result.resolved_attrs
        )
        if requested_name == resolved_name:
            continue
        previous = mappings.setdefault(requested_name, resolved_name)
        if previous != resolved_name:
            raise TextureFinalizationError(
                f"conflicting resolutions for {requested_name}: "
                f"{previous}, {resolved_name}"
            )
    return mappings
```

All mappings are validated and all source contents are prepared before the
first `os.replace`.

- [ ] **Step 6: Finalize before activating the DSF**

In `src/O4_Tile_Texture_Conversion.py`, add:

```python
import O4_Texture_Artifact_Finalizer as TAF


def finalize_texture_conversion(tile, result_holder):
    if "exception" in result_holder:
        return False
    result = result_holder.get("result")
    if result is None or result.interrupted or result.failed:
        return False
    try:
        TAF.finalize_terrain_texture_references(tile, result.results)
    except TAF.TextureFinalizationError as exc:
        UI.vprint(1, "Texture artifact finalization failed:", str(exc))
        UI.vprint(3, exc)
        return False
    return True
```

In `src/O4_Tile_Utils.py`, after conversion thread join and result reporting,
but before `" *Activating DSF file."`, add:

```python
if convert_launched and not TTC.finalize_texture_conversion(
    tile,
    convert_result_holder,
):
    UI.vprint(1, "Tile activation stopped after texture conversion failure.")
    return 0
```

Do not rename `.dsf.tmp` on failure.

- [ ] **Step 7: Run finalizer and scheduler regressions**

Run:

```powershell
uv run python -m unittest tests.test_texture_artifact_finalizer tests.test_texture_conversion_scheduler tests.test_texture_conversion_scheduler_limits tests.test_texture_conversion_scheduler_live tests.test_tile_texture_conversion tests.test_imagery_convert_color_normalization tests.test_provider_failover_scheduler -v
uv run ruff check src/O4_Texture_Models.py src/O4_Imagery_Utils.py src/O4_Texture_Conversion_Scheduler.py src/O4_Texture_Conversion_Runner.py src/O4_Texture_Artifact_Finalizer.py src/O4_Tile_Texture_Conversion.py src/O4_Tile_Utils.py tests/test_texture_artifact_finalizer.py tests/test_texture_conversion_scheduler.py tests/test_tile_texture_conversion.py tests/test_imagery_convert_color_normalization.py
uv run ty check src/O4_Texture_Models.py src/O4_Texture_Conversion_Scheduler.py src/O4_Texture_Conversion_Runner.py src/O4_Texture_Artifact_Finalizer.py src/O4_Tile_Texture_Conversion.py src/O4_Tile_Utils.py
```

Expected: all tests pass; resolved Arc naming reaches `.ter`; conversion or
finalization failure prevents activation; Ruff and ty exit `0`.

- [ ] **Step 8: Commit resolved texture finalization**

```powershell
git add src/O4_Texture_Models.py src/O4_Imagery_Utils.py src/O4_Texture_Conversion_Scheduler.py src/O4_Texture_Conversion_Runner.py src/O4_Texture_Artifact_Finalizer.py src/O4_Tile_Texture_Conversion.py src/O4_Tile_Utils.py tests/test_texture_artifact_finalizer.py tests/test_texture_conversion_scheduler.py tests/test_tile_texture_conversion.py tests/test_imagery_convert_color_normalization.py
git commit -m "fix: finalize resolved DDS references before activation"
```

### Task 7: Cross-Surface Review, Documentation, and Completion Evidence

**Files:**
- Modify: `TODO.md:1208-1232`

**Interfaces:**
- Consumes: all prior task contracts.
- Produces: a coherent completed backlog item, GitHub Issue #39 evidence, and
  full repository verification.

- [ ] **Step 1: Run the complete focused TODO-041-2 suite**

Run:

```powershell
uv run python -m unittest tests.test_coastal_artifact_policy tests.test_dsf_coastal_artifacts tests.test_mask_validation tests.test_texture_mask_lifecycle tests.test_texture_artifact_finalizer tests.test_provider_failover tests.test_provider_failover_scheduler tests.test_texture_source tests.test_texture_conversion_scheduler tests.test_texture_conversion_scheduler_limits tests.test_texture_conversion_scheduler_live tests.test_tile_texture_conversion tests.test_dds_quality_conversion tests.test_imagery_convert_color_normalization tests.test_bathymetry_gate -v
```

Expected: all tests pass with no network or external process execution.

- [ ] **Step 2: Inspect generated terrain semantics**

Run:

```powershell
uv run python -m unittest tests.test_dsf_coastal_artifacts -v
Select-String -Path src/O4_DSF_Utils.py -Pattern 'XP11|XP11.bathy'
Select-String -Path src/O4_DSF_Utils.py -Pattern 'DECAL_LIB|BORDER_TEX|WATER_COLOR_MASK'
```

Expected:

- terrain tests pass;
- no new XP11 branch appears;
- `DECAL_LIB` is guarded by `tri_type == 0`;
- `BORDER_TEX` consumes a validated external decision;
- `WATER_COLOR_MASK` remains on the non-overlay XP12 water path.

- [ ] **Step 3: Format and check every changed Python file**

Run:

```powershell
uv run ruff format src/O4_Coastal_Artifact_Policy.py src/O4_Mask_Validation.py src/O4_Texture_Artifact_Finalizer.py src/O4_DSF_Utils.py src/O4_Mask_Utils.py src/O4_Imagery_Utils.py src/O4_Texture_Models.py src/O4_Texture_Conversion_Utils.py src/O4_Texture_Source.py src/O4_Texture_Download_Scheduler.py src/O4_Texture_Download_Failover.py src/O4_Texture_Conversion_Scheduler.py src/O4_Texture_Conversion_Runner.py src/O4_Tile_Texture_Conversion.py src/O4_Tile_Utils.py tests/test_coastal_artifact_policy.py tests/test_dsf_coastal_artifacts.py tests/test_mask_validation.py tests/test_texture_mask_lifecycle.py tests/test_texture_artifact_finalizer.py tests/test_provider_failover_scheduler.py tests/test_texture_source.py tests/test_texture_conversion_scheduler.py tests/test_tile_texture_conversion.py tests/test_dds_quality_conversion.py tests/test_imagery_convert_color_normalization.py
uv run ruff check Ortho4XP.py src tests
uv run ty check src/O4_Coastal_Artifact_Policy.py src/O4_Mask_Validation.py src/O4_Texture_Artifact_Finalizer.py src/O4_DSF_Utils.py src/O4_Mask_Utils.py src/O4_Imagery_Utils.py src/O4_Texture_Models.py src/O4_Texture_Conversion_Utils.py src/O4_Texture_Source.py src/O4_Texture_Download_Scheduler.py src/O4_Texture_Download_Failover.py src/O4_Texture_Conversion_Scheduler.py src/O4_Texture_Conversion_Runner.py src/O4_Tile_Texture_Conversion.py src/O4_Tile_Utils.py
```

Expected: formatter reports only intentional changes; Ruff and ty exit `0`.

- [ ] **Step 4: Run full repository verification**

Use the repository `quality-check` skill and run:

```powershell
uv run python -m unittest discover -s tests
uv run python .codex/skills/quality-check/scripts/quality_check.py
git diff --check
```

Expected: full unittest discovery passes; the quality script passes unittest,
Ruff, ty, whitespace, complexity, and native validation; `git diff --check`
prints nothing.

- [ ] **Step 5: Perform the required local review**

Review the complete diff against every acceptance criterion:

```powershell
git diff -- src tests TODO.md
git status --short
```

Confirm explicitly:

- missing masks never select overlay coordinates;
- no external mask enters cleanup;
- failed DDS conversion retains its mask;
- extent-incompatible failover is impossible;
- resolved provider names reach final `.ter` references;
- ocean decals are absent;
- invalid sand configuration preserves existing masks;
- no sister sea-texture module or XP11 branch was added.

Fix every defect found, rerun its focused test, and repeat Steps 3 and 4 before
continuing.

- [ ] **Step 6: Update backlog evidence**

Change `TODO-041-2` to `Status: Completed` and append concise evidence naming:

```markdown
Completion evidence:

- Coastal disposition is selected before XP12 DSF pool allocation.
- External masks are retained; imprinted masks are removed only after successful
  DDS encoding.
- Provider extent class is stable across failover and resolved DDS references
  are finalized before tile activation.
- Deterministic `unittest` coverage includes missing-mask, ocean, extent,
  cleanup success/failure, sand validation, and provider-naming cases.
- Full repository quality verification passed; command evidence is recorded in
  GitHub Issue #39.
```

Keep GitHub Issue #39 linked.

- [ ] **Step 7: Commit implementation completion evidence**

```powershell
git add TODO.md src tests
git commit -m "docs: complete TODO-041-2 coastal hardening"
```

- [ ] **Step 8: Comment on and close GitHub Issue #39**

Build the comment from the observed commit list and the required successful
commands from Steps 1 and 4:

```powershell
$completionCommits = (
    git log --format='- `%h` %s' --reverse 9c7d345..HEAD
) -join "`n"
$issueBody = @"
Implemented TODO-041-2 as an XP12-only coastal artifact lifecycle.

Commits:
$completionCommits

Verification:
- The complete focused TODO-041-2 unittest suite passed.
- Full unittest discovery passed.
- The repository quality-check script passed.
- `git diff --check` reported no whitespace errors.

Behavior:
- External BORDER_TEX masks are retained.
- Imprinted masks are removed only after successful DDS encoding.
- Provider extent class is preserved through failover.
- Resolved DDS and patch-style names come from the resolved TextureSource.
- Terrain references are finalized before activation.
- Ocean decals are excluded and sand geometry is validated.
"@
gh issue comment 39 --repo tvproductions/Ortho4XP --body $issueBody
gh issue close 39 --repo tvproductions/Ortho4XP --reason completed
```

Verify:

```powershell
gh issue view 39 --repo tvproductions/Ortho4XP --json number,title,state,stateReason,labels,url
```

Expected: issue state is `CLOSED` with reason `COMPLETED`.

## Execution Checkpoints

After Tasks 2, 4, and 6, stop for a local code-review pass before continuing.
Each checkpoint verifies both the new task and every earlier TODO-041-2 test so
the cross-module lifecycle cannot drift.

Do not activate or package a sample tile as completion evidence unless a local
mesh and licensed imagery are already available. The deterministic contract
tests and generated `.ter` fixtures are the required portable evidence.
