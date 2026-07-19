# Sister-Project Upstream Watch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hybrid scheduled and local audit chore that detects new work in `Ypsos/ORTHO4XP_V3`, records complete human dispositions, and treats `tvproductions/ORTHO4XP_V3` only as a passive synchronization fork.

**Architecture:** A thin command wrapper delegates to a standard-library Python package split into validated models, local Git inspection, audit generation, ledger validation, GitHub issue management, and CLI orchestration. GitHub Actions runs only the lightweight detector; substantive audits run locally against explicit SHAs and never execute upstream content. Machine state is JSON, human decisions live in Markdown with embedded canonical JSON records, and baseline updates are atomic and coverage-gated.

**Tech Stack:** Python 3.13, standard-library `argparse`, `ast`, `dataclasses`, `hashlib`, `json`, `subprocess`, `tempfile`, and `urllib`; Git; GitHub Actions; repository `unittest`, Ruff, and ty tooling.

## Global Constraints

- The active Ortho4XP repository remains strictly X-Plane 12 only.
- `Ypsos/ORTHO4XP_V3` is the only engineering audit source.
- `tvproductions/ORTHO4XP_V3` is a passive synchronization fork; normal lag is informational and never blocks baseline advancement.
- Never execute upstream Python, installers, scripts, hooks, or submodules.
- Tests perform no network access and require no X-Plane installation or imagery provider.
- Use Python 3.13.x through `uv`, standard-library `unittest`, Ruff, and ty.
- Do not add runtime dependencies.
- Use explicit 40-character Git SHAs in evidence and accepted state.

---

## File Map

- Create `scripts/__init__.py`: marks repository maintenance scripts as an importable package.
- Create `scripts/upstream_watch.py`: thin executable entry point.
- Create `scripts/upstream_watch_core/__init__.py`: exports the supported maintenance API.
- Create `scripts/upstream_watch_core/models.py`: validated state, report, decision, and status models plus canonical JSON.
- Create `scripts/upstream_watch_core/git_repo.py`: constrained Git subprocess runner and repository comparisons.
- Create `scripts/upstream_watch_core/audit.py`: explicit-range manifest generation and non-executing source inspection.
- Create `scripts/upstream_watch_core/ledger.py`: structured Markdown record parsing, coverage validation, digesting, and atomic state advancement.
- Create `scripts/upstream_watch_core/github_api.py`: minimal GitHub REST transport and single-issue lifecycle.
- Create `scripts/upstream_watch_core/cli.py`: command parsing, orchestration, rendering, and exit-code mapping.
- Create `.github/upstream-watch.json`: repository configuration and accepted author baseline.
- Create `.github/workflows/upstream-watch.yml`: weekly and manual detector.
- Create `docs/upstream/ORTHO4XP_V3-audit.md`: durable review ledger.
- Create `tests/test_upstream_watch.py`: all network-independent behavioral coverage.
- Modify `tests/_path.py`: add repository root for importing `scripts`.
- Modify `.github/workflows/ci.yml`: lint and type-check maintained scripts.
- Modify `.gitignore`: ignore local `.upstream-watch/` raw reports.
- Modify `docs/development.md`: document check, audit, validate, and accept commands.
- Modify `TODO.md`: harden stale `TODO-044` and `TODO-045` requirements and record `TODO-041-3` completion evidence.

### Task 1: Validated State and Status Contracts

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/upstream_watch_core/__init__.py`
- Create: `scripts/upstream_watch_core/models.py`
- Modify: `tests/_path.py`
- Create: `tests/test_upstream_watch.py`

**Interfaces:**
- Produces: `WatchExit`, `RepositoryRef`, `AcceptedBaseline`, `WatchState`, `PathChange`, `CommitRecord`, `InspectionResult`, `ForkState`, `AuditReport`, `FindingRecord`, `ReviewedNoActionRecord`, `canonical_json_bytes()`, and `load_state()`.
- `WatchExit` values are `CURRENT=0`, `ERROR=1`, `REVIEW_REQUIRED=2`, `FORK_ANOMALY=3`, and `HISTORY_REWRITE=4`.
- All SHAs are lowercase 40-character hexadecimal strings; repository slugs are `owner/name` without schemes or credentials.

- [ ] **Step 1: Add repository-root test imports and failing model tests**

Add `ROOT_DIR` to `sys.path` in `tests/_path.py`. In `tests/test_upstream_watch.py`, add tests that load a valid state, reject short SHAs, reject authenticated URLs in repository fields, reject an unknown schema version, and assert canonical JSON stability:

```python
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _path import ROOT_DIR  # noqa: F401
from scripts.upstream_watch_core.models import (
    WatchExit,
    canonical_json_bytes,
    load_state,
)


