# Skills-first development stack

Start with `.agents/skills/skills-first-start/SKILL.md` for task routing and
orientation. This project records sources in `.skills-first/bundle.lock.json`.
Superpowers supplies feature design and implementation; gz-skills supplies
portable engineering disciplines. Superpowers Backplane remains pinned for
future adoption but is disabled by default because readiness is incomplete.
Use existing project backlog and handoff practices in the meantime.

Project AGENTS.md, domain authorities and verification commands remain binding.
Keep project-owned operational skills, supporting domain code, and records
separate. Confirm actual discovery before invoking upstream entry skills;
configuration does not prove loading. Preserve independently versioned upstream
sources and avoid duplicate plugin/copied-skill discovery.

No lite/heavy profile or gzkit lifecycle is selected by the starter. For adoption,
structural backporting, updates and verification, use the reviewed starter at
https://github.com/tvproductions/gz-skills-first-starter. Existing project instructions
and app architecture are preserved until specific changes are authorized.

For projects adopting the starter's Python baseline, use the latest stable
release within each explicitly selected Python/tool release family. Python's
family is 3.14.x: verify the latest patch from official sources at setup/adoption
and scoped maintenance, then pin that exact patch for local execution and CI.
An already-installed version or a `3.14` selector does not prove freshness.
Keep tools pinned/locked after verification; changing families requires separate
review. Record any compatibility exception with evidence and a revisit condition,
including the documented XPPython3 host exception. Preserve project dependencies
and authorities, report adoption gaps, and follow the reviewed starter's Python
engineering skill. This rule does not authorize automatic upgrades or schedules.

At adoption and scoped maintenance, check this starter template, Superpowers,
Superpowers Backplane and gz-skills independently for upstream updates. Compare
the recorded starter/component SHAs with official published releases; where no
release exists, distinguish a reviewed published commit from a stable release.
Record the checked date, selected/latest versions or SHAs, compatibility evidence
and adopt/defer decisions. Review configuration changes before using native
update operations, preserve project additions and overrides, keep rollback pins,
and verify actual loaded sources in a fresh session. Track SP-BP freshness while
it is deferred; keep it disabled until readiness and explicit adoption are
established. Use the reviewed starter's `docs/adoption.md` maintenance procedure.

Generic maintenance belongs in gz-skills: use its discovered
`gzs-update-dependencies` for authorized dependency/tool updates and
`gzs-dependency-risk-audit` for risk assessments. The starter supplies baseline
policy and stack-specific binding guidance. Do not create a duplicate local
maintenance skill or generic freshness reporter. Freshness-only reporting and
expanded template/plugin inventory are upstream proposals; verify release support
before claiming those capabilities exist.

Track the adopted starter's own version and exact SHA in its bundle lock,
independently of app and upstream plugin versions. Compare reviewed template
releases and their changelog using the starter's `docs/versioning.md` policy.
A version label is not publication or readiness proof. Reconcile older
unversioned records without inventing historical provenance or overwriting
project changes.
