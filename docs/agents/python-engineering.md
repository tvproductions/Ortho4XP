# Project Python engineering binding

This project adopts the Python engineering standard from
gz-skills-first-starter 0.1.0, revision
`b3dd0e47095499bd07f33448b38166221c2c1eec`. The reviewed update preserves the
original tool choices and adds exact-family freshness and template provenance
guidance; see the [follow-up receipt](../dependency-refresh-2026-10-11-follow-up.md).
The [approved design](../superpowers/specs/2026-10-11-skills-first-alignment-design.md)
defines the staged adoption. AGENTS.md retains project ownership, platform,
backlog, native tooling, and generated-data authority.

## Runtime and application dependencies

Use Python 3.14.8 through uv, with `requires-python`, Ruff's `py314` target,
ty, installers and CI aligned. Use unittest, never an alternate test runner.
Preserve NumPy, Pillow, Pydantic, pyproj, Requests, aiohttp, Rtree, Shapely,
scikit-fmm and matched native/Python GDAL capabilities. The starter's small
dependency-free example does not constrain this application.

New behavior uses TDD at a public seam and clear domain outcomes. Keep domain
calculations independent of I/O; adapters own filesystem, network, process and
native effects. Existing flat O4 module names and external consumer contracts
remain valid. Prefer appropriate current stdlib APIs; do not mechanically
change annotation evaluation or syntax without consumer evidence. The runtime
migration's opportunity assessment is in the dependency-refresh evidence.

## Routine verification

```powershell
uv sync --dev
uv run python .codex/skills/quality-check/scripts/quality_check.py
uv run pre-commit run --all-files
```

The routine gate runs the real skills-stack source validator, unittest,
project-locked Ruff check, Ruff format checks, baseline/changed-file ty,
whitespace and structural audits, and native LLVM/CMake checks. Formatting
covers changed Python files and maintained skill scripts, preserving the
reviewed incremental modernization policy. Use `--skip-native` for a clearly
reported Python-only iteration. Repository hygiene additionally builds the
distribution and verifies native changed lines. Pre-commit has four local hooks
for Ruff check, format, ty and unittest. The format/type hooks use the same
reviewed baseline and changed-file policies as the routine gate.

Deep analyzers are never hooks, manual hooks, CI gates or an automatic
consequence of routine changes. A clean routine gate does not claim clean deep
hygiene. Skill scripts only orchestrate their own workflow and do not import
another skill's scripts.

## Explicit hygiene

```powershell
uv run --group hygiene python .codex/skills/maintenance-qa/scripts/maintenance_qa.py
uv run --group hygiene python .codex/skills/quality-check/scripts/quality_check.py --complexity-only --scope all
```

Run only on explicit maintenance requests. Tools are exact uv-lock pins in the
hygiene group and stay separate from runtime/dev dependencies. New task-specific
receipt directories live under ignored `tmp/`; source and operational data are
never analyzer outputs or mutation inputs. Missing tools, malformed output,
invalid syntax, omitted identities and incomplete measurements fail closed.
Run independent analyzers even when another fails. Legacy absolute failures
remain failures with precise tracking evidence; no mass domain refactor follows
merely to make a maintenance assessment pass.

| Tool | Interpretation and scope |
| --- | --- |
| Ruff C901 | Explicit ceiling 20; ignore `noqa` for measurement; preserve routine rule selection |
| complexipy | Cognitive/function and script ceiling 15; no ignores or snapshot waivers |
| Lizard | `lizard-functions-v1`: each function, module arithmetic mean and overall function-weighted mean ceiling 20 |
| Cohesion | Actual class percentages retained; historical LCOM4 policy is unverified and remains blocked |
| Bandit | Original source severity/confidence/context; no blanket suppressions |
| Vulture | Active O4 source at confidence 80; investigate public/dynamic consumers before deletion |
| Coverage.py | Active source statement and branch coverage via unittest; retain project minimum 40% |
| Interrogate | Source docstring presence against existing 10% minimum; review usefulness separately |
| deptry | Active source metadata and actual package/module mappings; first-party launcher recognized explicitly |
| pip-audit | Exact, hashed host-selected runtime/dev/hygiene lock export; no second resolver; every identity accounted for |
| Import Linter | Actual-source flat module graph; pure model definitions may not import I/O adapters, directly or indirectly |
| Cosmic Ray | Explicit disposable single-file scope and unittest; separate clean-baseline, survivor and tool-error outcomes |

