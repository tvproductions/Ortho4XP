# Superpowers Hygiene Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a check-only Superpowers freshness gate to repository hygiene, provide a safe explicit updater, and refresh the vendored tree from `v6.0.3` to `v6.1.1`.

**Architecture:** A focused `superpowers_vendor.py` module parses local source/version metadata, discovers stable upstream tags with `git ls-remote`, and exposes separate check and update commands. `hygiene.py` invokes only check mode; update mode clones an exact tag into a sibling staging directory, verifies the local override preimage, and swaps the vendor tree with rollback protection.

**Tech Stack:** Python 3.13, standard-library `unittest`, `unittest.mock`, `tempfile`, `pathlib`, `json`, `hashlib`, `shutil`, and `subprocess`; Git; `uv`; Ruff; ty.

## Global Constraints

- Use Python 3.13.x through `uv` and standard-library `unittest` only.
- Hygiene checks never modify files.
- Confirmed staleness fails; unavailable upstream emits a visible warning and exits successfully.
- Select only stable tags matching `vMAJOR.MINOR.PATCH`; ignore prereleases and unreleased `main` commits.
- Updates require the explicit `--update` flag and must refuse a dirty vendor tree.
- Resolve and verify every replacement path beneath `.agents/skills` before rename or removal.
- Preserve the existing token-analysis Ruff/ty adaptation only when its upstream SHA256 is `b3b124b975086e66540dca1328d7b6b75416450b0c93fc246f0d7d148fc2394c`.
- Preserve source attribution and the documented whitespace adaptations.
- Do not modify Git branches, worktrees, remotes, or history from the vendor tool.
- Remain portable to Windows 11, current Apple Silicon macOS, and Ubuntu.

---

### Task 1: Implement Deterministic Release and Metadata Checking

**Files:**
- Create: `.codex/skills/repo-hygiene/scripts/superpowers_vendor.py`
- Create: `tests/test_superpowers_vendor.py`
- Modify: `.agents/skills/superpowers/SOURCE.md`

**Interfaces:**
- Produces: `Version.parse(tag: str) -> Version | None`, ordered by major/minor/patch.
- Produces: `parse_releases(output: str) -> list[Release]`, with annotated tags resolved to peeled commits.
- Produces: `read_source_pin(vendor_dir: Path) -> SourcePin`.
- Produces: `read_manifest_versions(vendor_dir: Path) -> dict[str, str]`.
- Produces: `check_vendor(root: Path, ls_remote: Callable[[str], str]) -> CheckResult`.
- CLI: `superpowers_vendor.py --check` exits 0 for current/unavailable, nonzero for stale/malformed.

- [ ] **Step 1: Write failing semantic-version and release parsing tests**

Create `tests/test_superpowers_vendor.py` with this import helper, then add the
release test:

```python
import importlib.util
import unittest

try:
    import _path
except ModuleNotFoundError:
    from tests import _path


def load_vendor_module():
    path = (
        _path.ROOT_DIR
        / ".codex"
        / "skills"
        / "repo-hygiene"
        / "scripts"
        / "superpowers_vendor.py"
    )
    spec = importlib.util.spec_from_file_location("superpowers_vendor", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load vendor module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SuperpowersReleaseTests(unittest.TestCase):
    def test_selects_highest_stable_tag_and_peels_annotated_tag(self):
        vendor = load_vendor_module()
        output = "\n".join(
            [
                "tag-object refs/tags/v6.1.1",
                "release-commit refs/tags/v6.1.1^{}",
                "older-commit refs/tags/v6.0.3",
                "preview-commit refs/tags/v7.0.0-rc1",
            ]
        )

        latest = vendor.latest_stable_release(vendor.parse_releases(output))

        self.assertEqual(latest.tag, "v6.1.1")
        self.assertEqual(latest.version, vendor.Version(6, 1, 1))
        self.assertEqual(latest.commit, "release-commit")
```

- [ ] **Step 2: Run the release test and verify RED**

Run:

```powershell
uv run python -m unittest tests.test_superpowers_vendor.SuperpowersReleaseTests -v
```

Expected: ERROR because `superpowers_vendor.py` does not exist.

- [ ] **Step 3: Implement release parsing**

Add these public models and parsing rules:

