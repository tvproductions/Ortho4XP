# Dependency refresh follow-up — 2026-10-11

Mode: **authorized update**. The user requested another dependency update after
gz-skills was bumped. This pass preserves the uncommitted full alignment and
the approved Python 3.14 starter standard, project dependencies and tool groups.

## Reviewed source changes

| Surface | Previous selection | Selected release and revision |
| --- | --- | --- |
| gz-skills | 0.5.0, `5c3b327fc238a740062d366f03a4b443ab28834f` | [0.6.0](https://github.com/tvproductions/gz-skills/releases/tag/v0.6.0), `e722e808647481c4c9d2feab61f1843aa8e0b19a` |
| Starter template | Unversioned reviewed commit `4acc41595b673faabdbe9be8d38b62755048ab93` | [0.1.0](https://github.com/tvproductions/gz-skills-first-starter/releases/tag/v0.1.0), `b3dd0e47095499bd07f33448b38166221c2c1eec` |
| Superpowers | 7.0.0, `bb92a77741419a4ab5f06e711a283343f1ada0c3` | Retained; latest published release |
| Backplane | Deferred commit `d0eeee829c491da02351e793544aa16ad96461bf` | Retained; upstream main matches, no published release; disabled |

Reviewed release notes, tag targets and changed source files before applying.
gz-skills adds project setup and the Pythonic detection/application pair, taking
the canonical catalog to 19 skills. The update skill now distinguishes review
from authorized mutation and inventories templates/plugins. Its profile defaults
explicitly yield to approved starter policies and overrides. No profile was
initialized or selected; no retired tool was reintroduced or application package
removed. Python CLI floor 3.13 is compatible with our 3.14.8 environment; native
skill loading does not require installing the upstream Python CLI.

The starter's first release adds explicit template version provenance and
selected-family freshness guidance. Its front-door skill and instruction
fragment were reconciled from the reviewed release, byte for byte. The project
Python binding retains its reviewed tool choices, platform GUI exception and
stricter complexity ratchet. The starter's source still describes capabilities
absent from its own gz-skills 0.5.0 baseline as proposals; the project stack guide
records that our reviewed 0.6.0 override now supplies them.

Both native catalogs and the project bundle record use the same new immutable
gz-skills SHA. The starter record now includes its actual released version and
SHA; the prior development revision was not retroactively labeled 0.1.0.
Previous selections above are rollback pins. No upstream cache was patched.

## Other dependency surfaces

Fresh [PyPI registry queries](evidence/2026-10-11-dependency-follow-up/pypi.json)
cover all direct runtime, dev, hygiene, release and build dependencies plus uv.
All selected versions remain current. The
[full locked dependency tree](evidence/2026-10-11-dependency-follow-up/tree.txt)
contains no newer package annotations, and the synchronized all-group Windows
environment's outdated query returned no rows. `uv lock --upgrade` resolved 96
packages without byte changes; `uv lock --check` passed. `pyproject.toml`,
`.python-version`, runtime wheels and `uv.lock` retain the prior verified values.

[Python's official release index](https://www.python.org/downloads/) identifies
3.14.8 as the newest stable patch in the selected 3.14 family. Python 3.15.0 is
available in a newer family; this maintenance pass preserves the approved
`>=3.14,<3.15` compatibility decision. The executing interpreter is 3.14.8.
uv 0.13.0, setup-uv 10.3.0, checkout's v7 track (latest patch 7.0.1), and
setup-python's v7 track (7.0.0) remain current by their upstream release APIs.
Pre-commit hooks use project-locked tools; no independent hook revision applies.

[7-Zip's current download page](https://www.7-zip.org/download.html) still lists
26.04, and [X-Plane's vendor page](https://developer.x-plane.com/tools/xptools/)
still lists XPTools 24-5. Verified bundled bytes are retained. The prior
NVcompress/NVTT, Medit/freeglut and Moulinette provenance gaps remain recorded
in the [initial refresh](dependency-refresh-2026-10-11.md); no unverifiable
replacement was introduced. Triangle4XP remains project-owned source; LLVM and
CMake minimum requirements remain intact without machine-global upgrades.
Upstream plugins own their internal dependencies. There is no additional
project-managed container, Node package or independent hook-tool manifest in
the established inventory.

## Installation and verification

`codex plugin add gz-skills@ortho4xp-skills-first --json` installed version 0.6.0
through the native manager. The manager enabled its user entry; that one entry
was restored to `enabled = false`, with project enablement retained. Alternate
sources remain disabled here; unrelated installations were not updated.
The inventory reports Backplane installed but disabled. This refresh performed
no Backplane install or enable action, and infers no readiness from that state.

All 42 canonical installed skill-resource files match the reviewed tagged
source, normalizing only CRLF. A fresh Codex app-server `skills/list` request
with project cwd and `forceReload: true` discovered all 19 canonical gz-skills
entries from the selected 0.6.0 path, without duplicates or discovery errors.
Backplane was absent from discovery. Claude source configuration is coherent;
Claude activation was not performed. Raw receipt: `tmp/dependency-rerun-discovery.json`.

| Verification | Observed result |
| --- | --- |
| Full routine quality command | PASS: 590 unittest tests, Ruff, format, ty, structural/whitespace, source coherence, clang-tidy and fresh LLVM/CMake build |
| Distribution build and application CLI help | PASS: wheel/sdist built; launcher startup/help exited 0 |
| Final four pre-commit hooks | PASS: project-locked Ruff check/format, ty and complete unittest suite |
| Universal locked uv advisory audit | PASS: 93 packages, zero vulnerabilities and zero adverse statuses |
| All-group synchronization and outdated checks | PASS: no newer packages; resolution stable |

The [advisory receipt](evidence/2026-10-11-dependency-follow-up/audit.json) retains
the universal audit result. This pass did not change application runtime bytes,
repeat PyInstaller packaging or rerun deep analyzers. The prior deep-hygiene
FAIL and Linux/macOS execution, packaging-boundary and native provenance gaps
remain tracked in the [quality receipt](evidence/2026-10-11-quality-migration.md)
and initial refresh. Routine verification does not claim those gaps are resolved.

Work remains uncommitted. The follow-up changes source records/catalogs, two
starter-owned instruction files and coupled documentation only; earlier approved
runtime and quality implementation remains intact.

Durable [routine output](evidence/2026-10-11-dependency-follow-up/routine-quality.txt)
and [hook output](evidence/2026-10-11-dependency-follow-up/pre-commit.txt) retain the
fresh verification. A final local review confirmed matching catalog/source pins,
unchanged runtime manifest/lock and project enablement, identical starter copies,
resolving changed-document links and `git diff --check` success.