BASE_SHA = "4ca0a8d404b078ad899979bafde84769a0fb235b"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class WatchStateTests(unittest.TestCase):
    def _state(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "author": {
                "repository": "Ypsos/ORTHO4XP_V3",
                "branch": "ORTHO4XP_V3",
            },
            "passive_fork": {
                "repository": "tvproductions/ORTHO4XP_V3",
                "branch": "ORTHO4XP_V3",
            },
            "baseline": {
                "reviewed_sha": BASE_SHA,
                "audit_id": "bootstrap-existing-baseline",
                "audit_date": "2026-06-16",
                "manifest_sha256": EMPTY_SHA256,
                "path_count": 0,
            },
        }

    def test_load_state_accepts_valid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "state.json")
            path.write_text(json.dumps(self._state()), encoding="utf-8")
            state = load_state(path)
        self.assertEqual(state.baseline.reviewed_sha, BASE_SHA)
        self.assertEqual(WatchExit.REVIEW_REQUIRED, 2)

    def test_canonical_json_is_order_independent(self) -> None:
        self.assertEqual(canonical_json_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}')
```

- [ ] **Step 2: Run the model tests and confirm the import failure**

Run: `uv run python -m unittest tests.test_upstream_watch.WatchStateTests -v`

Expected: FAIL because `scripts.upstream_watch_core.models` does not exist.

- [ ] **Step 3: Implement immutable models and validation**

Use frozen, slotted dataclasses and explicit `from_dict()` methods. Implement canonical JSON with `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")`. Reject booleans where integers are expected, control characters in branches, path traversal, non-HTTPS API URLs, repository values containing `://` or `@`, invalid dates, unknown keys, duplicate changed paths, and unknown enum values. Define `AuditReport.manifest_payload()` to omit `generated_at` and inspection tool versions so its digest remains reproducible.

The central validators must have these signatures:

```python
def validate_sha(value: object, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise StateValidationError(f"{field} must be a lowercase 40-character SHA")
    return value


def validate_repository(value: object, field: str) -> str:
    if not isinstance(value, str) or REPOSITORY_RE.fullmatch(value) is None:
        raise StateValidationError(f"{field} must use the owner/name form")
    if "://" in value or "@" in value:
        raise StateValidationError(f"{field} must not contain a URL or credentials")
    return value


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def load_state(path: Path) -> WatchState:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StateValidationError(f"Could not load state from {path.name}") from exc
    return WatchState.from_dict(payload)


def load_report(path: Path) -> AuditReport:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportValidationError(f"Could not load report from {path.name}") from exc
    return AuditReport.from_dict(payload)
```

Define `REPOSITORY_RE`, `StateValidationError`, and `ReportValidationError` in
the same module. Do not use assertions for runtime validation.

- [ ] **Step 4: Run focused tests, Ruff, format, and ty**

Run:

```powershell
uv run python -m unittest tests.test_upstream_watch.WatchStateTests -v
uv run ruff check scripts tests/test_upstream_watch.py
uv run ruff format --check scripts tests/test_upstream_watch.py tests/_path.py
uv run ty check scripts tests/test_upstream_watch.py
```

Expected: model tests pass and all three static checks exit `0`.

- [ ] **Step 5: Commit the state contract**

```powershell
git add scripts tests/_path.py tests/test_upstream_watch.py
git commit -m "feat: define upstream watch state contract"
```

### Task 2: Safe Local Git Comparison

**Files:**
- Create: `scripts/upstream_watch_core/git_repo.py`
- Modify: `tests/test_upstream_watch.py`

