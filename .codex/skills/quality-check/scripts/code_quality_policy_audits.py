from __future__ import annotations

import re
import tokenize
from pathlib import Path

from code_quality_models import (
    CodeQualityFinding,
    relative_project_path,
    scan_python_files,
)


FORBIDDEN_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore\[")
FORBIDDEN_TEST_TIER_DIRS = ("integration", "e2e", "slow", "bdd")
FORBIDDEN_TEST_TIER_FLAGS = ("--integration", "--e2e", "--slow", "--bdd-only")
TEST_TIER_FLAG_SCAN_BASES = [
    "Ortho4XP.py",
    "src",
    ".codex/skills/quality-check/scripts",
    ".codex/skills/repo-hygiene/scripts",
    ".codex/skills/git-sync/scripts",
]
TEST_TIER_FLAG_SCAN_EXCLUDED_NAMES = {"code_quality_policy_audits.py"}


def _comment_tokens(path: Path) -> list[tokenize.TokenInfo]:
    try:
        with path.open("rb") as handle:
            return [
                token
                for token in tokenize.tokenize(handle.readline)
                if token.type == tokenize.COMMENT
            ]
    except (OSError, SyntaxError, tokenize.TokenError):
        return []


def audit_type_ignores(
    project_root: Path, paths: list[Path] | None = None
) -> list[CodeQualityFinding]:
    scanned = scan_python_files(project_root) if paths is None else paths
    return [
        CodeQualityFinding(
            check="type_ignores",
            path=relative_project_path(path, project_root),
            message="`# type: ignore[<code>]` is not honored by ty; use bare `# type: ignore` or `# ty: ignore[<ty-code>]`.",
            severity="block",
            line=token.start[0],
        )
        for path in scanned
        for token in _comment_tokens(path)
        if FORBIDDEN_TYPE_IGNORE.search(token.string)
    ]


def _test_tier_dir_findings(project_root: Path) -> list[CodeQualityFinding]:
    tests_root = project_root / "tests"
    if not tests_root.is_dir():
        return []
    return [
        CodeQualityFinding(
            check="test_tiers",
            path=relative_project_path(tests_root / name, project_root),
            message=f"Forbidden test tier `tests/{name}/`; use deterministic unittest discovery under `tests/`.",
            severity="block",
        )
        for name in FORBIDDEN_TEST_TIER_DIRS
        if (tests_root / name).exists()
    ]


def _text_files_from_base(base_path: Path) -> list[Path]:
    if not base_path.exists():
        return []
    if base_path.is_file():
        return [base_path]
    return [item for item in base_path.rglob("*") if item.is_file()]


def _scanned_text_files(project_root: Path) -> list[Path]:
    return [
        item
        for base in TEST_TIER_FLAG_SCAN_BASES
        for item in _text_files_from_base(project_root / base)
        if _is_scanned_text_file(item)
    ]


def _is_scanned_text_file(path: Path) -> bool:
    return path.suffix in {".py", ".md", ".toml"} and (
        path.name not in TEST_TIER_FLAG_SCAN_EXCLUDED_NAMES
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def _test_tier_flag_findings(project_root: Path) -> list[CodeQualityFinding]:
    return [
        CodeQualityFinding(
            check="test_tiers",
            path=relative_project_path(item, project_root),
            message=f"Forbidden third-tier test flag `{flag}`.",
            severity="block",
        )
        for item in _scanned_text_files(project_root)
        for flag in FORBIDDEN_TEST_TIER_FLAGS
        if flag in _read_text(item)
    ]


def audit_test_tiers(project_root: Path) -> list[CodeQualityFinding]:
    findings = _test_tier_dir_findings(project_root)
    findings.extend(_test_tier_flag_findings(project_root))
    return findings