```python
@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, tag: str) -> Version | None:
        match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag)
        if match is None:
            return None
        return cls(*(int(part) for part in match.groups()))


@dataclass(frozen=True)
class Release:
    tag: str
    version: Version
    commit: str


def parse_releases(output: str) -> list[Release]:
    direct: dict[str, str] = {}
    peeled: dict[str, str] = {}
    for line in output.splitlines():
        commit, ref = line.split(maxsplit=1)
        prefix = "refs/tags/"
        if not ref.startswith(prefix):
            continue
        tag = ref.removeprefix(prefix)
        if tag.endswith("^{}"):
            peeled[tag[:-3]] = commit
        else:
            direct[tag] = commit
    return [
        Release(tag, version, peeled.get(tag, commit))
        for tag, commit in direct.items()
        if (version := Version.parse(tag)) is not None
    ]


def latest_stable_release(releases: list[Release]) -> Release:
    if not releases:
        raise MetadataError("Upstream exposes no stable Superpowers release tags.")
    return max(releases, key=lambda release: release.version)
```

- [ ] **Step 4: Run the release tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Write failing metadata/check outcome tests**

Add fixture helpers that write `SOURCE.md`, `package.json`, and every
version-bearing manifest. Test these exact outcomes:

```python
def test_confirmed_stale_vendor_fails_with_update_command(self):
    result = vendor.check_vendor(
        self.root,
        ls_remote=lambda _repo: release_output("v6.1.1", "new-commit"),
    )
    self.assertEqual(result.status, vendor.Status.STALE)
    self.assertIn("superpowers_vendor.py --update", result.message)


def test_unavailable_upstream_warns_without_failing(self):
    def unavailable(_repo):
        raise vendor.UpstreamUnavailable("network unavailable")

    result = vendor.check_vendor(self.root, ls_remote=unavailable)
    self.assertEqual(result.status, vendor.Status.UNAVAILABLE)
    self.assertEqual(result.exit_code, 0)


def test_manifest_disagreement_is_invalid(self):
    write_manifest(self.vendor_dir / ".codex-plugin/plugin.json", "6.0.2")
    result = vendor.check_vendor(self.root, ls_remote=lambda _repo: "")
    self.assertEqual(result.status, vendor.Status.INVALID)
    self.assertNotEqual(result.exit_code, 0)
```

- [ ] **Step 6: Run the check tests and verify RED**

Run:

```powershell
uv run python -m unittest tests.test_superpowers_vendor.SuperpowersCheckTests -v
```

Expected: FAIL because source/manifest validation and result statuses are absent.

- [ ] **Step 7: Implement metadata validation and check mode**

Use these stable public contracts:

```python
class Status(Enum):
    CURRENT = "current"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


@dataclass(frozen=True)
class SourcePin:
    repository: str
    release: str
    commit: str


@dataclass(frozen=True)
class CheckResult:
    status: Status
    message: str

    @property
    def exit_code(self) -> int:
        return 1 if self.status in {Status.STALE, Status.INVALID} else 0
```

`read_source_pin()` must require `Repository`, `Release`, and `Commit` bullet
fields. `read_manifest_versions()` must read `package.json`, all four plugin
manifests, `gemini-extension.json`, and the nested Claude marketplace plugin
version. Missing files, invalid JSON, missing version fields, disagreement, or
disagreement with `SOURCE.md` return `Status.INVALID`.

The production `ls_remote()` uses:

```python
subprocess.run(
    ["git", "ls-remote", "--tags", repository, "refs/tags/v*"],
    check=False,
    capture_output=True,
    text=True,
)
```

A nonzero return raises `UpstreamUnavailable`. A current pin matches both the
latest release tag and peeled commit. A lower stable version returns
`Status.STALE` with the exact update command.

Before running the checker against the real vendor tree, normalize its legacy
source metadata by adding the observed release between repository and commit:

```markdown
- Repository: https://github.com/obra/superpowers
- Release: v6.0.3
- Commit: 896224c4b1879920ab573417e68fd51d2ccc9072
```

- [ ] **Step 8: Run all vendor check tests and verify GREEN**

Run:

```powershell
uv run python -m unittest tests.test_superpowers_vendor -v
```

Expected: all Task 1 tests PASS without network access.

- [ ] **Step 9: Run changed-file checks and commit Task 1**

Run:

```powershell
uv run ruff check .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_superpowers_vendor.py
uv run ruff format --check .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_superpowers_vendor.py
uv run ty check .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_superpowers_vendor.py
git add .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_superpowers_vendor.py .agents/skills/superpowers/SOURCE.md
git commit -m "feat: check vendored superpowers freshness"
```

