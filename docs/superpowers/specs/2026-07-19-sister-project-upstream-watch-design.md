# Sister-Project Upstream Watch Design

## Purpose

Ortho4XP uses `Ypsos/ORTHO4XP_V3` as a continuing source of field evidence,
workflow ideas, and possible improvements. The project must detect that author's
progress reliably without assuming that upstream code is suitable for direct
adoption. The local fork remains strictly X-Plane 12 only.

This design establishes a hybrid chore: GitHub performs lightweight scheduled
detection and notification, while a deterministic local command produces the
evidence used for human engineering review. Upstream changes enter this
repository only after they are reproduced where practical, covered by local
tests, and implemented through this project's architecture.

## Authoritative Source and Passive Fork

The chore recognizes these repositories in different roles:

- Authoritative source: `https://github.com/Ypsos/ORTHO4XP_V3`
- Passive synchronization fork: `https://github.com/tvproductions/ORTHO4XP_V3`

The authoritative source determines whether new work is available for review.
The `tvproductions` fork is not an independent development line. Its status is
an informational checkpoint showing whether GitHub's passive fork has been
synchronized with the author. Synchronizing that fork does not mark author
changes as reviewed, and leaving it behind does not block an audit or baseline
advancement. An ahead or diverged passive fork is a configuration anomaly to
investigate, not a normal engineering state.

The committed state records the monitored branches, the last fully reviewed
author commit, the audit date, the audit identifier, a digest of the reviewed
change manifest, and a schema version. A reviewed baseline may advance only
through a completed audit. Passive-fork state is observed at runtime and is not
part of the accepted engineering baseline.

## Components

### Scheduled Detector

`.github/workflows/upstream-watch.yml` runs weekly and through manual workflow
dispatch. It has repository-contents read permission and issues write
permission. It compares remote heads with the committed state and creates,
reopens, updates, or resolves one issue labeled `upstream-watch`.

The detector reports these states separately:

- author changes awaiting review;
- passive fork synchronized or behind;
- unexpected passive-fork commits or divergence;
- rewritten or non-ancestor author history;
- invalid or stale audit state;
- no outstanding changes.

Normal passive-fork lag is informational and does not keep the engineering
review issue open after the author baseline is current. Unexpected commits or
divergence on the passive fork do keep the issue open as a configuration
anomaly.

The detector never modifies `TODO.md`, the audit ledger, or the reviewed
baseline. Scheduled failures do not block normal push or pull-request CI.

### Local Audit Command

`scripts/upstream_watch.py` provides cross-platform commands to:

- check remote heads against committed state;
- compare an explicit reviewed base and candidate head;
- produce a structured audit report;
- validate that every detected path has a disposition;
- validate the ledger and state transition;
- advance the reviewed state only after a complete audit.

The command uses explicit SHAs in reports and state transitions. Branch names
are discovery inputs, not evidence identifiers. A history rewrite stops the
incremental audit and requires a full-tree comparison against the reviewed
tree.

### State and Ledger

`.github/upstream-watch.json` is the machine-readable configuration and
accepted-baseline state. It contains no credentials or mutable remote data
beyond observed commit identifiers and completed-audit metadata.

`docs/upstream/ORTHO4XP_V3-audit.md` is the durable review ledger. Each entry
records:

- audit identifier and date;
- exact base and head SHAs;
- passive-fork synchronization state observed during the audit;
- commit list and authorship;
- findings and affected paths;
- disposition and rationale for every finding;
- X-Plane 12 compatibility assessment;
- verification evidence;
- linked TODO identifiers or GitHub Issues for accepted work.

Generated raw reports remain local files or CI artifacts. The state-advance
operation consumes the raw report, verifies complete coverage, records its
digest and path count, and requires the matching ledger entry before updating
the committed baseline.

## Audit Evidence

An audit report contains:

- base and head SHAs and ancestry status;
- commit metadata;
- added, modified, renamed, copied, and deleted paths;
- file and line statistics;
- dependency-file changes;
- provider and regional-data changes;
- Python syntax results from parsing without importing upstream modules;
- targeted static-analysis results;
- X-Plane 11 and X-Plane 12 compatibility signals;
- authoritative-source and passive-fork synchronization status.

