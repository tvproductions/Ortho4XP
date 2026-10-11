# Ortho4XP Skills-first Alignment Design

## Intent and reference

Adopt the full standard of
[gz-skills-first-starter](https://github.com/tvproductions/gz-skills-first-starter)
in verified stages. The maintainer confirmed full alignment, including Python
3.14 and quality-tool changes, while retaining Ortho4XP's additional domain
dependencies.

Reviewed starter revision: `4acc41595b673faabdbe9be8d38b62755048ab93`.
This published revision supplies adoption tooling and the Python engineering
binding. Its pinned Superpowers baseline is older than the current published
release, so use its documented project-specific catalog route, as already used
in the maintainer's xplane-health project.

## Alternatives and selection

1. **Native stack and full engineering standard in stages (recommended):**
   maintain exact source pins, preserve project authorities, prove native
   dependency compatibility before the runtime switch, and explicitly compare
   old and new quality measurements.
2. **Configure the shared starter baseline unchanged:** reproducible, but would
   select Superpowers 6.4.1 despite a verified 7.0.0 release and would retain
   unresolved Python/tool-policy gaps.
3. **Refresh vendored Superpowers:** retains the current layout but conflicts
   with the starter's ownership/discovery contract and was rejected by automatic
   approval review. Do not retry that replacement.

## Stage 1: Native skill discovery and project binding

- Record the starter revision and component revisions in
  `.skills-first/bundle.lock.json`.
- Use a project-local `ortho4xp-skills-first` catalog with matching Codex and
  Claude component pins: Superpowers 7.0.0 at
  `bb92a77741419a4ab5f06e711a283343f1ada0c3`, gz-skills 0.5.0 at
  `5c3b327fc238a740062d366f03a4b443ab28834f`, and the starter's deferred
  Backplane revision `d0eeee829c491da02351e793544aa16ad96461bf`.
- Enable the default pair only for this project. Keep Backplane disabled and
  override duplicate gz-skills discovery only within project configuration.
  Native managers own installation caches; preserve other projects' state.
- Copy the starter-owned `skills-first-start` entry unchanged. Keep the Python
  engineering binding reachable at the recorded starter revision.
- Replace the vendored Superpowers discovery path with native plugin discovery
  only after the native source is installed and verified. Preserve a recoverable
  snapshot and Git history; remove the obsolete vendoring instructions together
  with the tree. This is an explicit migration, not an upstream-tree refresh.
- Update AGENTS.md to point to the stack binding while retaining ownership,
  native-build, platform, data, backlog, and release rules. Keep project-owned
  operational skills in their established locations.
- Validate catalogs, installation identity, and configuration. Fresh-session
  skill discovery remains UNKNOWN until an actual new session verifies it.

## Stage 2: Python 3.14 and domain dependencies

- Select current supported Python 3.14.8; synchronize `.python-version`,
  `requires-python`, Ruff/ty targets, installers, documentation, and CI.
- Preserve scientific and geospatial runtime requirements: aiohttp, NumPy,
  Pillow, Pydantic, pyproj, Requests, Rtree, Shapely, scikit-fmm, and GDAL.
  Preserve native mesh/scenery/texture utilities and PyInstaller packaging.
  The starter's dependency-free helper does not constrain the application.
- Replace CPython 3.13 wheel references with checksum-verified CPython 3.14
  assets. The existing vendor publishes GDAL 3.13.3 for CPython 3.14 Windows.
  PyPI does not publish a CPython 3.14 scikit-fmm wheel: build and test its
  released source in isolated temporary storage before adopting a wheel or
  a reproducible source-build path. A failed compatibility probe blocks the
  runtime switch; do not remove this runtime capability to pass.
- Keep GDAL Python bindings and the native library matched on each platform.
  Windows vendor and Homebrew currently provide 3.13.3. Reconcile Linux's
  existing 3.9.0 pin with the supported native installation before claiming
  Linux compatibility or a clean universal vulnerability audit.
- Regenerate uv.lock through uv, sync all groups, repeat resolution without
  churn, and verify actual imports and representative GDAL/skfmm operations.
- Assess Python 3.14 opportunities with concrete consumer evidence; defer
  syntax/API modernization that does not help this maintenance change.

## Stage 3: Routine checks and explicit hygiene

- Routine pre-commit checks: project-locked Ruff check/format, ty, and unittest.
  Keep CI routine checks aligned; preserve required native and packaging smoke
  checks. Do not run deep hygiene automatically through hooks or CI.
- Preserve current lint rules and justified exceptions. Add strict rules only
  after reviewing their findings; do not select ALL or blanket-suppress debt.
- Explicit hygiene uses Ruff C901 (ceiling 20), complexipy (ceiling 15), Lizard,
  Interrogate, Vulture, Bandit, Coverage.py, Cosmic Ray, deptry, pip-audit, and
  Import Linter. Establish current supported tool versions through uv.
- Retire Xenon and Radon after retaining their final evidence and comparing
  measurements against the starter's `lizard-functions-v1` contract. Retain
  project-specific Lizard thresholds and a baseline that may only shrink;
  do not describe new scores as Radon equivalents or waive absolute failures.
- Replace mutmut with Cosmic Ray only after a synthetic unittest fixture
  proves compatibility on the pinned runtime. Keep application mutation scope
  bounded and explicit.
- Define import-boundary checks from actual module responsibilities; preserve
  legacy module naming and external import contracts. Record assessed dynamic
  imports rather than removing needed dependencies to satisfy deptry.
- Update skill scripts, tests, examples, and consumer documentation together.
  Meaningful workflow changes use failing unittest cases before implementation.

## Authority and verification

TODO.md identifiers and GitHub Issue links remain the backlog authority;
ROADMAP.md remains direction. No Backplane lifecycle, automatic schedules,
deployment, release publication, or changes to other projects are introduced.

Each stage runs its affected tests and the applicable project verification.
The maintenance handoff records exact sources, runtime/tool versions, native
asset provenance, vulnerability results, unresolved compatibility limits,
measurement comparisons, and actual host discovery status. Configuration alone
never counts as completed installation or loading.

## Current evidence before implementation

The initial dependency refresh on Python 3.13.16 passes the full existing
quality gate (556 unittest cases, lint, format, ty, complexity baseline, and
LLVM/CMake), distribution build, imports, CLI help, and build-job validation.
The installed Windows environment has zero OSV findings across 58 third-party
packages. The universal uv audit reports 10 advisory records against Linux
GDAL 3.9.0, representing seven CVEs after alias deduplication.

The starter's configure preview fails closed on the current vendored
Superpowers path. No vendored instruction files have been changed.

## Execution evidence

The user approved this staged design. The subsequent
[implementation receipt](../../dependency-refresh-2026-10-11.md) records the
native replacement, runtime and quality changes, observed verification and
remaining assessment failures. The section above describes the initial state.