**Interfaces:**
- Consumes: validated `RepositoryRef`, `PathChange`, and `CommitRecord` models.
- Produces: `GitCommandError`, `GitRunner.run(args, cwd=None)`, `FetchedRepositories`, `fetch_repositories()`, `classify_author_history()`, `classify_passive_fork()`, `list_commits()`, `list_changes()`, and `read_blob()`.
- Git arguments are fixed lists; repository slugs are converted internally to `https://github.com/{slug}.git` after validation.

- [ ] **Step 1: Write failing temporary-repository tests**

Add `GitRepositoryTests` with a helper that runs local Git with `user.name=Upstream Watch Tests` and `user.email=upstream-watch@example.invalid`. Build one bare author remote and one bare passive-fork remote from temporary working repositories. Cover equal heads, author fast-forward, passive fork behind, passive fork unexpectedly ahead, passive-fork divergence, deleted paths, and rewritten author history.

The key assertions are:

```python
self.assertEqual(classify_author_history(runner, BASE_SHA, head), WatchExit.REVIEW_REQUIRED)
self.assertEqual(classify_passive_fork(runner, author_head, behind_head), ForkState.BEHIND)
self.assertEqual(classify_passive_fork(runner, author_head, ahead_head), ForkState.UNEXPECTED_COMMITS)
self.assertEqual(classify_passive_fork(runner, author_head, divergent_head), ForkState.DIVERGED)
```

- [ ] **Step 2: Run the Git tests and confirm the missing-module failure**

Run: `uv run python -m unittest tests.test_upstream_watch.GitRepositoryTests -v`

Expected: FAIL because `git_repo.py` does not exist.

- [ ] **Step 3: Implement the constrained Git runner and comparisons**

`GitRunner.run()` executes `git` with `check=False`, captured UTF-8 text, `stdin=DEVNULL`, `GIT_TERMINAL_PROMPT=0`, and no shell. It raises `GitCommandError` containing the redacted argument list and stderr on nonzero status. `fetch_repositories()` initializes a temporary bare repository and fetches exact author, passive-fork, base, and candidate refs without tags or submodules. Use `git merge-base --is-ancestor` in both directions for classifications.

Apply status precedence exactly: an operational failure returns `ERROR`; a
non-ancestor author baseline returns `HISTORY_REWRITE`; an author fast-forward
returns `REVIEW_REQUIRED` regardless of passive-fork state; when the author is
current, unexpected passive-fork commits or divergence return `FORK_ANOMALY`;
otherwise equal or normally behind passive-fork state returns `CURRENT`.

Use NUL-delimited output for paths:

```python
name_status = runner.run(
    ["diff", "--name-status", "-z", "--find-renames", "--find-copies", base, head],
    cwd=repo,
)
numstat = runner.run(["diff", "--numstat", "-z", base, head], cwd=repo)
```

Reject absolute paths, `..` components, NULs, and paths that cannot be decoded. `read_blob()` uses `git show {sha}:{path}` with a validated SHA and repository-relative path; it never checks out or imports content.

- [ ] **Step 4: Run focused and static checks**

Run:

```powershell
uv run python -m unittest tests.test_upstream_watch.GitRepositoryTests -v
uv run ruff check scripts tests/test_upstream_watch.py
uv run ruff format --check scripts tests/test_upstream_watch.py
uv run ty check scripts tests/test_upstream_watch.py
```

Expected: all commands exit `0`.

- [ ] **Step 5: Commit Git comparison support**

```powershell
git add scripts/upstream_watch_core/git_repo.py tests/test_upstream_watch.py
git commit -m "feat: compare upstream Git histories safely"
```

### Task 3: Deterministic Audit Reports Without Upstream Execution

**Files:**
- Create: `scripts/upstream_watch_core/audit.py`
- Modify: `tests/test_upstream_watch.py`

**Interfaces:**
- Consumes: explicit base/head SHAs and `git_repo` functions.
- Produces: `build_audit_report()`, `inspect_python_blob()`, `classify_change_signals()`, `write_report()`, and `manifest_sha256()`.
- `build_audit_report(state, base_sha, head_sha, generated_at, runner) -> AuditReport` never imports or executes upstream content.

