# Python quality migration receipt — 2026-10-11

The approved full Python engineering standard is implemented against starter
revision `4acc41595b673faabdbe9be8d38b62755048ab93`, with Ortho4XP's application
dependencies and stricter existing Lizard regression policy preserved.
Python 3.14.8 was used for these Windows measurements. Deep hygiene remains
**FAIL**; passing routine verification does not turn these findings into success.

Routine verification comprises unittest, Ruff, formatting, ty, actual skills-stack
validation, whitespace/structural checks and native LLVM/CMake verification.
Pre-commit runs four local, project-locked routine hooks. Ruff's hook uses the
same reviewed source scope as the routine gate via `--lint-only`; formatting and
typing likewise use the reviewed baseline/changed-file adapters. Deep analyzers
are explicit commands, never hooks or CI gates.

```powershell
uv run --group hygiene python .codex/skills/maintenance-qa/scripts/maintenance_qa.py
uv run --group hygiene python .codex/skills/quality-check/scripts/quality_check.py --complexity-only --scope all
```

The complete [hygiene run](2026-10-11-quality-migration/hygiene-run.txt) and
[dimension summary](2026-10-11-quality-migration/hygiene-summary.json) retain actual
verdicts. Final standalone complexity was rerun after the hook adapter changes.
[Input hashes](2026-10-11-quality-migration/input-sha256.json) identify the assessed
source, metadata and policy bytes. Analyzer outputs retain original source
identities; temporary databases and coverage data remain under ignored `tmp/`.

| Assessment | Actual result | Evidence and tracking |
| --- | --- | --- |
| Ruff C901, ceiling 20 | FAIL: 14 findings | [Native receipt](2026-10-11-quality-migration/analyzer-0.txt); source/function identities and values retained |
| complexipy 8.0.1, ceiling 15 | FAIL: 86 of 2,528 reported records exceed 15 | [Cognitive scores](2026-10-11-quality-migration/cognitive.json); no ignore/snapshot waivers |
| Lizard 1.24.1, `lizard-functions-v1` | FAIL/error: 28 function and 3 module ceiling violations; 2 source files have discovery errors | [Complete contract receipt](2026-10-11-quality-migration/lizard.json) |
| Existing stricter Lizard ratchet | FAIL: retained measurable findings plus newly exposed scope debt | [Scores, regressions and errors](2026-10-11-quality-migration/ratchet.json); no baseline rewritten to pass |
| Cohesion 1.2.0 | FAIL: policy unverified for 295 measured classes | Same ratchet receipt retains native percentages and explicit `cohesion_policy_unverified` findings |
| pip-audit 2.10.1 | PASS: 92 host-selected exact identities, 0 advisories, 0 skipped | Summary retains lock-export audit receipt path; expected/audited identity populations must match |
| deptry 0.25.1 | PASS: no active-source usage findings | Actual metadata, first-party launcher and package/module mappings assessed; archived `src/Unused` excluded |
| Import Linter 2.15 / Grimp 3.17 | PASS: configuration/source definitions independent of I/O adapters; 166 graph nodes | Actual flat source graph, including conditional and indirect edges; standard forbidden contract |
| Bandit 1.9.4 | FAIL: 8 high-confidence findings, 2 medium and 6 low severity | [Original findings and contexts](2026-10-11-quality-migration/bandit-findings.json) |
| Vulture 2.16 | FAIL: 6 candidates | [Native receipt](2026-10-11-quality-migration/vulture.txt); public/dynamic consumers require investigation before deletion |
| Coverage.py 7.16.2 | FAIL: 38.52% combined statement/branch coverage, 4,098 branches; minimum 40% | Retained project threshold; branch measurement differs from former statement-only coverage |
| Interrogate 1.7.0 | PASS: 16.2%; retained minimum 10% | Presence measurement does not establish docstring usefulness |
| Cosmic Ray 8.7.0 compatibility fixture | PASS: 13 generated mutants, all NORMAL/KILLED; 0 survivors or worker errors | [Fresh fixture receipt](2026-10-11-quality-migration/cosmic-receipt.json) and [outcomes](2026-10-11-quality-migration/cosmic-outcomes.json) |

