# Skills-first adoption receipt — 2026-10-11

The user approved the full staged design in
[the alignment specification](../superpowers/specs/2026-10-11-skills-first-alignment-design.md).
The initial source was starter commit `4acc41595b673faabdbe9be8d38b62755048ab93`.
The initial [source record](../../.skills-first/bundle.lock.json) selected released
Superpowers 7.0.0 and gz-skills 0.5.0 through the starter's adopter-owned catalog
route. Backplane remained deferred and disabled, without an installation request.

## Observed native state

This section records the initial adoption. The subsequent
[follow-up refresh](../dependency-refresh-2026-10-11-follow-up.md) advances the
starter to 0.1.0 and gz-skills to 0.6.0, with new installation/discovery evidence.
The current bundle record is authoritative for selected revisions. The later
native inventory reports Backplane installed but disabled; no Backplane install
or enable action was performed during the refresh.

Codex CLI 0.162.1 registered this checkout's catalog and installed both plugins
through `codex plugin` commands. Installed skill bytes, normalized only for
line endings, matched the reviewed release sources: 74 Superpowers files and
35 gz-skills files. Newly created user entries were disabled; project overrides
enable them. Existing user selections were preserved, and alternate sources
were disabled only in this project.

A fresh Codex app-server process received `skills/list` with this checkout as
its cwd and `forceReload: true`. It returned the project `skills-first-start`
entry and the selected native `superpowers:using-superpowers` and
`gz-skills:gzs-router` paths, without discovery errors or duplicate upstream
sources. The raw receipt is task-local `tmp/skills-first-discovery.json`.
Claude's coherent catalog is supplied; Claude installation was not performed.

The old vendor tree was unchanged when archived to ignored
`tmp/superpowers-before-native-migration.tar`, then retired after replacement
verification. Git history remains the durable recovery source. The starter
entry and `AGENTS.skills-first.md` are unchanged starter copies. Project
authority and operational skills remain project-owned.

## Project adaptation

Python 3.14.8 and the starter's routine/deep quality split are adopted while
retaining scientific dependencies, `unittest`, numerical behavior, native
LLVM/CMake checks, release assets, TODO/GitHub links, and generated-data rules.
See [Python engineering](python-engineering.md) and
[dependency refresh evidence](../dependency-refresh-2026-10-11.md) for runtime
and quality verification. No lite/heavy profile or gzkit lifecycle is selected.

Future adoption must refresh both catalogs and the source record together,
review upstream changes, and separately verify installed provenance and fresh
discovery. [The stack guide](skills.md) contains the supported commands and
rollback rules.
