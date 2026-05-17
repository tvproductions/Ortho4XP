from __future__ import annotations

import ast
from pathlib import Path

from code_quality_models import (
    CLASS_LINE_LIMIT,
    CLASS_SIZE_WAIVERS,
    MODULE_HARD_LINE_LIMIT,
    MODULE_SIZE_WAIVERS,
    MODULE_SOFT_LINE_LIMIT,
    CodeQualityFinding,
    line_count,
    relative_project_path,
    scan_python_files,
    stale_waiver_findings,
)


def _module_size_finding(
    rel: str, lines: int, waivers: dict[str, str]
) -> CodeQualityFinding | None:
    if lines > MODULE_HARD_LINE_LIMIT and rel in waivers:
        return CodeQualityFinding(
            check="module_size",
            path=rel,
            message=f"Module spans {lines} lines (>{MODULE_HARD_LINE_LIMIT}) under waiver: {waivers[rel]}",
            severity="warn",
        )
    if lines > MODULE_HARD_LINE_LIMIT:
        return CodeQualityFinding(
            check="module_size",
            path=rel,
            message=f"Module spans {lines} lines (>{MODULE_HARD_LINE_LIMIT}); split it or add an explicit waiver with rationale.",
            severity="block",
        )
    if lines > MODULE_SOFT_LINE_LIMIT:
        return CodeQualityFinding(
            check="module_size",
            path=rel,
            message=f"Module spans {lines} lines (>{MODULE_SOFT_LINE_LIMIT}); watch for file-scale drift.",
            severity="warn",
        )
    return None


def audit_module_size(
    project_root: Path,
    paths: list[Path] | None = None,
    waivers: dict[str, str] | None = None,
) -> list[CodeQualityFinding]:
    waived = MODULE_SIZE_WAIVERS if waivers is None else waivers
    scanned = scan_python_files(project_root) if paths is None else paths
    existing = {relative_project_path(path, project_root) for path in scanned}
    findings = [
        finding
        for path in scanned
        if (
            finding := _module_size_finding(
                relative_project_path(path, project_root), line_count(path), waived
            )
        )
    ]
    findings.extend(
        stale_waiver_findings("module_size", "MODULE_SIZE_WAIVERS", waived, existing)
    )
    return findings


def _class_size_finding(
    rel: str, node: ast.ClassDef, waivers: dict[str, str]
) -> tuple[str, CodeQualityFinding | None]:
    end = getattr(node, "end_lineno", node.lineno)
    span = end - node.lineno + 1
    key = f"{rel}::{node.name}"
    if span <= CLASS_LINE_LIMIT:
        return key, None
    if key in waivers:
        return key, CodeQualityFinding(
            check="class_size",
            path=rel,
            message=f"Class `{node.name}` spans {span} lines (>{CLASS_LINE_LIMIT}) under waiver: {waivers[key]}",
            severity="warn",
            line=node.lineno,
        )
    return key, CodeQualityFinding(
        check="class_size",
        path=rel,
        message=f"Class `{node.name}` spans {span} lines (>{CLASS_LINE_LIMIT}); split it or add an explicit waiver with rationale.",
        severity="block",
        line=node.lineno,
    )


def _class_nodes(path: Path) -> list[ast.ClassDef]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    return [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def audit_class_size(
    project_root: Path,
    paths: list[Path] | None = None,
    waivers: dict[str, str] | None = None,
) -> list[CodeQualityFinding]:
    waived = CLASS_SIZE_WAIVERS if waivers is None else waivers
    scanned = scan_python_files(project_root) if paths is None else paths
    extant: set[str] = set()
    findings: list[CodeQualityFinding] = []
    for path in scanned:
        rel = relative_project_path(path, project_root)
        for node in _class_nodes(path):
            key, finding = _class_size_finding(rel, node, waived)
            extant.add(key)
            if finding:
                findings.append(finding)
    findings.extend(
        stale_waiver_findings("class_size", "CLASS_SIZE_WAIVERS", waived, extant)
    )
    return findings