Expected: every check exits 0 and the commit succeeds.

---

### Task 2: Implement the Explicit Safe Updater

**Files:**
- Modify: `.codex/skills/repo-hygiene/scripts/superpowers_vendor.py`
- Modify: `tests/test_superpowers_vendor.py`

**Interfaces:**
- Produces: `update_vendor(root: Path, release: Release, runner: CommandRunner) -> None`.
- CLI: `superpowers_vendor.py --update` refreshes only a clean vendor tree and leaves reviewable uncommitted changes.
- Preserves: locally adapted `tests/claude-code/analyze-token-usage.py` after verifying the exact upstream preimage hash.

- [ ] **Step 1: Write failing dirty-tree and exact-tag update tests**

Build a temporary parent Git repository containing a minimal current vendor
fixture and a separate local upstream Git repository with `v6.0.3` and
annotated `v6.1.1` tags. The `v6.1.1` tree must include all version manifests,
the upstream token-analysis preimage, and a file present only in the newer
release.

Add:

```python
def test_update_refuses_dirty_vendor_tree(self):
    (self.vendor_dir / "README.md").write_text("dirty\n", encoding="utf-8")
    with self.assertRaisesRegex(vendor.UpdateError, "uncommitted changes"):
        vendor.update_vendor(self.root, self.latest, vendor.run_command)


def test_update_uses_exact_tag_and_preserves_local_adaptation(self):
    adapted = self.vendor_dir / vendor.ADAPTED_TOKEN_ANALYSIS_PATH
    adapted.write_text("locally adapted\n", encoding="utf-8")
    commit_all(self.root, "Adapt token utility")

    vendor.update_vendor(self.root, self.latest, vendor.run_command)

    self.assertEqual(adapted.read_text(encoding="utf-8"), "locally adapted\n")
    self.assertTrue((self.vendor_dir / "new-release-file.txt").exists())
    source = vendor.read_source_pin(self.vendor_dir)
    self.assertEqual(source.release, "v6.1.1")
    self.assertEqual(source.commit, self.latest.commit)
    self.assertFalse(any(self.vendor_dir.parent.glob(".superpowers-*-*")))
```

- [ ] **Step 2: Run updater tests and verify RED**

Run:

```powershell
uv run python -m unittest tests.test_superpowers_vendor.SuperpowersUpdateTests -v
```

Expected: FAIL because update mode does not exist.

- [ ] **Step 3: Implement clean-tree, staging, adaptation, and swap helpers**

Implement these boundaries:

```python
ADAPTED_TOKEN_ANALYSIS_PATH = Path("tests/claude-code/analyze-token-usage.py")
ADAPTED_TOKEN_ANALYSIS_UPSTREAM_SHA256 = (
    "b3b124b975086e66540dca1328d7b6b75416450b0c93fc246f0d7d148fc2394c"
)


def ensure_vendor_clean(root: Path, vendor_dir: Path) -> None:
    relative = vendor_dir.relative_to(root)
    result = run_command(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", str(relative)],
        cwd=root,
    )
    if result.stdout.strip():
        raise UpdateError(f"Vendor tree has uncommitted changes: {relative}")


def apply_local_adaptations(current: Path, staged: Path) -> None:
    upstream_file = staged / ADAPTED_TOKEN_ANALYSIS_PATH
    digest = hashlib.sha256(upstream_file.read_bytes()).hexdigest()
    if digest != ADAPTED_TOKEN_ANALYSIS_UPSTREAM_SHA256:
        raise UpdateError(
            "Upstream changed tests/claude-code/analyze-token-usage.py; "
            "reconcile the local Ruff/ty adaptation before updating."
        )
    shutil.copy2(current / ADAPTED_TOKEN_ANALYSIS_PATH, upstream_file)
    for relative in (Path("README.md"), Path("RELEASE-NOTES.md")):
        path = staged / relative
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")
```

`stage_release()` must clone with `--depth 1 --branch <exact-tag>`, verify
`git rev-parse HEAD` equals `Release.commit`, remove only the resolved staged
`.git` directory, add the updated `SOURCE.md`, and call
`apply_local_adaptations()`.

