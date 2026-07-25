# Task 7 Closeout Report — TODO-041-2

## Scope and state

- Review range: `63fb1b5..HEAD`; Task 7 completion is recorded by the
  `docs: complete TODO-041-2 coastal hardening` commit.
- Scope remains XP12 coastal artifact lifecycle only.
- No XP11 branch, sister sea-texture subsystem, provider/network call, GDAL or
  encoder process, X-Plane installation, or sample tile was added to evidence.
- GitHub Issue #39 remains open and has not been commented on during Task 7.

## Quality-condition traceability

Every row below was triggered by a reproduced repository gate condition. No
untriggered cleanup is included.

| Files/refactor | Reproduced condition | Targeted correction |
| --- | --- | --- |
| `tests/test_imagery_convert_color_normalization.py` | `ConvertTextureColorNormalizationTests` class size 410 lines, then module MI and `_partial_save_failure` parameter-count regressions | Split scenarios into streaming/cached classes, use a shared base and module helper, and document the tested lifecycle contract. |
| `tests/test_texture_artifact_finalizer.py` | `TextureArtifactFinalizerTests` class size 510 lines; later new-file `radon_mi < 50` and module-size warning | Split reference/validation/transaction classes and document the exact validation and rollback matrix. The remaining module-size result is a nonblocking code-quality warning, recorded below. |
| `tests/test_dds_quality.py` | Three test nloc regressions and module MI regression, including `radon_mi=52.9236` against baseline `53.73` | Move repeated result assertions and the expected enabled request into small helpers; document the decoded-image test boundary. |
| `tests/test_dds_quality_conversion.py` | Test nloc blocks/warnings and module MI regression, ending at `radon_mi=70.4008` against baseline `70.554` | Use a real temporary artifact fixture, extract encode helpers, and document two-phase cleanup and cleanup-order invariants. |
| `tests/test_mask_validation.py` | New nesting-depth 4 finding in overflow coverage | Move repeated invalid-input assertion to a helper and remove nested `subTest` depth. |
| `tests/test_provider_failover_scheduler.py` | New module MI block (`47.7079`) | Document requested/active identity invariants exercised by the scheduler tests. |
| `tests/test_texture_conversion_scheduler.py` | Module MI regression (`46.3195`, baseline `51.0003`) | Document ordered-result and identity-preservation contracts. |
| `tests/test_texture_source.py` | Module MI advise regression (`70.0247`, baseline `73.5706`) | Document requested versus resolved source identity coverage. |
| `tests/test_tile_texture_conversion.py` | Test nloc block (43, baseline 30) and module MI regression | Extract the successful scheduler harness and document activation/shutdown ordering. |
| `src/O4_Coastal_Artifact_Policy.py` | New parameter-count, nesting, and module MI blocks | Decompose native/masked decisions, remove redundant inputs, and isolate external-mask validation. |
| `src/O4_DSF_Utils.py`, `src/O4_DSF_Coastal_Artifacts.py`, `tests/test_dsf_coastal_artifacts.py` | `build_dsf` CC/nloc regressions, `create_terrain_file` parameter count 9 versus 8, and module Halstead/MI regressions | Restore the terrain-writer parameter envelope and extract coastal artifact discovery/caching from the legacy DSF loop. |
| `src/O4_Mask_Validation.py`, `src/O4_Mask_Build_Validation.py`, `src/O4_Mask_Utils.py` | New validation CC/nesting/MI blocks and `build_masks` CC/nesting/nloc regressions | Decompose numeric validation and sand blur; move build preflight out of the legacy build function. |
| `src/O4_Texture_Artifact_Finalizer.py`, `src/O4_Texture_Artifact_Validation.py`, `src/O4_Terrain_Artifact_Transaction.py`, `src/O4_Texture_Finalization_Models.py` | Finalizer CC/nesting/MI blocks | Split immutable models, result validation, and atomic rewrite/rollback transaction while retaining the facade. |
| `src/O4_Imagery_Utils.py`, `src/O4_Texture_Mask_Lifecycle.py` | `convert_texture` CC/nloc, `convert_texture_source` nloc/nesting, and imagery module Halstead/raw-lloc blocks | Extract DDS mask loading and two-phase ownership, and restore compact legacy mask adapters. |
| `src/O4_Texture_Conversion_Utils.py` | Module MI block (`47.2854`, baseline `51.1761`) | Move partial-save and path cleanup ownership to the mask-lifecycle module; retain conversion facade aliases. |
| `src/O4_Texture_Artifact_Activation.py`, `src/O4_Tile_Texture_Conversion.py`, `src/O4_Tile_Utils.py` | Finalization nesting block; `build_tile` CC/nesting/nloc and module MI regressions | Extract activation validation and combine the pre-activation stop boundary. |
| `src/O4_Texture_Resolution.py`, `src/O4_Texture_Conversion_Runner.py` | Runner module MI/nloc regressions, including `radon_mi=52.5602` against baseline `52.9918` | Extract resolution attachment, batch-result construction, and job result coercion. |
| `src/O4_Texture_Conversion_Scheduler.py`, `src/O4_Texture_Models.py`, `src/O4_Texture_Source.py`, `src/O4_Texture_Download_Scheduler.py` | Module MI regressions after adding ordered results and dual identities | Document the immutable contracts and keep requested/active/resolved identities in dedicated models. |
| `src/O4_DDS_Quality.py`, `src/O4_Texture_Color_Normalization.py` | DDS QA function nloc/module MI and color-normalization MI regressions | Extract QA reporting and use the shared partial-save cleanup contract. |