Every changed path must be assigned to a finding or to an explicit
`reviewed-no-action` record. Each finding has exactly one disposition:

- `adopt`: behavior can be integrated without architectural translation;
- `reimplement`: retain the behavior but implement it through local contracts;
- `investigate`: evidence is insufficient for a final decision;
- `reject`: behavior conflicts with project requirements or quality standards;
- `superseded-locally`: the local implementation already satisfies or exceeds
  the relevant behavior.

An `investigate` disposition blocks advancement of the reviewed baseline for
the affected path. Accepted work must link to a TODO item or GitHub Issue.
Rejected and superseded work retains its rationale to prevent repeated review
without new evidence.

## Adoption Standard

For candidate behavior, the engineering review follows this sequence:

1. Extract the intended behavior and the real-world problem it addresses.
2. Reproduce that problem in this active Ortho4XP repository where practical.
3. Add a failing deterministic `unittest` or fixture before changing behavior.
4. Implement the solution through local architecture and dependency policy.
5. Compare observable results with the sister-project behavior or supplied
   imagery.
6. Record the result and evidence in the ledger and linked work item.

Large upstream modules are not imported merely because they run in the sister
project. French regional knowledge and real-world coastal imagery behavior are
valuable evidence, but provider legality, credential requirements, portability,
resource use, error handling, and strict X-Plane 12 compatibility remain local
acceptance gates.

## Security and Failure Handling

Upstream repositories are untrusted data. The chore does not execute upstream
Python, installers, shell scripts, Git hooks, or submodules. Syntax checks parse
source files without importing them. Static-analysis tools inspect files only.

Remote API, authentication, pagination, rate-limit, malformed-state, clone, and
Git failures are reported distinctly and return failure without changing the
reviewed state. Reports redact credentials and avoid embedding authenticated
remote URLs. Temporary repositories and reports are removed by the command
when it created them, except when an explicit output path requests retention.

The local command uses these exit statuses:

- `0`: the author state is valid and no engineering review is outstanding;
- `1`: an operational or validation failure prevented a trustworthy result;
- `2`: author changes require review, with passive-fork status included in the
  report;
- `3`: the author baseline is current but the passive fork has unexpected
  commits or has diverged;
- `4`: rewritten author history requires manual intervention and a full-tree
  audit.

Normal passive-fork lag does not change exit status `0` or prevent baseline
advancement. The detector resolves the tracking issue only for exit status `0`.
Tests assert the status precedence as well as each individual status.

## Testing

`tests/test_upstream_watch.py` uses standard-library `unittest`, temporary local
Git repositories, and mocked GitHub responses. It performs no network access.
Coverage includes:

- no-change and new-commit detection;
- additions, modifications, renames, copies, and deletions;
- author ancestry and rewritten history;
- passive fork synchronized and normally behind states;
- unexpected passive-fork commits and divergence;
- API pagination, rate limits, and malformed responses;
- incomplete path coverage and invalid dispositions;
- prohibited baseline advancement;
- valid state advancement and manifest digest recording;
- issue creation, update, reopen, and resolution decisions;
- stable exit-status semantics;
- redaction and rejection of unsafe state values.

Workflow configuration receives a syntax and permissions review. The shared
Python core, rather than workflow-specific shell logic, owns comparison and
state-transition semantics so local and scheduled behavior cannot drift.

## Backlog Integration

The implementation rewrites `TODO-044` and `TODO-045` so their acceptance
criteria stand independently of sister-project files that no longer exist at
the author's current head. Historical source commits remain linked as research
evidence where they can be identified.

Future upstream audits may create or refine TODO items only through a reviewed
ledger decision. The automated detector never edits backlog priorities.

## Completion Criteria

The chore is complete when:

- scheduled and manually dispatched detection report author progress and
  passive-fork synchronization state;
- the local command produces reproducible reports for explicit SHA ranges;
- incomplete audits cannot advance the committed baseline;
- a completed audit updates state and retains a durable ledger entry;
- rewritten author history and passive-fork anomalies are visibly
  distinguished;
- all tests pass without network access;
- stale backlog references are independently specified;
- repository quality checks pass.