`replace_vendor()` must verify `vendor_dir.parent.resolve()` equals
`(root / ".agents/skills").resolve()`, rename the current directory to a unique
sibling backup, rename the staged payload into place, and restore the backup on
any second-rename failure. It removes the backup only after the new vendor is
in place.

- [ ] **Step 4: Run updater tests and verify GREEN**

Run the Task 2 Step 2 command. Expected: both tests PASS.

- [ ] **Step 5: Write and verify a failing rollback test**

Inject a `rename_path(source: Path, target: Path)` callable into
`replace_vendor()`. The test callable succeeds for the backup rename and fails
for the staged rename. Assert that `UpdateError` is raised, the original vendor
content is restored, and no backup directory remains.

Run the single test before implementation. Expected: FAIL because the rename
callable is not injected or restoration is absent.

- [ ] **Step 6: Implement rollback and verify GREEN**

On staged-rename failure, rename the backup back to the original vendor path
before raising `UpdateError`. If restoration itself fails, report both errors
and the exact backup path; do not delete it.

Run:

```powershell
uv run python -m unittest tests.test_superpowers_vendor -v
```

Expected: all vendor checker/updater tests PASS.

- [ ] **Step 7: Add CLI update selection and changed-file checks**

Use a mutually exclusive required parser group for `--check` and `--update`.
`--update` discovers the latest stable release, performs the guarded refresh,
and prints the old/new tag and commit. It returns nonzero on invalid metadata,
unavailable upstream, dirty vendor state, hash mismatch, clone failure, or
replacement failure.

Run:

```powershell
uv run ruff check .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_superpowers_vendor.py
uv run ruff format --check .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_superpowers_vendor.py
uv run ty check .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_superpowers_vendor.py
```

Expected: all commands exit 0.

- [ ] **Step 8: Commit Task 2**

```powershell
git add .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_superpowers_vendor.py
git commit -m "feat: safely refresh vendored superpowers"
```

---

### Task 3: Integrate Hygiene, Refresh to v6.1.1, and Verify Delivery

**Files:**
- Modify: `.codex/skills/repo-hygiene/scripts/hygiene.py:281-296`
- Modify: `.codex/skills/repo-hygiene/SKILL.md`
- Modify: `tests/test_repo_hygiene.py`
- Replace from upstream release: `.agents/skills/superpowers/**`
- Modify: `.agents/skills/superpowers/SOURCE.md`
- Modify: `docs/superpowers/plans/2026-07-19-superpowers-hygiene-refresh-plan.md`

**Interfaces:**
- Consumes: `superpowers_vendor.py --check` and `--update`.
- Produces: quick/full hygiene freshness enforcement before dependency and build gates.
- Produces: vendored Superpowers `v6.1.1` pinned to `d884ae04edebef577e82ff7c4e143debd0bbec99`.

- [ ] **Step 1: Write the failing hygiene ordering test**

Extend `RepoHygienePatternTests`:

```python
import sys
from unittest import mock


def test_superpowers_check_precedes_python_hygiene(self):
    hygiene = load_hygiene_module()
    order = []

    def record_run(args, *, check=True):
        if args == hygiene.SUPERPOWERS_CHECK_COMMAND:
            order.append("superpowers")
        return mock.Mock(returncode=0)

    with (
        mock.patch.object(hygiene, "run", side_effect=record_run),
        mock.patch.object(hygiene, "scan_forbidden_patterns"),
        mock.patch.object(
            hygiene,
            "run_python_hygiene_commands",
            side_effect=lambda: order.append("python"),
        ),
        mock.patch.object(hygiene, "changed_python_files", return_value=[]),
        mock.patch.object(hygiene, "run_complexity_quality"),
        mock.patch.object(sys, "argv", ["hygiene.py", "--quick"]),
    ):
        hygiene.main()

    self.assertEqual(order, ["superpowers", "python"])
```

- [ ] **Step 2: Run the hygiene test and verify RED**

Run:

```powershell
uv run python -m unittest tests.test_repo_hygiene.RepoHygienePatternTests.test_superpowers_check_precedes_python_hygiene -v
```

Expected: FAIL because `SUPERPOWERS_CHECK_COMMAND` and its invocation are absent.

- [ ] **Step 3: Integrate the check into quick and full hygiene**

Add:

```python
SUPERPOWERS_CHECK_COMMAND = [
    "uv",
    "run",
    "python",
    ".codex/skills/repo-hygiene/scripts/superpowers_vendor.py",
    "--check",
]
```