## Verification evidence

| Command | Result |
| --- | --- |
| `uv run python .codex/skills/quality-check/scripts/quality_check.py --complexity-only --scope all` | Initial controlled rerun: 0 BLOCK, 9 WARN, 2 ADVISE; exit 1. |
| Exact 15-module focused command from `task-7-brief.md` | 109 tests passed. |
| `uv run python -m unittest tests.test_dsf_coastal_artifacts -v` | 4 tests passed. |
| XP11/directive `Select-String` checks | XP11 search empty; expected XP12 directives present. |
| Changed-file `ruff format`; repository `ruff check`; changed-file and `tests` ty | Passed; formatter made no changes. |
| `uv run python -m unittest discover -s tests` | 498 tests passed. |
| Controlled final `--complexity-only --scope all` rerun | Exit 0; `Complexity baseline check passed` with no baseline BLOCK, WARN, or ADVISE regressions. |
| Final exact 15-module focused command from `task-7-brief.md` | 109 tests passed. |
| Final `uv run python -m unittest tests.test_dsf_coastal_artifacts -v` and source inspection | 4 tests passed; XP11 search empty; `WATER_COLOR_MASK`, validated `BORDER_TEX`, and `tri_type == 0` decal guard confirmed. |
| Final changed-file `ruff format`; repository `ruff check`; changed-file and `tests` ty | Passed; 35 files unchanged by formatter. |
| Final `uv run python -m unittest discover -s tests` | 498 tests passed. |
| Final `uv run python .codex/skills/repo-hygiene/scripts/hygiene.py --full` | Exit 0; sync, package build, 498 tests, Ruff, format, ty, full complexity, CMake configure, Clang-Tidy config, and native build passed. |
| Final `uv run python .codex/skills/quality-check/scripts/quality_check.py` | Exit 0; unittest, Ruff, ty, format, whitespace, code-quality, full complexity, Clang-Tidy, CMake, and native build passed. |
| `uv run python .codex/skills/maintenance-qa/scripts/maintenance_qa.py` | Exit 0, PASS with warnings; security lint, 59% coverage, and 16.0% docstring coverage passed. |
| `git diff --check` | Exit 0 with no output. |

## Current warnings and gate behavior

- During remediation, the standalone complexity command treated baseline
  WARN/ADVISE regressions as blocking and exited `1`, even with 0 BLOCK
  findings. The final command exited `0`.
- The full quality script reported 19 nonblocking code-quality warnings. The
  work-attributable warning is
  `tests/test_texture_artifact_finalizer.py` at 642 lines; the remaining
  findings are existing legacy size warnings/waivers.
- Standalone maintenance QA reported two nonblocking warning dimensions:
  56 assessed dependency CVEs and 4 dead-code findings. Mutation testing was
  explicitly skipped because it is not yet configured. The maintenance audit
  still returned `PASS (with warnings)` and exit `0`.
- No required Task 7 verification stage was skipped. GitHub Issue #39 was
  intentionally not commented on or closed because whole-branch review is the
  next gate.

## Acceptance checklist

- [x] Missing masks never select overlay coordinates.
- [x] No external mask enters conversion cleanup.
- [x] Failed DDS conversion retains its mask.
- [x] Extent-incompatible failover is rejected.
- [x] Resolved provider names reach final terrain references.
- [x] Ocean decals are absent.
- [x] Invalid sand configuration is rejected before mask replacement.
- [x] No sister sea-texture subsystem or XP11 branch was added.
- [x] Full complexity baseline has no regressions.
- [x] Full hygiene, maintenance, and native quality gates pass.
- [x] TODO completion evidence is updated.
- [x] Task 7 completion commit is created.

## Self-review

The complete diff was reviewed against every Task 7 acceptance criterion. The
quality remediation preserves the approved behavior and extracts only
responsibilities implicated by reproduced metrics. No new failure class or
untriggered cleanup was introduced. Issue #39 remains open and uncommented
until independent Task 7 and whole-branch review completes.

## Independent review remediation

The independent Task 7 review returned three findings. Changes below are
limited to those reproduced failure classes.

