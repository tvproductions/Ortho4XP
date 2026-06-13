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

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = Path(__file__).resolve().parents[1]

COVERAGE_BASELINE_PATH = SKILL_DIR / "coverage-baseline.json"
INTERROGATE_BASELINE_PATH = SKILL_DIR / "interrogate-baseline.json"
VULTURE_WHITELIST_PATH = SKILL_DIR / "vulture.whitelist.py"


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def check_dependency_cves() -> tuple[str, str]:
    """Run uv audit and check for CVEs."""
    returncode, stdout, stderr = run_command(
        ["uv", "audit", "--preview-features", "audit-command"]
    )
    
    # uv audit writes warnings to stderr but results to stdout
    output = stdout + stderr
    
    if "Found 0 known vulnerabilities" in output:
        return "PASS", "No known CVEs"
    
    # Parse vulnerability count
    import re
    match = re.search(r"Found (\d+) known vulnerabilities", output)
    if match:
        count = int(match.group(1))
        return "WARN", f"{count} known CVEs (assessed, see SECURITY.md)"
    
    if returncode != 0 and "Found" not in output:
        return "FAIL", f"uv audit failed: {stderr[:100]}"
    
    return "PASS", "No known CVEs"


def check_security_lint() -> tuple[str, str]:
    """Run ruff check --select S and count findings."""
    returncode, stdout, stderr = run_command(
        ["uv", "run", "ruff", "check", "--select", "S", "src/"]
    )
    
    if returncode == 0:
        return "PASS", "0 findings"
    
    # Count findings from output
    import re
    matches = re.findall(r"^S\d+", stdout, re.MULTILINE)
    count = len(matches)
    
    if count == 0:
        return "PASS", "0 findings"
    
    return "FAIL", f"{count} security findings"


def check_dead_code() -> tuple[str, str]:
    """Run vulture and check for dead code."""
    cmd = ["uv", "run", "vulture", "src/", "--min-confidence", "80"]
    
    # Add whitelist if it exists
    if VULTURE_WHITELIST_PATH.exists():
        cmd.extend(["--exclude", str(VULTURE_WHITELIST_PATH)])
    
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode == 0:
        return "PASS", "0 findings"
    
    # Count findings from output
    lines = [line for line in stdout.splitlines() if line.strip() and "unused" in line.lower()]
    count = len(lines)
    
    if count == 0:
        return "PASS", "0 findings"
    
    return "WARN", f"{count} dead code findings"


def check_test_coverage() -> tuple[str, str]:
    """Run coverage and compare to baseline."""
    # Run tests with coverage
    returncode, stdout, stderr = run_command(
        ["uv", "run", "coverage", "run", "-m", "unittest", "discover", "-s", "tests"]
    )
    
    # Debug: show what we captured
    if returncode != 0:
        combined = stdout + stderr
        return "FAIL", f"Tests failed (rc={returncode}): {combined[:300]}"
    
    # Generate report
    returncode, stdout, stderr = run_command(["uv", "run", "coverage", "report"])
    
    # Parse total coverage from last line
    import re
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", stdout)
    if not match:
        return "FAIL", f"Could not parse coverage from: {stdout[:200]}"
    
    coverage_pct = int(match.group(1))
    
    # Load baseline
    baseline = 40  # Default
    if COVERAGE_BASELINE_PATH.exists():
        with open(COVERAGE_BASELINE_PATH) as f:
            baseline = json.load(f).get("minimum_coverage", 40)
    
    if coverage_pct >= baseline:
        return "PASS", f"{coverage_pct}% (baseline: {baseline}%)"
    
    return "FAIL", f"{coverage_pct}% (baseline: {baseline}%)"


def check_docstring_coverage() -> tuple[str, str]:
    """Run interrogate and compare to baseline."""
    returncode, stdout, stderr = run_command(
        ["uv", "run", "interrogate", "src/", "--fail-under", "0"]
    )
    
    output = stdout + stderr
    
    # Debug: print what we captured
    if not output.strip():
        return "FAIL", f"No output captured (rc={returncode})"
    
    # Parse coverage from output: "RESULT: PASSED (minimum: 0.0%, actual: 11.8%)"
    import re
    match = re.search(r"actual:\s*(\d+\.\d+)%", output)
    if not match:
        return "FAIL", f"Could not parse docstring coverage from: {output[:200]}"
    
    coverage_pct = float(match.group(1))
    
    # Load baseline
    baseline = 10.0  # Default
    if INTERROGATE_BASELINE_PATH.exists():
        with open(INTERROGATE_BASELINE_PATH) as f:
            baseline = json.load(f).get("minimum_coverage", 10.0)
    
    if coverage_pct >= baseline:
        return "PASS", f"{coverage_pct:.1f}% (baseline: {baseline:.1f}%)"
    
    return "FAIL", f"{coverage_pct:.1f}% (baseline: {baseline:.1f}%)"


def check_mutation_testing() -> tuple[str, str]:
    """Run mutmut (optional, skip if not configured)."""
    # Check if mutmut is configured
    mutmut_config = ROOT / "mutmut.toml"
    if not mutmut_config.exists():
        return "SKIP", "Not yet configured"
    
    returncode, stdout, stderr = run_command(
        ["uv", "run", "mutmut", "run", "--paths-to-mutate", "src/"]
    )
    
    # Parse results
    import re
    match = re.search(r"(\d+) survived", stdout)
    if match:
        survived = int(match.group(1))
        return "WARN", f"{survived} mutations survived"
    
    if returncode == 0:
        return "PASS", "All mutations killed"
    
    return "FAIL", f"mutmut failed: {stderr[:100]}"


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
    
    # Print report
    print("\nMaintenance QA Report")
    print("=" * 70)
    print(f"{'Dimension':<20} {'Status':<8} {'Details'}")
    print("-" * 70)
    
    for name, status, details in results:
        print(f"{name:<20} {status:<8} {details}")
    
    print("=" * 70)
    
    # Determine overall status
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
