# Deeper hygiene review — 2026-10-11

Reviewed commit: `dc6ee33559c51b7e986a961bcc014e0a43d6829f`, Python 3.14.8 on
Windows. This is a requested reassessment and recommendation, not an application
implementation. No application code, threshold, whitelist or baseline changed.

The canonical command was rerun:

```powershell
uv run --group hygiene python .codex/skills/maintenance-qa/scripts/maintenance_qa.py
```

It exited **1 / FAIL**. Every selected dimension ran independently; mutation
remains NOT_REQUESTED because no application mutation scope was supplied. The
[summary](2026-10-11-deeper-hygiene-review/summary.json),
[exact populations and commands](2026-10-11-deeper-hygiene-review/scope.json) and
[268 source/configuration hashes](2026-10-11-deeper-hygiene-review/input-sha256.json)
make the assessment reproducible. Task-local complete output is
`tmp/deeper-hygiene-review.log`. A separate Ruff query reassessed the ten asset
diagnostics from the previous receipt.

| Dimension | Fresh outcome |
| --- | --- |
| Dependency advisories | PASS: 92 exact host-selected identities, zero advisories/skips; [receipt](2026-10-11-deeper-hygiene-review/advisory-audit.json) |
| Dependency usage / import boundaries | PASS / PASS; 166 graph nodes |
| Bandit | FAIL: eight raw findings, not eight demonstrated vulnerabilities |
| Vulture | FAIL: six candidates; four straightforward cleanup candidates and two API decisions |
| Coverage | FAIL: 38.52% combined statement/branch against 40%; statements 42.31%, branches 26.31% |
| Docstring presence | PASS: 16.2%, minimum 10% |
| Ruff C901 / cognitive complexity | FAIL: 14 / 86 above their respective 20 / 15 ceilings |
| Lizard C/C/C | FAIL/error: 28 function and three module violations; two files have incomplete discovery |
| Stricter ratchet / Cohesion policy | FAIL: 343 flagged comparisons, including 295 undefined-policy class measurements |

Reviewed findings: **0 critical, 5 high, 3 medium, 1 low**, grouped below by causal
failure rather than counting each analyzer hit as a separate defect. Routes are
project maintenance tasks identified here; external issues were not created.

## High-priority findings

**DH-001 — Streamed subprocesses can deadlock.**
`src/O4_Subprocess_Runtime.py:21` consumes stdout until EOF before draining stderr,
while both are pipes. A child blocked on a full stderr pipe cannot finish or close
stdout. Mesh generation and overlay conversion call this path at
`src/O4_Mesh_Utils.py:648` and `src/O4_Overlay_Utils.py:96`, among others.
The existing tests exercise short stdout, not stderr pressure.