| Finding | Root cause | Correction |
| --- | --- | --- |
| Critical: DSF raster retention | `coastal_artifacts` stored `(CoastalMaskDecision, PIL.Image)` and returned the retained image on cache hits; `needs_mask` did not explicitly close its opened source image. | Cache only the immutable decision; return the inferred crop only on the cache miss and return `None` on hits without reloading. Explicitly close the source image after cropping and close rejected crops. |
| Important: model dependency inversion | `O4_Texture_Models` imported `TextureCleanupPlan` from `O4_Texture_Mask_Lifecycle`, which imports filesystem, PIL, filename, and UI backends. | Define `TextureCleanupPlan` in the backend-neutral model module and import it from the lifecycle consumer. Validate an isolated direct model import while guarding against lifecycle-backend imports. |
| Minor: terrain file modes | Transaction staging wrote fresh candidate and rollback files with process-default modes despite the documented original-mode contract. | Apply `shutil.copymode` from the original terrain to both candidate and backup during preparation; any mode-copy `OSError` follows the existing preparation cleanup/error path. |

### RED/GREEN evidence

| Cycle | RED | GREEN |
| --- | --- | --- |
| Decision-only coastal cache | `test_cache_retains_only_decision_and_returns_mask_once` failed because the cache value was `(decision, PIL.Image)`, not `CoastalMaskDecision`. | The same test passed; the second lookup returned the same decision and `None` without invoking the loader. |
| Inferred-mask source ownership | `test_inferred_mask_source_is_closed_after_crop` failed because `close()` had 0 calls. | Both DSF ownership regressions passed after explicit source/rejected-crop closure. |
| Backend-neutral model import | `test_direct_import_does_not_load_mask_lifecycle_backend` failed because direct model execution attempted to import `O4_Texture_Mask_Lifecycle`. | Isolated direct model execution plus all five mask-lifecycle tests passed (6 tests). |
| Terrain mode propagation | `test_staged_candidate_and_backup_preserve_original_mode` failed because `copymode` had no calls. | The test passed with exact candidate/backup calls and matching portable permission bits. |
| Mode-copy preparation cleanup | With the mode-copy calls mutation-reverted, `test_mode_copy_failure_removes_staged_files` failed because no `TextureFinalizationError` was raised. | With the fix restored, both mode tests passed; the injected `OSError` retained original terrain bytes and left no staging artifacts. |

Focused post-fix checkpoint:

- `uv run python -m unittest tests.test_dsf_coastal_artifacts
  tests.test_texture_artifact_finalizer tests.test_texture_models
  tests.test_texture_mask_lifecycle -v`
- Result: 39 tests passed.

### Review-fix quality traceability

The full complexity gate exposed only regressions attributable to the review
fixes. Each correction stayed within that reproduced failure class:

| Reproduced condition | Correction |
| --- | --- |
| `needs_mask` CC 5 versus baseline 4, nesting 4 versus baseline 3, and nloc 26 versus baseline 22 | Extract `_cropped_mask_image` for owned source-image handling, then `_mask_crop_request` for the pure crop geometry. |
| `O4_Texture_Models` module MI 64.3877 versus baseline 64.4917 | Document the backend-neutral cleanup-plan ownership contract. |
| `test_cache_retains_only_decision_and_returns_mask_once` nloc 42 | Extract the repeated coastal-artifact lookup setup. |
| `tests/test_texture_artifact_finalizer.py` module MI 47.0315 | Move the transaction-specific mode regressions into `tests/test_terrain_artifact_transaction.py`. |
| Ruff S603 on the first subprocess-based model-boundary test | Replace the subprocess mechanism with isolated `importlib` execution and a guarded import boundary. |

The first full complexity rerun after the review fix exited `1` with the
`needs_mask` CC/nesting/nloc findings, the model MI warning, the cache-test
nloc block, and the finalizer-test MI block. After the exact-class corrections,
the second rerun exposed only the `needs_mask` nloc warning. The final helper
extraction removed that last regression, and the final complexity rerun exited
`0` with `Complexity baseline check passed`.

### Review-fix final verification

| Command | Result |
| --- | --- |
| Exact 15-module Task 7 command from `task-7-brief.md` | 111 tests passed. |
| Focused DSF/finalizer/transaction/model/lifecycle regressions | 39 tests passed. |
| Changed-file `ruff format`; repository `ruff check`; changed-file and `tests` ty | Passed; 9 files unchanged by formatter. |
| `uv run python -m unittest discover -s tests` | 503 tests passed. |
| `uv run python .codex/skills/quality-check/scripts/quality_check.py --complexity-only --scope all` | Exit 0; `Complexity baseline check passed`. |
| `uv run python .codex/skills/repo-hygiene/scripts/hygiene.py --full` | Exit 0; 503 tests, Ruff, ty, format, complexity, package build, CMake/Clang-Tidy configuration, and native build passed. |
| `uv run python .codex/skills/quality-check/scripts/quality_check.py` | Exit 0; unittest, Ruff, ty, format, whitespace, code quality, complexity, Clang-Tidy, CMake, and native build passed. |

The full quality run reported 19 nonblocking legacy/size warnings and 0
blocks. No review-fix verification stage was skipped. GitHub Issue #39 remains
open and uncommented for whole-branch review.
