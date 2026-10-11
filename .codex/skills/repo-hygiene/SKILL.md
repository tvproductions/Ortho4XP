---
name: repo-hygiene
description: Run Ortho4XP build readiness, workspace tidiness, generated-artifact and toolchain validation. Deep analyzer assessment requires an explicit request.
---

# Repo Hygiene

Use pinned Python 3.14.8 through uv, unittest, project-locked Ruff and ty, and
LLVM/Clang CMake presets. Keep domain dependencies and packaging data intact.

```powershell
uv run python .codex/skills/repo-hygiene/scripts/hygiene.py --quick
uv run python .codex/skills/repo-hygiene/scripts/hygiene.py --full
```

The quick workflow inspects state, builds the distribution, runs unittest,
Ruff, reviewed-baseline/changed-file ty and changed-file formatting, and scans
for obsolete setup instructions. Full adds changed-line clang-format,
clang-tidy configuration and changed-line analysis, and native CMake build.

These readiness checks do not run deep analyzers. Explicitly requested hygiene
uses the maintenance-qa command documented in
[Python engineering](../../../docs/agents/python-engineering.md).

Generated data stays uncommitted: .venv, Utils/build, OSM_data, Masks,
Orthophotos, Elevation_data, Geotiffs, Tiles, tmp, yOrtho4XP_Overlays and
Ortho4XP.cfg. Do not delete user data automatically. Root dependency declarations
belong in pyproject.toml and uv.lock; temporary hash-preserving audit exports are
valid verification artifacts. Do not introduce manual environment setup,
alternate test runners or an MSVC-first release-build policy.

TODO.md identifiers and GitHub links remain the executable queue; ROADMAP.md
remains rationale. If a prerequisite blocks implementation, phase or reorder
TODO.md while preserving completed status and identifiers.