The complexity scope includes launcher, source, tests, project scripts and
maintained skill scripts. Historical `src/Unused` code is measured for the
complexity comparison; deptry/Vulture active-source scope excludes this
packaged-out archive. Counting scopes and metrics are reported explicitly.

Lizard counts functions, async functions, methods and nested definitions once.
Class/module/lambda code does not enter function averages. Empty modules have
null means and no denominator contribution. Compile/AST discovery must match
Lizard locations; unsupported inline definitions or omitted CSV functions are
measurement errors. Values of 20 pass, greater values fail, without rounding.
Lizard, Ruff and cognitive scores are independent, not Radon equivalents.
The stricter project Lizard size/parameter/nesting/cyclomatic ratchet remains in
`complexity-thresholds.json` and `complexity-baseline.json`. Baseline refresh
requires full scope and may only shrink existing identities/scores; it never
waives absolute failures. The old Radon/Xenon envelope, thresholds and final
quality receipt are archived in `docs/evidence/2026-10-11-legacy-*`.

Cohesion 1.2.0 emits percentages, not LCOM4. The historical LCOM4 parser matched
no measurements and the baseline contains zero Cohesion entries. This is a
verification-chain defect. Preserve actual class percentages as blocked
`cohesion_policy_unverified` records; do not claim a working LCOM4 ratchet or
invent a percentage threshold. A reviewed percentage policy is separately
required before that dimension can pass.

The [Import Linter forbidden contract](https://import-linter.readthedocs.io/en/stable/contract_types/forbidden/)
is defined in `.codex/skills/maintenance-qa/importlinter.ini`. Its standard CLI
accepts packages rather than the actual flat O4 modules. The skill-local AST
graph adapter preserves original names, static imports in conditional branches,
line evidence and indirect edges, then uses the standard ForbiddenContract API.
Its explicit roots must match every active O4 module. Dynamic imports still
need separate consumer review; this adapter does not execute application code.

The [pip-audit](https://github.com/pypa/pip-audit) adapter uses `uv export --locked`
with all groups, preserving selected transitive pins and hashes. It appends
reviewed local-wheel identities and byte hashes, then audits with
`--no-deps --disable-pip`. A missing/skipped identity or advisory is a failure.
It assesses the host-selected resolution, not every foreign-platform runtime
or native library. No known advisories does not establish vulnerability absence.

## Mutation compatibility and bounded execution

Cosmic Ray 8.7.0 was tested on Python 3.14.8 with an invented increment function
and unittest checking negative, zero and positive inputs. Its unmodified baseline
was NORMAL/SURVIVED; all 13 generated mutants were NORMAL/KILLED. No application
mutation coverage is implied by that compatibility proof.

```powershell
uv run --group hygiene python .codex/skills/maintenance-qa/scripts/maintenance_qa.py --mutation-config tmp/ASSESSMENT/cosmic-ray.toml --mutation-workdir tmp/ASSESSMENT
```

Prepare an unused disposable directory with copied selected code/tests. Require
one file inside that directory, a unittest test command, a per-run timeout at
most 60 seconds, at most 200 generated jobs and 600 seconds per analyzer command.
Require an actually clean unmodified baseline and complete result population.
Retain databases, diffs and outcomes; inspect survivors before adding tests.
Equivalent mutants require human assessment. Timeouts, incomplete results,
worker exceptions and missing measurements are failures, not killed mutants.
See the [Cosmic Ray tutorial](https://cosmic-ray.readthedocs.io/en/latest/tutorials/intro/index.html).

## Evidence and maintenance

The [dependency-refresh evidence](../dependency-refresh-2026-10-11.md) records
runtime/native compatibility, freshness and advisory results. The quality
migration [receipt](../evidence/2026-10-11-quality-migration.md) records actual tool outputs and the remaining complexity,
cohesion, security, dead-code and coverage debt. Preserve useful docstrings and
meaningful tests; do not add filler, blanket exceptions or transplanted upstream
percentage targets. Freshness, compatibility and vulnerabilities are separate
assessments. Review runtime/dev/hygiene and native plugin pins explicitly during
adoption and quarterly maintenance; no scheduled work is created automatically.
