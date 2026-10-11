# Skills-first ownership and adoption

Ortho4XP adopts [gz-skills-first-starter](https://github.com/tvproductions/gz-skills-first-starter)
for Superpowers feature workflows and gz-skills engineering disciplines. Read
[the stack instructions](../../AGENTS.skills-first.md) and the
[starter-owned entry](../../.agents/skills/skills-first-start/SKILL.md).
AGENTS.md remains the project authority; TODO.md and GitHub Issue links remain
the backlog, and ROADMAP.md remains direction.

## Sources and scope

[The bundle record](../../.skills-first/bundle.lock.json) records starter
provenance and immutable component revisions. Both native catalogs record
matching sources. Native plugin managers own upstream installations; do not
copy upstream skill trees into project discovery or edit installed caches.
The starter-owned front door is copied unchanged from the recorded starter.
Project operational workflows remain under `.codex/skills/`.

| Component | Selected release | Responsibility |
| --- | --- | --- |
| Superpowers | 7.0.0 | Feature design, planning, implementation, review |
| gz-skills | 0.6.0 | Portable engineering disciplines and engineering skill selection |
| Superpowers Backplane | Deferred; disabled | Future backlog and handoff integration |

The reviewed starter 0.1.0 initially pins Superpowers 6.4.1 and gz-skills 0.5.0.
This dependency refresh
selects verified current published releases through its documented
project-specific catalog route, named `ortho4xp-skills-first`. The shared
starter is unchanged. A future shared-baseline update should reconcile the
catalog and bundle together rather than add duplicate skill discovery.

Codex enablement lives in `.codex/config.toml`. The old global gz-skills source
and xplane-health sources are disabled only in this project. Newly installed
Ortho4XP plugin entries are disabled in user configuration and enabled here;
other projects' settings remain intact. Backplane is cataloged but disabled
without an installation request. Native inventory currently reports Backplane
installed but disabled; this refresh neither installed nor enabled it.
Claude's catalog is supplied for portability; native Claude
installation is a separate host operation and is not implied by this catalog.

The Python engineering binding lives at the reviewed starter revision and is
applied through [the project Python binding](python-engineering.md). Domain
dependencies, native utilities, application imports, data, release structure,
and numerical behavior remain Ortho4XP-owned. No lite/heavy profile or gzkit
lifecycle is selected.

The copied starter 0.1.0 guidance describes freshness review and template/plugin
inventory as upstream proposals because its own baseline pins gz-skills 0.5.0.
The project's reviewed 0.6.0 override now supplies those capabilities. Its
profile defaults yield to this approved Python 3.14 starter standard: retain
the selected tool groups and retired-tool decisions, and do not initialize or
select a lite/heavy profile as a dependency-update side effect. See the
[follow-up refresh receipt](../dependency-refresh-2026-10-11-follow-up.md).

## Native Codex installation

From the trusted repository root, inventory native marketplaces and plugins
before installation. Then use the verified manager commands:

```powershell
codex plugin marketplace list --json
codex plugin list --json
codex plugin marketplace add ./ --json
codex plugin add superpowers@ortho4xp-skills-first --json
codex plugin add gz-skills@ortho4xp-skills-first --json
```

The add command enables a new plugin at user scope. Restrict newly added
entries to `enabled = false` in user configuration while retaining this
project's `enabled = true` overrides; preserve existing selections. Native
marketplace registration records the resolved checkout path outside Git.
Register the catalog again after moving the checkout. Project settings require
a trusted project. See [official Codex plugin configuration](https://developers.openai.com/plugins/build/plugins).

Verify source/configuration coherence with:

```powershell
uv run python scripts/check_skills_stack.py
```

Installed source provenance and actual fresh-session skill discovery require
separate checks. A coherent catalog cannot prove either. The relevant entries
are `skills-first-start`, `superpowers:using-superpowers`, and
`gz-skills:gzs-router`; ensure their paths refer to the selected native sources.

## Updates and rollback

Follow the recorded starter's
[adoption guide](https://github.com/tvproductions/gz-skills-first-starter/blob/4acc41595b673faabdbe9be8d38b62755048ab93/docs/adoption.md).
Check live published releases, review source changes, and update the bundle
and both catalogs coherently. Use native managers' supported operations and
verify installed bytes and new-session discovery. Keep Backplane disabled
until separately approved readiness and adoption.

The retired vendored source is recoverable from Git history; a task-local
snapshot was also preserved under ignored `tmp/` during migration. Rollback
must restore one coherent discovery source and its matching configuration,
not enable both native and copied upstream skills. Never remove shared caches
manually to repair this project's setup.
