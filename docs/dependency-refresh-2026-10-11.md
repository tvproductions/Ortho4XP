# Dependency and skills-first refresh — 2026-10-11

This implements the user-approved
[staged alignment](superpowers/specs/2026-10-11-skills-first-alignment-design.md).
All changes are uncommitted. Ortho4XP retains its domain dependencies and
project rules while adopting the starter's runtime, native skill ownership,
and routine/deep quality separation.

The [same-day follow-up](dependency-refresh-2026-10-11-follow-up.md) records
the subsequent gz-skills 0.6.0 and starter 0.1.0 refresh and fresh verification.

## Runtime and dependency inventory

| Surface | Selected version or disposition |
| --- | --- |
| Python | 3.14.8; `>=3.14,<3.15` |
| uv / uv_build | 0.13.0 / `>=0.13.0,<0.14` |
| NumPy / Pillow | 2.5.4 / 12.3.0 |
| GDAL / pyproj / Shapely | 3.13.3 / 3.8.0 / 2.2.0 |
| Requests / aiohttp / Pydantic | 2.34.2 / locked 3.14.5 / locked 2.14.1 |
| Rtree / scikit-fmm | 1.4.1 / 2025.6.23, current released versions |
| Ruff / ty / pre-commit / packaging | 0.17.0 / 0.0.86 / 4.6.2 / 26.3 |
| PyInstaller | 6.22.3, explicit release group |
| setup-uv action | 10.3.0; installs uv 0.13.0 |
| checkout / setup-python actions | Current v7 major tracks retained |
| Superpowers / gz-skills | 7.0.0 / 0.6.0, immutable native sources |
| Starter template | 0.1.0, exact released revision recorded in the bundle |
| Backplane | Immutable deferred source; disabled; later inventory reports installed |
| Windows/macOS 7-Zip | 26.04; coherent Windows EXE/DLL set |
| DSFTool / macOS DDSTool | Existing bytes match current vendor XPTools 24-5 |
| Triangle4XP | Project-owned source; LLVM/CMake build retained |

The hygiene group pins Bandit 1.9.4, cohesion 1.2.0, complexipy 8.0.1,
Cosmic Ray 8.7.0, coverage 7.16.2, deptry 0.25.1, grimp 3.17,
Import Linter 2.15, interrogate 1.7.0, Lizard 1.24.1, pip-audit 2.10.1,
and Vulture 2.16. Radon/Xenon evidence is archived before retirement;
Cosmic Ray replaces the incompatible mutation path. Upstream plugins own
their bundled JavaScript dependencies; installed caches were not patched.

Selected before/after values come from the original committed manifests and
lockfile, rather than from the temporary verification environments:

| Surface | Before | After |
| --- | --- | --- |
| Python / uv_build | 3.13.14 / `>=0.11.21,<0.12` | 3.14.8 / `>=0.13.0,<0.14` |
| NumPy / Pillow | 2.4.4 / 12.2.0 | 2.5.4 / 12.3.0 |
| pyproj / Shapely / Requests | 3.7.2 / 2.1.2 / 2.33.1 | 3.8.0 / 2.2.0 / 2.34.2 |
| aiohttp / Pydantic | 3.14.1 / 2.13.4 | 3.14.5 / 2.14.1 |
| GDAL Linux / Windows / macOS | 3.9.0 / 3.12.2 / 3.12.3 | 3.13.3 on all targets |
| Ruff / ty | 0.15.17 / 0.0.49 | 0.17.0 / 0.0.86 |
| coverage / Lizard | 7.14.1 / 1.22.1 | 7.16.2 / 1.24.1 |
| Superpowers | Vendored 6.0.3 | Native 7.0.0 |
| gz-skills | 0.5.0 | 0.6.0 in the follow-up refresh |
| 7-Zip | 26.01 | 26.04 |

## Binary provenance and compatibility

Python 3.14's deferred annotation evaluation makes four quoted return
annotations unnecessary in the color-correction and texture result models.
The existing Ruff upgrade rules required removing those quotes after selecting
`py314`; changed-file type checks passed. Algorithms and external contracts
remain unchanged. Broader syntax/API modernization was assessed and deferred
because this refresh supplies no consumer requirement for it. Platform GUI
setup deliberately uses a Tk-capable interpreter, including Homebrew Python
on macOS, through uv rather than requiring a uv-managed interpreter everywhere.

