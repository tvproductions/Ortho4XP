from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
CEREMONY_TRAILER = "Sync: git-sync"


def git(args: list[str], *, check: bool = False) -> tuple[int, str, str]:
    proc = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, ["git", *args], proc.stdout, proc.stderr
        )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def run(args: list[str]) -> None:
    print("+ " + " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True, text=True)  # noqa: S603


def current_branch() -> tuple[str | None, str | None]:
    rc, out, err = git(["rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0:
        return None, err or "Could not determine current branch."
    if out == "HEAD":
        return None, "Detached HEAD."
    return out, None


def status_lines() -> list[str]:
    rc, out, _err = git(["status", "--porcelain"])
    if rc != 0:
        return []
    return [line for line in out.splitlines() if line.strip()]


def has_merge_head() -> bool:
    return (ROOT / ".git" / "MERGE_HEAD").exists()


def head_is_merge_commit() -> bool:
    rc_merge, merge_head, _ = git(["rev-list", "--max-count=1", "--merges", "HEAD"])
    rc_head, head_sha, _ = git(["rev-parse", "HEAD"])
    return (
        rc_merge == 0 and rc_head == 0 and bool(merge_head) and merge_head == head_sha
    )


def remote_branch_exists(remote: str, branch: str) -> bool:
    rc, _out, _err = git(["rev-parse", "--verify", "--quiet", f"{remote}/{branch}"])
    return rc == 0


def sync_state(remote: str, branch: str) -> dict[str, Any]:
    warnings: list[str] = []
    if not remote_branch_exists(remote, branch):
        warnings.append(f"Could not resolve remote branch: {remote}/{branch}")
        return {"ahead": 0, "behind": 0, "diverged": False, "warnings": warnings}

    rc_ahead, ahead_out, _ = git(
        ["rev-list", "--count", f"{remote}/{branch}..{branch}"]
    )
    rc_behind, behind_out, _ = git(
        ["rev-list", "--count", f"{branch}..{remote}/{branch}"]
    )
    ahead = int(ahead_out) if rc_ahead == 0 and ahead_out.isdigit() else 0
    behind = int(behind_out) if rc_behind == 0 and behind_out.isdigit() else 0
    return {
        "ahead": ahead,
        "behind": behind,
        "diverged": ahead > 0 and behind > 0,
        "warnings": warnings,
    }


def classify_paths(paths: list[str]) -> str:
    buckets: dict[str, int] = {}
    for path in paths:
        first = Path(path).parts[0] if Path(path).parts else "root"
        buckets[first] = buckets.get(first, 0) + 1
    labels = [
        key if count == 1 else f"{key} ({count} files)"
        for key, count in sorted(buckets.items())
    ]
    summary = ", ".join(labels[:4])
    if len(labels) > 4:
        summary += f" +{len(labels) - 4} more"
    return summary or "staged changes"


def staged_files() -> list[str]:
    rc, out, _err = git(["diff", "--cached", "--name-only"])
    if rc != 0:
        return []
    return [line for line in out.splitlines() if line.strip()]


def stranded_commit_subject() -> str | None:
    editmsg = ROOT / ".git" / "COMMIT_EDITMSG"
    try:
        lines = editmsg.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    subject = next(
        (line.strip() for line in lines if line.strip() and not line.startswith("#")),
        None,
    )
    if not subject:
        return None

    rc, head_subject, _err = git(["log", "-1", "--format=%s"])
    if rc == 0 and head_subject == subject:
        return None
    if ": " not in subject:
        return None
    return subject


def build_commit_message(files: list[str]) -> str:
    subject = f"chore: update {classify_paths(files)} (git sync)"
    return f"{subject}\n\n{CEREMONY_TRAILER}"


def plan(
    *,
    target_branch: str | None,
    remote: str,
    apply: bool,
    auto_add: bool,
    allow_push: bool,
    hygiene: bool,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    actions: list[str] = [f"git fetch --prune {remote}"]

    branch, branch_error = current_branch()
    if branch_error:
        blockers.append(branch_error)
        branch = None

    target = target_branch or branch
    if branch and target and branch != target:
        blockers.append(f"Not on branch {target} (current: {branch})")

    if has_merge_head():
        blockers.append("Merge in progress. Resolve it before git-sync.")
    if head_is_merge_commit():
        blockers.append("Merge commit at HEAD. Linearize history before git-sync.")

    dirty = bool(status_lines())
    if dirty and auto_add:
        actions.append("git add -A")
    if dirty and hygiene:
        actions.append("project hygiene quick gate")
    if dirty and auto_add:
        actions.append("git commit")

    fetch_rc, _fetch_out, fetch_err = git(["fetch", "--prune", remote])
    if fetch_rc != 0:
        msg = fetch_err or f"Fetch failed for remote {remote}."
        if apply:
            blockers.append(msg)
        else:
            warnings.append(f"{msg} ahead/behind may be stale.")

    state = sync_state(remote, target) if target else {"ahead": 0, "behind": 0}
    state_warnings = state.get("warnings", [])
    if isinstance(state_warnings, list):
        warnings.extend(str(warning) for warning in state_warnings)
    ahead = int(state["ahead"])
    behind = int(state["behind"])
    effective_ahead = ahead + (1 if dirty and auto_add else 0)
    diverged = effective_ahead > 0 and behind > 0

    if target and diverged:
        actions.append(f"git pull --rebase {remote} {target}")
    elif target and behind > 0:
        actions.append(f"git pull --ff-only {remote} {target}")
    if target and allow_push and (effective_ahead > 0 or diverged):
        actions.append(f"git push {remote} {target}")

    if target and not remote_branch_exists(remote, target):
        blockers.append(f"Missing remote branch: {remote}/{target}")

    return {
        "branch": target,
        "remote": remote,
        "apply": apply,
        "dirty": dirty,
        "ahead": ahead,
        "behind": behind,
        "diverged": diverged,
        "actions": actions,
        "executed": [],
        "blockers": blockers,
        "warnings": warnings,
    }


def commit_if_needed(executed: list[str]) -> None:
    files = staged_files()
    if not files:
        return

    stranded = stranded_commit_subject()
    if stranded:
        raise SystemExit(
            "Refusing to auto-commit: .git/COMMIT_EDITMSG holds an unlanded "
            f"commit subject: {stranded!r}."
        )

    message = build_commit_message(files)
    run(["git", "commit", "-m", message])
    executed.append("git commit")


def apply_sync(
    result: dict[str, Any], *, auto_add: bool, allow_push: bool, hygiene: bool
) -> None:
    blockers = result["blockers"]
    if blockers:
        raise SystemExit(1)

    branch = result["branch"]
    remote = result["remote"]
    executed = result["executed"]

    if result["dirty"] and auto_add:
        run(["git", "add", "-A"])
        executed.append("git add -A")

    if result["dirty"] and hygiene:
        run(
            [
                "uv",
                "run",
                "python",
                ".codex/skills/repo-hygiene/scripts/hygiene.py",
                "--quick",
            ]
        )
        executed.append("project hygiene quick gate")

    commit_if_needed(executed)

    state = sync_state(remote, branch)
    if state["diverged"]:
        run(["git", "pull", "--rebase", remote, branch])
        executed.append(f"git pull --rebase {remote} {branch}")
    elif state["behind"] > 0:
        run(["git", "pull", "--ff-only", remote, branch])
        executed.append(f"git pull --ff-only {remote} {branch}")

    post_pull = sync_state(remote, branch)
    if allow_push and post_pull["ahead"] > 0:
        run(["git", "push", remote, branch])
        executed.append(f"git push {remote} {branch}")
        git(["fetch", "--prune", remote])


def print_result(result: dict[str, Any]) -> None:
    title = "Git sync execution" if result["apply"] else "Git sync plan (dry-run)"
    print(title)
    print(f"  Branch: {result['branch']}")
    print(f"  Remote: {result['remote']}")
    print(
        "  "
        f"ahead={result['ahead']} "
        f"behind={result['behind']} "
        f"diverged={result['diverged']} "
        f"dirty={result['dirty']}"
    )
    print("  Actions:")
    for action in result["actions"]:
        print(f"    - {action}")
    if result["executed"]:
        print("  Executed:")
        for item in result["executed"]:
            print(f"    - {item}")
    if result["warnings"]:
        print("  Warnings:")
        for warning in result["warnings"]:
            print(f"    - {warning}")
    if result["blockers"]:
        print("  Blockers:")
        for blocker in result["blockers"]:
            print(f"    - {blocker}")
    elif result["apply"]:
        print("Git sync completed.")
    else:
        print("  Use --apply to execute.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Guarded local<->origin sync for Ortho4XP."
    )
    parser.add_argument("--branch", help="Branch to sync. Default: current branch.")
    parser.add_argument("--remote", default="origin", help="Remote name.")
    parser.add_argument(
        "--apply", action="store_true", help="Execute sync actions. Default: dry-run."
    )
    parser.add_argument(
        "--auto-add",
        dest="auto_add",
        action="store_true",
        default=True,
        help="Auto-add changes before creating a sync commit.",
    )
    parser.add_argument(
        "--no-auto-add",
        dest="auto_add",
        action="store_false",
        help="Do not auto-add changes.",
    )
    parser.add_argument(
        "--push",
        dest="allow_push",
        action="store_true",
        default=True,
        help="Push after local reconciliation.",
    )
    parser.add_argument(
        "--no-push",
        dest="allow_push",
        action="store_false",
        help="Commit and reconcile without pushing.",
    )
    parser.add_argument(
        "--hygiene",
        dest="hygiene",
        action="store_true",
        default=True,
        help="Run project hygiene quick gate before committing.",
    )
    parser.add_argument(
        "--no-hygiene",
        dest="hygiene",
        action="store_false",
        help="Skip project hygiene gate.",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON.")
    args = parser.parse_args()

    result = plan(
        target_branch=args.branch,
        remote=args.remote,
        apply=args.apply,
        auto_add=args.auto_add,
        allow_push=args.allow_push,
        hygiene=args.hygiene,
    )

    if args.apply:
        apply_sync(
            result,
            auto_add=args.auto_add,
            allow_push=args.allow_push,
            hygiene=args.hygiene,
        )
        final_state = sync_state(args.remote, result["branch"])
        result["ahead"] = final_state["ahead"]
        result["behind"] = final_state["behind"]
        result["diverged"] = final_state["diverged"]
        result["dirty"] = bool(status_lines())

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_result(result)

    return 1 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