- [ ] **Step 1: Write failing report and security tests**

Add `AuditReportTests` that commit a Python file containing top-level `raise RuntimeError("must not execute")`, an invalid Python file, a provider `.lay`, and an XP11+bathy string. Verify the audit reports syntax success/failure, dependency/provider/XP12 signals, stable path ordering, commit authorship, and identical manifest digests across different `generated_at` values.

```python
report = build_audit_report(state, base_sha, head_sha, "2026-07-19T12:00:00Z", runner)
self.assertEqual(report.changes[0].path, "Providers/Global/Test.lay")
self.assertIn("xp11-bathy", report.compatibility_signals)
self.assertEqual(report.manifest_sha256(), report_with_later_timestamp.manifest_sha256())
```

- [ ] **Step 2: Run report tests and confirm failure**

Run: `uv run python -m unittest tests.test_upstream_watch.AuditReportTests -v`

Expected: FAIL because `audit.py` does not exist.

- [ ] **Step 3: Implement report construction and source inspection**

Parse changed `.py` blobs with `ast.parse(blob.decode("utf-8-sig"), filename=path)` and record syntax errors as data. Never call `compile`, `exec`, `eval`, `runpy`, import machinery, or upstream entry points. Classify dependency files by exact names (`pyproject.toml`, `uv.lock`, `requirements*.txt`, `environment*.yml`), provider files by the `Providers/` prefix, and XP compatibility from case-insensitive token matches with file/line evidence.

Derive `audit_id` deterministically as
`ypsos-{base_sha[:12]}-{head_sha[:12]}`. The manifest digest covers schema
version, audit ID, base/head SHAs, ancestry, commit records, and sorted path
changes including rename/copy origins and line statistics. It excludes
`generated_at`, passive-fork observations, syntax/static-analysis observations,
and tool versions so repeating the same Git range has the same accepted
change-manifest digest.

For targeted Ruff analysis, materialize only changed Python blobs under a temporary directory and invoke the already-installed `ruff` executable with:

```python
[ruff_executable, "check", "--no-cache", "--output-format=json", temporary_root]
```

Record `available=false` when Ruff is absent and treat malformed Ruff JSON as an operational audit error. Write reports atomically with a trailing newline and canonical key ordering.

- [ ] **Step 4: Run focused and static checks**

Run:

```powershell
uv run python -m unittest tests.test_upstream_watch.AuditReportTests -v
uv run ruff check scripts tests/test_upstream_watch.py
uv run ruff format --check scripts tests/test_upstream_watch.py
uv run ty check scripts tests/test_upstream_watch.py
```

Expected: all commands exit `0`.

- [ ] **Step 5: Commit audit generation**

```powershell
git add scripts/upstream_watch_core/audit.py tests/test_upstream_watch.py
git commit -m "feat: generate deterministic upstream audit reports"
```

### Task 4: Structured Ledger Coverage and Atomic Baseline Advancement

**Files:**
- Create: `scripts/upstream_watch_core/ledger.py`
- Modify: `tests/test_upstream_watch.py`

**Interfaces:**
- Consumes: `AuditReport`, `WatchState`, `FindingRecord`, and `ReviewedNoActionRecord`.
- Produces: `parse_ledger()`, `validate_coverage()`, `validate_state_transition()`, and `advance_baseline()`.
- Structured ledger lines use exactly `<!-- upstream-watch:audit {JSON} -->`, `<!-- upstream-watch:finding {JSON} -->`, and `<!-- upstream-watch:reviewed-no-action {JSON} -->`.

- [ ] **Step 1: Write failing ledger and advancement tests**

Add `LedgerTests` for complete coverage, missing paths, duplicate paths, unknown paths, empty rationale, `investigate` blocking, accepted work without `TODO-*`/`#N`/GitHub links, digest mismatch, and atomic valid advancement. Patch `Path.replace` to fail and verify the original state remains byte-for-byte unchanged.

```python
coverage = validate_coverage(report, ledger_entry)
self.assertEqual(coverage.covered_paths, frozenset(change.path for change in report.changes))
with self.assertRaisesRegex(LedgerValidationError, "investigate"):
    advance_baseline(state_path, report, ledger_entry, "2026-07-19")
```

