"""Check immutable stack sources and project-only discovery configuration."""

import argparse
import json
import re
import tomllib
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
COMPONENTS = {"superpowers", "gz-skills", "superpowers-backplane"}
CATALOGS = {
    ".agents/plugins/marketplace.json": "ref",
    ".claude-plugin/marketplace.json": "sha",
}
SURFACES = (".agents/skills", ".codex/skills", ".claude/skills", ".github/skills")
# Skill identities from reviewed Superpowers 7.0.0 and deferred Backplane.
# Reconcile this set when the bundle's component pins change.
UPSTREAM_SKILLS = {
    "brainstorming",
    "diagnosing-superpowers",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
    "receiving-code-review",
    "requesting-code-review",
    "subagent-driven-development",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "using-superpowers",
    "verification-before-completion",
    "writing-plans",
    "writing-skills",
    "managing-superpowers-backlog",
    "managing-superpowers-handoffs",
}
SKILL_NAME = re.compile(r"^name:\s*(['\"]?)([a-z0-9-]+)\1\s*(?:#.*)?$", re.MULTILINE)


def repository_identity(repository: str) -> str:
    """Treat an optional Git suffix and trailing slash as the same source."""
    if not isinstance(repository, str):
        raise ValueError("Source repository must be a URL string.")
    return repository.rstrip("/").removesuffix(".git")


def upstream_name(name: str) -> bool:
    """Recognize reviewed upstream identities without relying on host caches."""
    return name in COMPONENTS or name in UPSTREAM_SKILLS or name.startswith("gzs-")


def copied_upstream_skill(skill: Path) -> bool:
    """Check frontmatter identity, including copies placed in renamed folders."""
    text = skill.read_text("utf-8-sig")
    if not text.startswith("---\n"):
        return False
    frontmatter, separator, _ = text.partition("\n---")
    identity = SKILL_NAME.search(frontmatter) if separator else None
    return identity is not None and upstream_name(identity[2])


def check_skill_entry(root: Path, entry: Path) -> list[str]:
    """Reject one discovery entry's folder or upstream frontmatter identities."""
    if upstream_name(entry.name):
        return [
            f"Duplicate upstream skill discovery: {entry.relative_to(root).as_posix()}."
        ]
    failures = []
    for skill in entry.rglob("SKILL.md"):
        if copied_upstream_skill(skill):
            failures.append(
                f"Duplicate upstream skill discovery: {skill.relative_to(root)}."
            )
    return failures


def check_copied_skills(root: Path) -> list[str]:
    """Reject component trees and copied upstream skill identities."""
    failures = []
    for surface in SURFACES:
        directory = root / surface
        if not directory.exists():
            continue
        for entry in directory.iterdir():
            failures.extend(check_skill_entry(root, entry))
    return failures


def check_revisions(revisions: list) -> list[str]:
    """Report every revision that is not a full immutable commit SHA."""
    failures = []
    for revision in revisions:
        if not isinstance(revision, str) or not SHA.fullmatch(revision):
            failures.append(
                "Every source revision must be a full immutable commit SHA."
            )
    return failures


def check_bundle(lock: dict) -> list[str]:
    """Check required component coverage and immutable source revisions."""
    components = lock["components"]
    failures = []
    names = {component["name"] for component in components}
    if len(components) != len(COMPONENTS) or names != COMPONENTS:
        failures.append(
            "Bundle must record the default pair and deferred Backplane once."
        )
    revisions = [lock["starter"]["revision"]]
    revisions.extend(component["revision"] for component in components)
    return failures + check_revisions(revisions)


def check_catalog(
    root: Path, path: str, revision_key: str, selection: tuple[str, dict]
) -> list[str]:
    """Compare one native catalog with the recorded source identities."""
    name, expected = selection
    catalog = json.loads((root / path).read_text("utf-8"))
    actual = {
        plugin["name"]: (
            plugin["source"].get(revision_key),
            repository_identity(plugin["source"]["url"]),
            plugin["source"].get("source"),
        )
        for plugin in catalog["plugins"]
    }
    failures = []
    if catalog["name"] != name or actual != expected:
        failures.append(f"{path} differs from the recorded catalog/source identities.")
    if len(catalog["plugins"]) != len(expected):
        failures.append(f"{path} contains duplicate component entries.")
    return failures


def check_sources(root: Path) -> list[str]:
    """Return source-coherence failures without modifying files or host state."""
    lock = json.loads((root / ".skills-first/bundle.lock.json").read_text("utf-8"))
    expected = {
        component["name"]: (
            component["revision"],
            repository_identity(component["repository"]),
            "url",
        )
        for component in lock["components"]
    }
    failures = check_bundle(lock)
    selection = lock["catalog"]["name"], expected
    for path, revision_key in CATALOGS.items():
        failures.extend(check_catalog(root, path, revision_key, selection))
    return failures


def check_discovery(root: Path) -> list[str]:
    """Reject duplicate copied skills and unintended component enablement."""
    lock = json.loads((root / ".skills-first/bundle.lock.json").read_text("utf-8"))
    name = lock["catalog"]["name"]
    config = tomllib.loads((root / ".codex/config.toml").read_text("utf-8"))
    plugins = config.get("plugins", {})
    failures = []
    for component in COMPONENTS:
        expected = component != "superpowers-backplane"
        if plugins.get(f"{component}@{name}", {}).get("enabled") is not expected:
            failures.append(f"{component} project enablement must be {expected}.")
    for identity, settings in plugins.items():
        component, separator, marketplace = identity.partition("@")
        if (
            separator
            and component in COMPONENTS
            and marketplace != name
            and settings.get("enabled") is not False
        ):
            failures.append(f"Duplicate component source is enabled: {identity}.")
    return failures + check_copied_skills(root)


def main() -> int:
    """Validate the selected project; installation and loading are separate checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    try:
        failures = check_sources(args.project) + check_discovery(args.project)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Skills stack validation failed: {error}")
        return 1
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("Skills stack sources and project configuration are coherent.")
    print("Native installation and fresh-session discovery require separate evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