Windows GDAL comes from the existing
[geospatial wheel vendor](https://github.com/cgohlke/geospatial-wheels/releases/tag/v2026.8.20).
The CP314 wheel SHA256 is
`7ef82062216a3dc094eafcc517a0a9421f049a6bef33f2cf45f6a61b75e10615`.
The macOS ARM64 NumPy wheel SHA256 is
`ffa6ce09a1c6a08e9667dd9c97aa0b14184e8d18f2a14b78b2a2328c9147f076`.

scikit-fmm has no released Windows CP314 wheel. Its unchanged released sdist
SHA256 `a3208f5f3881e40b7878d1121ba39b8d57f1bc38fb4e5f0d9d1c66a9b007e44f`
was built with MSVC 14.51, Meson 1.12.1, meson-python 0.22.1, wheel 0.48.0,
and NumPy 2.5.4. The resulting project-bundled wheel SHA256 is
`911e7b510cb5fb5ab9e78345fb8f1ae9086cd01c1acfec749a669f826c6cd8bf`.
Its upstream 374 tests passed; signed-distance probes checked finite values
and the expected inside/outside signs.

Linux's native GDAL bootstrap verifies release SHA256
`5e0c388d83da2d686cc00a40272882432cdb54edff43d4af173e532844a0a0ea`
before building into an explicit absolute prefix. Bash syntax and an invalid
prefix negative control passed. Native Linux compilation and macOS execution
remain unverified; the available WSL lacks the native prerequisites. CI now
contains the matching platform setup and must supply that execution evidence.

Official 7-Zip downloads were verified before extraction: Windows installer
SHA256 `d54bf805f9f3704d1e8db2fa3498ae7ef2df0312b40b558e7c71c734430a665d`;
macOS archive SHA256
`bee04358cbcbc7106273cee0e8d72916db2696c48067a3538c34d8cd6fd16578`.
The Windows executable reports 26.04 and loads its matching 26.04 DLL.
Creating and extracting a deterministic archive with that EXE/DLL set also
passed a byte-content comparison.

Legacy NVcompress/NVTT, Medit/freeglut, and Moulinette assets lack a verified
newer drop-in release/provenance chain in this refresh. They are retained,
not certified as current. This is a recorded native-asset verification gap;
release replacement requires authoritative provenance and platform probes.
Windows NVcompress reports NVTT 3.2.5; inactive historical macOS tools remain
source assets. No global LLVM/CMake installation was changed.

## Evidence and remaining checks

The final universal `uv audit --preview-features audit-command --locked
--output-format json` reported 93 audited packages, zero vulnerabilities,
and zero adverse statuses. `uv pip list --outdated` returned no rows in the
all-group Windows environment. The previous Linux GDAL advisory pin is gone;
[SECURITY.md](../SECURITY.md) records its historical advisories.

Python distribution builds and Windows PyInstaller onedir packaging passed.
The built executable printed CLI help and successfully validated the real
`tests/fixtures/build_job_minimal.toml` fixture with JSON `ok: true`. GDAL
MEM-to-GeoTIFF pixels, geotransform and CRS probes, Tk import, and core imports
passed on Python 3.14.8. Packaging outputs and raw task logs remain ignored
under `tmp/`; bundled release utility folders received only verified assets.

The complete routine quality command passed, including native clang-tidy and
the LLVM/CMake Triangle4XP build. Its full run passed 585 tests; the subsequent
Python gate passed 588 after regression tests were added. Final pre-commit
verification then passed all four hooks, including the complete unittest suite,
after the last Vulture and lint-scope negative controls were added. The
[final hook receipt](evidence/2026-10-11-quality-migration/pre-commit.txt) is
archived alongside migration evidence. Full local logs are
`tmp/skills-first-final-quality.log`, `tmp/skills-first-final-python-quality.log`
and `tmp/skills-first-pre-commit.log`. The independent final comparison assessed
257 functions across 22 changed/new Python files and found no increased or
introduced violations of any of the four preserved stricter Lizard dimensions.

The [durable quality migration receipt](evidence/2026-10-11-quality-migration.md)
archives actual analyzer output and source identities. Deep hygiene remains
**FAIL**: absolute complexity debt, four undiscovered inline Protocol methods,
unverified Cohesion metric policy, eight Bandit findings, six Vulture candidates,
and 38.52% branch/statement coverage below the retained 40% threshold. Dependency
audit, dependency usage, import boundaries and docstring presence passed. A fresh
Cosmic Ray compatibility fixture killed all 13 generated mutants; this is not
an application-wide mutation assessment. Ten broader provider/utility Ruff
findings are also retained in the receipt. None of these failures was suppressed
or converted into a clean assessment.

Native Codex installation and fresh-session discovery passed; immutable source
bytes and duplicate prevention were checked. The Claude catalog is supplied but
Claude activation was not performed. See the
[adoption receipt](agents/skills-adoption.md) for ownership, identities and
installation evidence. Linux compilation, macOS execution and the unresolved
native-asset provenance gaps above remain explicit verification limits.

The existing PyInstaller spec copies the complete `Utils` tree, including
local `Utils/build` output and platform-inapplicable utilities. The observed
probe bundle contains these directories. Release documentation requires
platform trimming, but it is not automated in the spec; this packaging-boundary
defect remains tracked here. The probe validates startup and dependencies,
not a distribution-ready release archive.