The Lizard contract aggregate covers 2,305 successfully assessed functions:
maximum 110 and function-weighted mean 2.881127982646421. It is a **partial
measurement**, because original inline Protocol methods were not discovered:
`scripts/upstream_watch_core/github_api.py:47` and
`src/O4_Texture_Conversion_Scheduler.py:16`, `:18`, `:20`. The strict CSV adapter
also records this population mismatch. Empty/header-only, malformed or incomplete
output cannot silently pass or erase a baseline. The missing-function discovery
defect requires a reviewed analyzer correction; changing domain methods merely
to satisfy discovery is not an approved debt waiver.

The historical Cohesion adapter expected an LCOM4 textual format, but installed
`cohesion -f` emits class percentages. It therefore recorded no Cohesion baseline
identities. These percentages, including native values above 100%, are retained
unchanged. Applying the old LCOM4 threshold to them would be invalid. The
historical policy remains an explicit failed measurement-policy gap until its
metric semantics are reviewed; no new percentage threshold was invented.

All four preserved ratchet dimensions were independently checked for introduced
quality/hygiene helpers and tests: NLOC block 37, CCN block 11, parameter block 5,
nesting block 4. Existing captured scores may not increase. The
[new-code assessment](2026-10-11-quality-migration/new-code-ratchet.json) records
**zero introduced or increased ratchet failures**. None of the new maintenance
helpers exceeds cognitive complexity 15. Existing scope debt remains visible,
including legacy tests and project scripts newly covered by the full source
universe. The ratchet reports 343 regressions, including 295 blocked Cohesion
policy findings; each identity/value is retained rather than blanket suppressed.

Bandit candidates are `O4_Airport_Geometry.py:1` B403;
`O4_DSF_Utils.py:4` B403 and `:144` B301;
`O4_Mesh_Utils.py:2` B403 and `:132` B301;
`O4_Subprocess_Runtime.py:1` B404 and `:11`, `:25` B603, all under `src/`.
Untrusted pickle deserialization and subprocess input boundaries require actual
consumer review. Findings are not automatically asserted to be exploitable.
Vulture candidates are `O4_DEM_Utils.py:678` unreachable code,
`O4_Imagery_Utils.py:852` `is_sharp_resize`,
`O4_Package_Metadata.py:3` and `O4_Package_Upgrader.py:4` `timezone`,
`O4_Vector_Map.py:320` unsatisfiable condition, and
`O4_Vector_Utils.py:817` `idx_pol1`. The old unused-only counter omitted the
unreachable/unsatisfiable findings; a failing semantic test demonstrated that
defect before the native finding-line parser was corrected.

The fresh Cosmic Ray probe uses an invented increment function and unittest
negative, zero and positive inputs. Its unmodified baseline was actually
NORMAL/SURVIVED before mutation execution. Retained
[source](2026-10-11-quality-migration/cosmic-source.txt),
[unittest](2026-10-11-quality-migration/cosmic-unittest.txt) and
[configuration](2026-10-11-quality-migration/cosmic-ray.toml) make the compatibility
claim reproducible. Complete result population is required; partial sessions,
timeouts and worker/test errors fail. This proves tool compatibility, not
application-wide mutation coverage or equivalent-mutant classification.

Broader asset lint debt was exposed by an initial unrestricted hook: 10 findings
in custom provider URL code and `Utils/run`, outside the reviewed routine scope.
The [original diagnostics](2026-10-11-quality-migration/asset-lint.json) retain
each path, line and Ruff rule (provider B010/S113/S105 and utility S603).
The hook now shares the routine scope instead of unexpectedly adopting a wider
baseline. This debt remains recorded in the active dependency-refresh evidence;
it was not waived by a suppression or application rewrite.

Final old Radon/Xenon-era comparisons remain in
[legacy baseline](2026-10-11-legacy-complexity-baseline.json),
[legacy thresholds](2026-10-11-legacy-complexity-thresholds.json) and
[legacy gate log](2026-10-11-legacy-quality.log). Radon/Xenon and mutmut are retired;
Ruff, complexipy, exact Lizard semantics and the actually executed Cosmic Ray
fixture replace them. Vulnerability freshness, compatibility and analyzer
findings are separate assessments. The host advisory audit does not cover every
foreign-platform runtime or native-library vulnerability.
