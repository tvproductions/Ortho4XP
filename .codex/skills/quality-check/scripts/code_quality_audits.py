from __future__ import annotations

from pathlib import Path

from code_quality_models import (
    CLASS_LINE_LIMIT,
    MODULE_HARD_LINE_LIMIT,
    MODULE_SOFT_LINE_LIMIT,
    CodeQualityFinding,
)
from code_quality_policy_audits import audit_test_tiers, audit_type_ignores
from code_quality_size_audits import audit_class_size, audit_module_size


def collect_code_quality_findings(project_root: Path) -> list[CodeQualityFinding]:
    findings: list[CodeQualityFinding] = []
    findings.extend(audit_type_ignores(project_root))
    findings.extend(audit_test_tiers(project_root))
    findings.extend(audit_module_size(project_root))
    findings.extend(audit_class_size(project_root))
    return findings


__all__ = [
    "CLASS_LINE_LIMIT",
    "MODULE_HARD_LINE_LIMIT",
    "MODULE_SOFT_LINE_LIMIT",
    "CodeQualityFinding",
    "audit_class_size",
    "audit_module_size",
    "audit_test_tiers",
    "audit_type_ignores",
    "collect_code_quality_findings",
]