In `main()`, call `run(SUPERPOWERS_CHECK_COMMAND)` immediately after the initial
Git status and before `scan_forbidden_patterns()` and
`run_python_hygiene_commands()`. Update the repo-hygiene skill documentation
with the check/update commands and the unavailable-upstream policy.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
uv run python -m unittest tests.test_repo_hygiene tests.test_superpowers_vendor -v
```

Expected: all focused tests PASS.

- [ ] **Step 5: Run the live stale check and explicit update**

Run:

```powershell
uv run python .codex/skills/repo-hygiene/scripts/superpowers_vendor.py --check
uv run python .codex/skills/repo-hygiene/scripts/superpowers_vendor.py --update
uv run python .codex/skills/repo-hygiene/scripts/superpowers_vendor.py --check
```

Expected: the first command reports `v6.0.3` stale and exits nonzero; update
refreshes the exact `v6.1.1` tag; the final command reports current at
`d884ae04edebef577e82ff7c4e143debd0bbec99` and exits 0.

- [ ] **Step 6: Inspect the vendor delta and source metadata**

Run:

```powershell
git diff --stat -- .agents/skills/superpowers
git diff --check
Select-String -Path .agents/skills/superpowers/SOURCE.md -Pattern "Release|Commit"
Select-String -Path .agents/skills/superpowers/package.json,.agents/skills/superpowers/.codex-plugin/plugin.json -Pattern '"version"'
```

Expected: upstream's 29-file release delta is present, `SOURCE.md` names
`v6.1.1` and `d884ae04...`, all manifests say `6.1.1`, and the only retained
content deviation is the documented token-analysis adaptation plus trailing
whitespace cleanup.

- [ ] **Step 7: Run portable upstream and focused repository validation**

Run the upstream tests through Git for Windows Bash when present:

```powershell
& "C:\Program Files\Git\bin\bash.exe" .agents/skills/superpowers/tests/codex/test-marketplace-manifest.sh
& "C:\Program Files\Git\bin\bash.exe" .agents/skills/superpowers/tests/hooks/test-session-start.sh
uv run python -m unittest tests.test_repo_hygiene tests.test_superpowers_vendor -v
uv run ruff check .codex/skills/repo-hygiene/scripts/hygiene.py .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_repo_hygiene.py tests/test_superpowers_vendor.py
uv run ruff format --check .codex/skills/repo-hygiene/scripts/hygiene.py .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_repo_hygiene.py tests/test_superpowers_vendor.py .agents/skills/superpowers/tests/claude-code/analyze-token-usage.py
uv run ty check .codex/skills/repo-hygiene/scripts/hygiene.py .codex/skills/repo-hygiene/scripts/superpowers_vendor.py tests/test_repo_hygiene.py tests/test_superpowers_vendor.py .agents/skills/superpowers/tests/claude-code/analyze-token-usage.py
```

Expected: all available commands pass without warnings. If Git Bash is absent,
record that environmental limitation and run the equivalent manifest JSON
validation through the deterministic Python tests; do not claim the shell test
ran.

- [ ] **Step 8: Run the complete repository quality gate**

Run:

```powershell
uv run python -m unittest discover -s tests
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected: the full unit suite and every quality stage pass, including Ruff,
formatting, ty, whitespace, complexity, clang-tidy, and LLVM/CMake.

- [ ] **Step 9: Mark the plan complete and commit delivery**

Check every completed plan box, run `git diff --check`, then:

```powershell
git add .agents/skills/superpowers .codex/skills/repo-hygiene tests/test_repo_hygiene.py tests/test_superpowers_vendor.py docs/superpowers/plans/2026-07-19-superpowers-hygiene-refresh-plan.md
git commit -m "chore: keep vendored superpowers current"
```

- [ ] **Step 10: Guarded-sync and re-audit repository topology**

Run:

```powershell
uv run python .codex/skills/git-sync/scripts/git_sync.py --branch master
uv run python .codex/skills/git-sync/scripts/git_sync.py --branch master --apply
uv run python .codex/skills/git-sync/scripts/git_sync.py --branch master
git branch --all --verbose --verbose
git worktree list --porcelain
git worktree prune --dry-run --verbose
```

Expected: final sync reports `ahead=0`, `behind=0`, no divergence, and a clean
workspace. Only local `master`, `origin/master`, and the primary registered
worktree remain; dry-run pruning reports no stale worktrees.