- [ ] **Step 2: Run ledger tests and confirm failure**

Run: `uv run python -m unittest tests.test_upstream_watch.LedgerTests -v`

Expected: FAIL because `ledger.py` does not exist.

- [ ] **Step 3: Implement structured Markdown parsing and coverage gates**

Extract only single-line, exact-prefix HTML comments and parse their payloads with `json.loads`; narrative Markdown is never interpreted as state. Require one matching audit record, unique finding identifiers, and exact changed-path coverage. Findings accept only `adopt`, `reimplement`, `investigate`, `reject`, or `superseded-locally`; reviewed-no-action records have no disposition and require a nonempty rationale. `adopt` and `reimplement` require at least one work-item link. Any `investigate` record blocks advancement.

`advance_baseline()` verifies report base equals current baseline, report digest and path count, ledger base/head/audit ID, and complete non-investigate coverage. Write a sibling temporary JSON file, flush and `os.fsync()`, then replace the state file atomically. Delete the temporary file after any exception.

- [ ] **Step 4: Run focused and static checks**

Run:

```powershell
uv run python -m unittest tests.test_upstream_watch.LedgerTests -v
uv run ruff check scripts tests/test_upstream_watch.py
uv run ruff format --check scripts tests/test_upstream_watch.py
uv run ty check scripts tests/test_upstream_watch.py
```

Expected: all commands exit `0`.

- [ ] **Step 5: Commit the acceptance gate**

```powershell
git add scripts/upstream_watch_core/ledger.py tests/test_upstream_watch.py
git commit -m "feat: gate upstream baseline advancement"
```

### Task 5: GitHub Tracking-Issue Lifecycle

**Files:**
- Create: `scripts/upstream_watch_core/github_api.py`
- Modify: `tests/test_upstream_watch.py`

**Interfaces:**
- Consumes: `WatchExit`, author/fork observations, and `GITHUB_TOKEN` or `GH_TOKEN` supplied by the caller.
- Produces: `HttpTransport` protocol, `UrllibTransport`, `GitHubClient`, `IssueSnapshot`, `WatchObservation`, `observation_fingerprint()`, and `reconcile_tracking_issue()`.
- The managed issue title is `[Upstream Watch] ORTHO4XP_V3 review status`; the managed label is `upstream-watch`.

- [ ] **Step 1: Write failing fake-transport tests**

Add `GitHubIssueTests` using a queue-backed fake transport. Cover pagination through the RFC 8288 `Link` header, label creation when absent, issue creation, body update, reopen, close on `CURRENT`, no duplicate comment for an unchanged fingerprint, a history comment for a changed fingerprint, rate-limit errors, malformed JSON, token redaction, and passive-fork lag displayed as informational.

```python
result = reconcile_tracking_issue(client, repository="tvproductions/Ortho4XP", observation=observation)
self.assertEqual(result.action, "created")
self.assertNotIn("secret-token", repr(client.transport.requests))
```

- [ ] **Step 2: Run GitHub tests and confirm failure**

Run: `uv run python -m unittest tests.test_upstream_watch.GitHubIssueTests -v`

Expected: FAIL because `github_api.py` does not exist.

- [ ] **Step 3: Implement the minimal REST client and issue reconciler**

Use `urllib.request.Request` with `Authorization: Bearer {token}`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, and a 30-second timeout. Restrict requests to `https://api.github.com/`; never put a token in a URL, exception, report, or issue body. Follow only `rel="next"` links that remain on the same API origin.

The reconciler upserts the label, finds all-state issues with the exact label and title, rejects duplicates, and then:

- closes an open issue for `CURRENT` while leaving normal passive-fork lag in the final body;
- creates, reopens, or updates for `REVIEW_REQUIRED`, `FORK_ANOMALY`, or `HISTORY_REWRITE`;
- appends one comment only when the canonical observation fingerprint changes;
- returns an error without mutating accepted state for operational failure.

- [ ] **Step 4: Run focused and static checks**

Run:

```powershell
uv run python -m unittest tests.test_upstream_watch.GitHubIssueTests -v
uv run ruff check scripts tests/test_upstream_watch.py
uv run ruff format --check scripts tests/test_upstream_watch.py
uv run ty check scripts tests/test_upstream_watch.py
```

