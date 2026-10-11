---
name: skills-first-start
description: Orient an agent in a skills-first project, choose among project workflows, Superpowers and gz-skills, or guide adoption and structural backporting of the starter.
---

# Start a skills-first task

Read the project's AGENTS.md and referenced authorities first. Identify the user's
actual task and available skills; recommend the smallest useful workflow and then
continue the authorized task. This skill is orientation, not another lifecycle.
Do not invoke every audit or reinterpret a small task as an architecture project.

For application operations, follow the project's own operational skills. For
engineering skill selection, prefer the discovered gz-skills `gzs-router` and
its maintained catalog; do not recreate that catalog here. For feature design
and implementation, use the installed SP `using-superpowers` entry and its
workflow. For adoption or structural backporting, read the starter's
`adopt-skills-stack` skill and `docs/backport.md` from a reviewed checkout.
For Python engineering, read `skills/python-engineering/SKILL.md` from the
reviewed starter checkout; it binds the runtime, idioms, routine tools and
on-demand hygiene selections. This path is not relative to the copied adopter
front door. Do not claim native discovery of that skill without evidence.
Backlog and handoff continuity stay with existing project practice while SP-BP,
an expected addition to the target stack, is deferred.

This is a bootstrap pointer. Broader cross-stack routing in `gzs-router` is a
future upstream integration; do not claim that the pinned router orchestrates
SP or starter adoption. Once that routing is shipped and verified, simplify
this pointer further rather than maintaining a parallel engineering catalog.

Check actual skill discovery before claiming an entry is available. A pinned
catalog or configuration is not an installed skill. If the target skill is
missing, identify the gap and use its reviewed source instructions when useful;
do not silently install it. The starter's own adoption skill can be read from a
reviewed checkout when it is not exposed through native discovery.

The maintained guidance lives at https://github.com/tvproductions/gz-skills-first-starter.
Use the revision recorded in `.skills-first/bundle.lock.json` when present.
From that reviewed checkout, `uv run --python 3.14.8 starter.py backport --project <root>` gives
a read-only starting assessment. Build a source-to-target mapping before changes;
retain project authorities, domain rules, records, and working verification.

SP and gz-skills are the current default pair. SP-BP stays cataloged but disabled
until readiness and explicit adoption are established. Do not invent its missing
issue automation or replace project backlog authority with local starter code.
No gz-skills lite/heavy profile is inferred here. Upstream main proposals are
not capabilities in the pinned release. Keep upstream sources independently
versioned, and never install their skills through duplicate discovery paths.

For current SP/gz-skills releases or development snapshots, follow the reviewed
starter's `docs/adoption.md` update procedure. Query upstream before saying
“latest”; preserve exact source pins and verify actual loading after an update.
The same maintenance review includes the starter template itself and deferred
SP-BP. Check all four independently at adoption and scoped maintenance; record
dates, upstream evidence and adopt/defer decisions. A newer SP-BP revision does
not authorize enabling it. Preserve project additions, overrides and rollback
pins when reconciling changes from a newer reviewed starter.

Route authorized dependency/tool updates to gz-skills `gzs-update-dependencies`
and dependency-risk assessments to `gzs-dependency-risk-audit`. The starter's
Python skill supplies policy, not a parallel generic maintenance workflow.
Freshness-only reporting and expanded template/plugin inventory remain upstream
enhancement proposals; do not invent a local skill or claim they have shipped.