A bounded, network-free witness sent 1,000,000 stderr bytes before stdout:
ordinary captured execution finished with code 0 in 0.033 seconds; the streamed
runner reached the child watchdog at 2.038 seconds, returned 77, and produced no
stdout. [Probe result](2026-10-11-deeper-hygiene-review/stream-probe.json).
The child watchdog prevents an indefinitely stuck diagnostic. This agrees with
[Python's pipe/deadlock warning](https://docs.python.org/3.14/library/subprocess.html#subprocess.Popen.wait).

Fix route: drain both streams concurrently while preserving separate stderr,
stdout callbacks and exit status. Add a failing real-child regression before
implementation; cover stderr pressure, nonzero exit and callback failure/cleanup.
Do not merge streams merely to hide the blocking condition.

**DH-002 — Provider failures strand the credential-refresh state.**
`Providers/O4_Custom_URL.py:83`, `:112`, `:136` and `:157` set a credential variable
to `"loading"` before a request. A connection or parsing failure does not reset
it. Subsequent calls sleep forever waiting for a refresh that has already failed.
The HTTP calls also lack connect/read timeouts, so even the first refresh can
block. Four Ruff S113 calls are reported; the Session.get path has the same
underlying omission even though it is not among those four hits.

An offline mocked connection failure reproduced stranded state in all four
loaders, followed by the next call entering its three-second waiting loop.
[Probe results](2026-10-11-deeper-hygiene-review/provider-probe.json).
Fix route: add bounded HTTP timeouts and refresh ownership/waiting; always reset
or publish state and notify waiters on success and failure. Test connection
failure, malformed response, timeout and concurrent callers. Avoid logging
credential values during the repair. No live provider request was made.

**DH-003 — Airport caches deserialize executable pickle data.**
The actual risky sites are `src/O4_DSF_Utils.py:144` and
`src/O4_Mesh_Utils.py:132`. Their single writer is
`src/O4_Airport_Geometry.py:148`; the filename comes from
`src/O4_File_Names.py:246` under the selected tile build directory.
Normal operation reads a locally generated cache; no remote exploitation path
was established. Nevertheless, a substituted/shared untrusted `.apt` file can
execute code before the existing corruption handlers can protect the reader.
This is the documented [pickle trust boundary](https://docs.python.org/3.14/library/pickle.html).

Fix route: replace the single writer and both readers together with a versioned,
validated data-only cache. Encode geometry with an explicit data representation
such as WKB plus bounded metadata, verify the schema and handle corrupt caches
by regeneration. Reject/regenerate old pickle caches rather than automatically
unpickling them as a migration fallback. Add round-trip geometry and corrupt/
hostile-cache tests. Three pickle-import diagnostics refer to this same feature;
they are not three additional exploitation sites.

**DH-004 — Lizard omits four valid Protocol methods.**
The missing definitions are `scripts/upstream_watch_core/github_api.py:47` and
`src/O4_Texture_Conversion_Scheduler.py:16`, `:18`, `:20`. Both strict adapters
correctly reject the population mismatch, but the analyzer contract cannot yet
measure these supported sources completely. The aggregate of 2,305 functions is
partial; maximum 110 and mean 2.8811 do not certify the omitted population.
[Native receipt](2026-10-11-deeper-hygiene-review/lizard.json).

Fix route: correct the Lizard parser/frontend or add a narrowly specified,
tested source-analysis normalization with original line mapping. Compare inline
and multiline ellipsis methods, abstract methods, nested and async definitions.
Require complete population equality in both adapters. Do not skip Protocol
methods or reformat domain code solely to satisfy the analyzer.

**DH-005 — Cohesion has no valid bound policy for its actual metric.**
The installed tool emits attribute-use percentages, calculated from method
attribute counts divided by class-variable/method population. It does not emit
the historical LCOM4 metric. Its parser considers direct synchronous methods;
modern constructs require compatibility checks. The 295 blocked measurements
are evidence of one undefined measurement-policy contract, not 295 proven
poorly cohesive classes. [Ratchet receipt](2026-10-11-deeper-hygiene-review/ratchet.json).

Fix route: specify the measured population, dataclass/classmethod/staticmethod/
async behavior and meaningful verdict semantics using synthetic positive and
negative fixtures. Demonstrate the installed analyzer's compatibility before
adopting its policy; if it fails those fixtures, propose a compatible replacement
through the approved tooling workflow. Do not translate the old LCOM4 threshold
to a percentage, clamp native values or baseline the entire error set as clean.

## Medium and low findings

**DH-006, medium — Test coverage needs explicit semantics and risk-focused tests.**
The historical minimum does not identify a metric, while the new runner includes
branches. Statements alone exceed the old numerical 40%; combined coverage
does not. This is not evidence that statement coverage regressed. There are
3,020 uncovered branch opportunities. The streamed runner has 93.94% combined
coverage yet still deadlocks in the probe, demonstrating a missing scenario
despite a high score. [Complete coverage receipt](2026-10-11-deeper-hygiene-review/coverage.json).
Fix route: record separate statement/branch/combined semantics in the baseline,
retain the current minimum, and add deterministic tests for subprocess pressure,
provider failure recovery, cache integrity, geometry boundaries and cancellation.
Do not prioritize GUI line-count coverage merely to cross 40%.

**DH-007, medium — Complexity is concentrated in consequential legacy operations.**
`build_dsf` (`src/O4_DSF_Utils.py:393`) scores 110 Lizard / 283 cognitive;
`update_dicosm` (`src/O4_OSM_Utils.py:69`) 63 / 182;
`record_water_tris` (`src/O4_Mask_Utils.py:434`) 58 / 162.
The 86 cognitive violations include six in nine archived `src/Unused`
modules; tests and maintenance scripts are also measured. The counts are not
86 independent shipped defects. Fix route: retain labeled populations and
characterize one hot path at a time, then extract stages with explicit inputs,
outputs and preserved ordering/error semantics. Start with a bounded DSF stage
after the runtime/security fixes. Keep the stricter ratchet and absolute limits.
[Cognitive scores](2026-10-11-deeper-hygiene-review/cognitive.json).

**DH-008, medium — The mask API advertises a parameter it ignores.**
`src/O4_Imagery_Utils.py:852` retains `is_sharp_resize`, and its comment promises
per-call selection; actual resizing uses `mask_resize_resampling`. The active
caller at `src/O4_Mask_Utils.py:419` still supplies the argument. Fix route:
reconcile and document global versus per-call resampling precedence, preserving
existing keyword callers through an explicit compatibility/deprecation path.
Test nearest/bicubic selection rather than deleting the flagged parameter blindly.

**DH-009, low — Remove obsolete unreachable code and unused imports safely.**
Delete the unreachable retired downloader below `src/O4_DEM_Utils.py:678`, the
permanently disabled road branch at `src/O4_Vector_Map.py:320`, and the unused
`timezone` imports in the metadata/upgrader modules. Preserve current return
behavior and run the relevant tests. `indexed_difference`'s `idx_pol1` parameter
is a compatibility candidate, not a safe blind deletion: an archived caller
uses the four-argument signature. Document that contract before deprecation.
Literal-name setattr calls in the provider can become normal attribute assignment
in the provider repair; this is lint maintenance, not a demonstrated exploit.
[Vulture receipt](2026-10-11-deeper-hygiene-review/vulture.txt).

## Reviewed alerts and execution order

The two provider S105 hits compare/assign the string `"loading"`; these are
verified false positives for a hardcoded credential. The subprocess B404/B603
alerts and two utility S603 alerts identify use of subprocess APIs. Reviewed
callers construct argv lists without `shell=True`; the utility configuration
selects fixed platform/build values. No shell-injection exploit was established.
Executable override/PATH trust is an intentional command-execution boundary
that should remain documented and tested. These generic alerts must not distract
from DH-001's proven blocking defect. Raw findings remain retained; no blanket
suppression or passed security-gate claim follows from this review.
[Bandit evidence](2026-10-11-deeper-hygiene-review/bandit.json) and
[asset evidence](2026-10-11-deeper-hygiene-review/asset-lint.json).

Recommended small changes: **DH-001 first**, DH-002 next, then DH-003; make
DH-004/005 measurement contracts trustworthy before using analyzer totals to
drive broader refactoring. Add consequential tests with each fix, clarify
DH-006's measurement contract, then undertake one DH-007 hot path and the
bounded DH-008/009 cleanup. Keep deeper checks explicitly requested; do not add
them to routine hooks or CI. Rerun the owning probe and required routine gate
for each implementation. This review did not reassess release packaging,
foreign-platform execution or native-binary provenance; their prior gaps remain
tracked in the dependency-refresh evidence.