Expected: all commands exit `0`.

- [ ] **Step 5: Commit issue management**

```powershell
git add scripts/upstream_watch_core/github_api.py tests/test_upstream_watch.py
git commit -m "feat: manage upstream watch tracking issue"
```

### Task 6: CLI, Scheduled Workflow, and CI Coverage

**Files:**
- Create: `scripts/upstream_watch_core/cli.py`
- Create: `scripts/upstream_watch.py`
- Create: `.github/upstream-watch.json`
- Create: `.github/workflows/upstream-watch.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `.gitignore`
- Modify: `tests/test_upstream_watch.py`

**Interfaces:**
- Produces: `check`, `audit`, `validate`, and `accept` subcommands and `main(argv: Sequence[str] | None = None) -> int`.
- `check` accepts `--state`, `--manage-issue`, `--repository`, and `--json`.
- `audit` requires `--state`, `--base`, `--head`, and `--output`.
- `validate` requires `--state`, `--report`, and `--ledger`.
- `accept` requires the same three paths plus `--date YYYY-MM-DD`.

- [ ] **Step 1: Write failing CLI contract tests**

Add `CliTests` that invoke `main()` with temporary files and patched orchestration functions. Assert help, explicit required SHA arguments, JSON output, all exit codes, missing-token behavior only when `--manage-issue` is used, atomic report output, validation without network, and passive-fork lag returning `0`.

```python
status = main(["check", "--state", str(state_path), "--json"])
self.assertEqual(status, WatchExit.CURRENT)
self.assertEqual(json.loads(stdout.getvalue())["passive_fork"]["state"], "behind")
```

- [ ] **Step 2: Run CLI tests and confirm failure**

Run: `uv run python -m unittest tests.test_upstream_watch.CliTests -v`

Expected: FAIL because `cli.py` and the wrapper do not exist.

- [ ] **Step 3: Implement the command wrapper and subcommands**

`scripts/upstream_watch.py` adds the repository root to `sys.path` only when run as a file, imports `main`, and exits with `SystemExit(main())`. `cli.py` converts known validation, Git, API, and I/O errors into exit `1` with a concise stderr message; `KeyboardInterrupt` returns `130`. JSON mode writes canonical JSON to stdout and all diagnostics to stderr.

Create `.github/upstream-watch.json` with schema version `1`, the two repository roles and `ORTHO4XP_V3` branches, and this bootstrap baseline:

```json
{
  "schema_version": 1,
  "author": {"repository": "Ypsos/ORTHO4XP_V3", "branch": "ORTHO4XP_V3"},
  "passive_fork": {"repository": "tvproductions/ORTHO4XP_V3", "branch": "ORTHO4XP_V3"},
  "baseline": {
    "reviewed_sha": "4ca0a8d404b078ad899979bafde84769a0fb235b",
    "audit_id": "bootstrap-existing-baseline",
    "audit_date": "2026-06-16",
    "manifest_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "path_count": 0
  }
}
```

- [ ] **Step 4: Add the weekly/manual workflow**

Create an Ubuntu workflow scheduled at `17 13 * * 1` with `workflow_dispatch`, `contents: read`, and `issues: write`. Check out the repository, set up Python `3.13`, run `check --manage-issue` while capturing its status, and fail the job only for status `1`. Statuses `2`, `3`, and `4` are reported through the tracking issue and job summary without turning expected drift into an Actions failure.

- [ ] **Step 5: Extend CI and ignored outputs**

Add `scripts` to all three CI Ruff commands and to all three ty commands. Add `.upstream-watch/` to `.gitignore`. Do not add the scheduled workflow to push/PR CI.

- [ ] **Step 6: Run CLI, workflow-surface, and static checks**

Run:

```powershell
uv run python -m unittest tests.test_upstream_watch.CliTests -v
uv run python scripts/upstream_watch.py --help
uv run ruff check scripts tests/test_upstream_watch.py
uv run ruff format --check scripts tests/test_upstream_watch.py
uv run ty check scripts tests/test_upstream_watch.py
```

Expected: tests pass, help lists all four subcommands, and static checks exit `0`.

- [ ] **Step 7: Commit the executable chore**

```powershell
git add .github .gitignore scripts tests/test_upstream_watch.py
git commit -m "feat: add scheduled upstream watch chore"
```

### Task 7: Initial Audit Ledger, Documentation, and Backlog Hardening

**Files:**
- Create: `docs/upstream/ORTHO4XP_V3-audit.md`
- Modify: `docs/development.md`
- Modify: `TODO.md`
- Modify: `tests/test_upstream_watch.py`

**Interfaces:**
- Consumes: implemented `audit` and `validate` commands.
- Produces: the first durable ledger entry for `4ca0a8d404b078ad899979bafde84769a0fb235b..8a25af093af758292b4ef4c2caff93719cb1a54a` and independent `TODO-044`/`TODO-045` requirements.

- [ ] **Step 1: Generate the explicit initial audit report**

Run:

```powershell
uv run python scripts/upstream_watch.py audit --state .github/upstream-watch.json --base 4ca0a8d404b078ad899979bafde84769a0fb235b --head 8a25af093af758292b4ef4c2caff93719cb1a54a --output .upstream-watch/2026-07-19-4ca0a8d-8a25af0.json
```

Expected: exit `0`; the report contains seven commits and 48 changed paths. Inspect the observed output before writing ledger metadata; do not copy an assumed digest.

- [ ] **Step 2: Add the initial structured ledger entry**

Record the exact report audit ID and digest, then apply these path groups:

- Every changed path under `Providers/`: `investigate`, linked to `TODO-041-4`
  and `#41`, because legality, credentials, service currency, and schema
  conversion remain unverified.
