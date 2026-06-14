#!/usr/bin/env python3
"""
Maintenance QA - Unified code quality audit.

Runs six complementary tools and produces a single pass/fail report:
- uv audit: Dependency CVE scan
- ruff check --select S: Security lint (bandit rules)
- vulture: Dead code detection
- coverage: Test coverage
- interrogate: Docstring coverage
- mutmut: Mutation testing (optional)
"""

import sys

from maintenance_dead_code import check_dead_code
from maintenance_dependency import check_dependency_cves
from maintenance_docstrings import check_docstring_coverage
from maintenance_mutation import check_mutation_testing
from maintenance_security import check_security_lint
from maintenance_test_coverage import check_test_coverage


def main() -> int:
    """Run all checks and produce unified report."""
    checks = [
        ("Dependency CVEs", check_dependency_cves),
        ("Security lint", check_security_lint),
        ("Dead code", check_dead_code),
        ("Test coverage", check_test_coverage),
        ("Docstring coverage", check_docstring_coverage),
        ("Mutation testing", check_mutation_testing),
    ]

    results = []
    for name, check_fn in checks:
        status, details = check_fn()
        results.append((name, status, details))

    print("\nMaintenance QA Report")
    print("=" * 70)
    print(f"{'Dimension':<20} {'Status':<8} {'Details'}")
    print("-" * 70)

    for name, status, details in results:
        print(f"{name:<20} {status:<8} {details}")

    print("=" * 70)

    statuses = [status for _, status, _ in results]
    if "FAIL" in statuses:
        print("\nResult: FAIL")
        return 1

    if "WARN" in statuses:
        print("\nResult: PASS (with warnings)")
        return 0

    print("\nResult: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
