# TUI plugin warning analysis — 2026-10-11

The user reported 14 gz-skills warnings and supplied this example:

```text
C:\Users\Jeff\.codex\plugins\cache\ortho4xp-skills-first\gz-skills\0.6.0\skills\gzs-hexagonal-architecture-audit\SKILL.md: failed to read file: The system cannot find the path specified. (os error 3)
```

This is a native cached-plugin file-read failure, not a request to vendor skills
or evidence that individual skills should not appear inside a plugin. The
selected plugin identity is `gz-skills@ortho4xp-skills-first`, version 0.6.0.

Observed current state:

- The exact reported file exists and was read successfully: 8,427 bytes,
  creation/last-write UTC 2026-10-11 21:47:52.
- All 42 installed canonical resource files match the reviewed tagged release,
  normalizing only line endings.
- Repeated fresh app-server `skills/list` requests with project cwd and
  `forceReload: true` load all 19 canonical entries with zero discovery errors.
  The hexagonal audit entry resolves to the exact reported path and native
  plugin identity; no duplicate gz-skills entries are present.
- A fresh Codex 0.162.1 TUI started in this repository without displaying the
  reported 14 warnings; `/skills` listed the GovZero entries. No model prompt
  was submitted, and the diagnostic TUI was closed.

The reported missing-path condition is not currently reproducible. An earlier
scan during cache installation/replacement or retained TUI diagnostic state is
consistent with these observations, but the original warning timestamp and
remaining 13 messages were not supplied. Their historical cause is unproven.
Do not claim all reported warnings fixed solely from a successful new loader.

The user subsequently reported that the warnings appear to be gone. This agrees
with fresh loading succeeding and supports retained diagnostic state as the
explanation, while leaving the original transient cause unproven.

The smallest next check is to exit and resume the affected TUI session, forcing
a new process to discover the current plugin files. `codex resume` provides the
existing-session picker; prefer selecting that session over `--last`, because
the diagnostic TUI created a newer empty session. If the warnings recur, retain
their complete text and timestamp before any reinstall or cache cleanup.

Separate probes emitted two icon-path metadata warnings under
`codex_skills::interface`; these do not match the reported missing-file warning.
They are not evidence of a gz-skills failure. A temporary process-only override
did not eliminate them, so attribution was not established by that experiment.
No installed cache, saved plugin configuration or application code was changed
for this analysis. Diagnostic scripts/logs remain under ignored `tmp/`.