- `src/O4_Altimetrie_Utils.py`: `reimplement`, linked to `TODO-041-5` and
  `#42`, retaining the DEM workflow but rejecting the Rasterio/GUI coupling,
  France-specific missing-CRS fallback, and whole-mosaic memory behavior.
- `src/O4_Correction_Utils.py`, `src/O4_Color_Check.py`, and
  `src/O4_Color_Normalize.py`: `reimplement`, linked to `TODO-041-6` and `#43`,
  retaining operator workflow and sea-only repair research through local
  provider scoring and cache contracts.
- `src/O4_Vector_Map.py` and `src/O4_OSM_Utils.py`: `reimplement`, linked to
  `TODO-041-1` and `#38`, retaining complete non-fatal airport-query handling
  while initializing DEM independently.
- `src/O4_Coastal_Manager.py`, `src/O4_DSF_Utils.py`,
  `src/O4_File_Names.py`, `src/O4_Imagery_Utils.py`, `src/O4_Mask_Utils.py`,
  and `src/O4_Sea_Texture.py`: `reimplement`, linked to `TODO-041-2` and `#39`,
  retaining only the agreed XP12 mask, cleanup, extent, naming, and ocean-decal
  behaviors while rejecting XP11+bathy restoration and wholesale sea-texture
  replacement.
- `README.md`: `reviewed-no-action`, because it documents the sister project
  rather than a portable behavior for this repository.
- `create_launcher_ORTHO.py`: `reviewed-no-action`, because its deletion belongs
  to the sister project's custom installer while this repository uses `uv` and
  its own packaging workflow.
- `src/O4_Config_Utils.py`, `src/O4_GUI_Utils.py`, `src/O4_Lang_EN.py`,
  `src/O4_Lang_FR.py`, and `src/O4_Tile_Utils.py`: `reviewed-no-action`, because
  those changes only expose the upstream DEM/correction modules and their GUI
  state; the approved workbenches will define their own core/UI contracts.

The provider `investigate` finding intentionally prevents baseline advancement until `TODO-041-4` resolves. Do not run `accept` for this range during `TODO-041-3`.

- [ ] **Step 3: Validate the initial ledger**

Run:

```powershell
uv run python scripts/upstream_watch.py validate --state .github/upstream-watch.json --report .upstream-watch/2026-07-19-4ca0a8d-8a25af0.json --ledger docs/upstream/ORTHO4XP_V3-audit.md
```

Expected: exit `2` with a structured result showing complete path coverage and baseline advancement blocked only by the `investigate` provider finding. Missing, duplicate, or unknown paths are failures and must be corrected.

- [ ] **Step 4: Document operator commands and evidence rules**

Add a development-guide section with exact `check`, `audit`, `validate`, and `accept` invocations; explain exit codes `0` through `4`, the passive-fork role, raw report location, the structured ledger records, and the rule that `accept` is run only after all investigations have final dispositions.

- [ ] **Step 5: Replace stale GPU and backup source references**

For `TODO-044`, remove the dependency on the deleted `O4_GPU_Backend` file and specify backend-neutral capability detection, bounded transfer costs, deterministic CPU equivalence, optional dependency isolation, and benchmark thresholds established before enabling GPU paths. For `TODO-045`, remove the deleted `O4_Backup_Manager` and `rollback.py` references and specify transactional backup manifests, checksums, atomic restore, retention, failure recovery, and cross-platform tests. Keep historical commit references only in the audit ledger.

- [ ] **Step 6: Add repository-surface consistency tests**

Add tests that load the committed state, parse the committed ledger, assert author/passive-fork roles, verify the initial report range is represented, and confirm `TODO-041-3`, `TODO-044`, and `TODO-045` no longer rely on absent upstream files.

- [ ] **Step 7: Run documentation and focused verification**

Run:

```powershell
uv run python -m unittest tests.test_upstream_watch -v
uv run ruff check scripts tests/test_upstream_watch.py
uv run ruff format --check scripts tests/test_upstream_watch.py
uv run ty check scripts tests/test_upstream_watch.py
git diff --check
```

Expected: all tests and static checks pass; `validate` remains status `2` solely because the provider audit is deliberately unresolved.

- [ ] **Step 8: Commit evidence and documentation**

```powershell
git add docs TODO.md tests/test_upstream_watch.py
git commit -m "docs: record initial sister-project audit"
```

### Task 8: Full Verification and Issue Evidence

**Files:**
- Modify only files required to correct defects found by verification.
- Update GitHub Issue `#40` with observed evidence; close it only after all acceptance criteria pass.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: verified repository behavior and an issue evidence comment.

- [ ] **Step 1: Run the full unit suite**

Run: `uv run python -m unittest discover -s tests`

Expected: all tests pass with zero failures and zero errors.

- [ ] **Step 2: Run repository lint, formatting, and type checks**

Run:

```powershell
uv run ruff check Ortho4XP.py src scripts tests
uv run ruff format --check .
uv run ty check tests scripts src/O4_Geo_Utils.py src/O4_File_Names.py
```

Expected: all commands exit `0`.

- [ ] **Step 3: Run the full repository quality gate**

Run: `uv run python .codex/skills/quality-check/scripts/quality_check.py`

Expected: unittest, Ruff, ty, whitespace, complexity, LLVM/CMake, and native checks all pass.

- [ ] **Step 4: Exercise the real detector without issue mutation**

Run: `uv run python scripts/upstream_watch.py check --state .github/upstream-watch.json --json`

Expected: valid canonical JSON; status `2` if the author head remains beyond the bootstrap baseline, normal passive-fork lag remains informational, and no GitHub issue is changed because `--manage-issue` is absent.

- [ ] **Step 5: Perform the manual workflow dispatch test**

After the implementation commits are pushed, dispatch `.github/workflows/upstream-watch.yml`. Confirm the run completes for expected review drift, creates or updates exactly one labeled tracking issue, contains no credentials, and reports the author and passive-fork roles correctly.

- [ ] **Step 6: Record evidence and close implementation tracking**

Comment on GitHub Issue `#40` with exact test counts, Ruff/format/ty results, full quality-gate result, detector output status, workflow run URL, and tracking-issue URL. Close `#40` only when all acceptance criteria are satisfied; leave the recurring upstream-review issue open while findings remain unresolved.

- [ ] **Step 7: Commit any verification corrections**

If verification required corrections, commit only the verified fixes:

```powershell
git add .github .gitignore docs scripts tests TODO.md
git commit -m "fix: complete upstream watch verification"
```

If no corrections were required, do not create an empty commit.
