---
name: maintenance-qa
description: Use when reviewing code quality, security, test coverage, dead code, or docstring coverage. Run before merging, before releases, or when auditing repository health.
---

# Maintenance QA

## Overview

Maintenance QA is a unified code quality audit that runs six complementary tools and produces a single pass/fail report. It complements the existing `quality-check` skill (which covers tests, lint, format, type checks, complexity, and native builds) by adding security, dead code, coverage, and docstring analysis.

**Core principle:** Every code quality dimension has a tool. Run them together. Fail fast on regressions.

## When to Use

- Before merging a feature branch
- Before creating a release
- When auditing repository health
- When investigating "why is this code here?"
- When asked "what's our test coverage?"

## Tools

| Tool | Purpose | Command |
|------|---------|---------|
| `uv audit` | Dependency CVE scan | `uv audit` |
| `ruff check --select S` | Security lint (bandit rules) | `uv run ruff check --select S src/` |
| `vulture` | Dead code detection | `uv run vulture src/ --min-confidence 80` |
| `coverage` | Test coverage | `uv run coverage run -m unittest discover -s tests && uv run coverage report` |
| `interrogate` | Docstring coverage | `uv run interrogate src/ --fail-under 0` |
| `mutmut` | Mutation testing | `uv run mutmut run --paths-to-mutate src/` |

## Workflow

### 1. Run the maintenance-qa script

```bash
uv run python .codex/skills/maintenance-qa/scripts/maintenance_qa.py
```

The script runs all six tools, parses their output, and produces a unified report with pass/fail status for each dimension.

### 2. Review findings

The script outputs a summary table:

```
Dimension          Status   Details
─────────────────  ───────  ─────────────────────────────────────────
Dependency CVEs    WARN     4 known CVEs in GDAL (assessed, see SECURITY.md)
Security lint      PASS     0 findings
Dead code          PASS     0 findings
Test coverage      PASS     44% (baseline: 40%)
Docstring coverage WARN     12% (baseline: 10%)
Mutation testing   SKIP     Not yet configured
```

### 3. Address failures

- **Dependency CVEs**: Review `SECURITY.md` for assessed risks. If new CVEs appear, assess impact and document.
- **Security lint**: Fix or add `# noqa: SXXX` with justification.
- **Dead code**: Remove or add to `.vulture_whitelist.py` with justification.
- **Test coverage**: Add tests for uncovered paths. Update baseline in `coverage-baseline.json`.
- **Docstring coverage**: Add docstrings to public APIs. Update baseline in `interrogate-baseline.json`.
- **Mutation testing**: Configure `mutmut` and establish baseline.

## Baselines

Baselines are stored in `.codex/skills/maintenance-qa/`:

- `coverage-baseline.json` — Minimum acceptable test coverage (currently 40%)
- `interrogate-baseline.json` — Minimum acceptable docstring coverage (currently 10%)
- `vulture.whitelist.py` — Known dead code that is intentional (e.g., `Unused/` directory)

## Integration with quality-check

The `maintenance-qa` skill is called by `quality-check` as part of the full repository audit. It can also be run standalone for focused code quality reviews.

## Common Mistakes

- **Ignoring `uv audit` warnings**: Even if CVEs are assessed, new ones may appear. Always check `SECURITY.md` for current assessment.
- **Whitelisting too much dead code**: Vulture finds real dead code. Only whitelist intentional cases (e.g., `Unused/` directory, future features).
- **Lowering coverage baseline**: Coverage should trend up, not down. If it drops, add tests or justify the drop.
- **Skipping mutation testing**: Mutation testing is expensive but valuable. Run it on critical paths (e.g., config parsing, geometry calculations).

## Quick Reference

| Question | Command |
|----------|---------|
| What CVEs affect our dependencies? | `uv audit` |
| Are there security issues in our code? | `uv run ruff check --select S src/` |
| Is there dead code? | `uv run vulture src/ --min-confidence 80` |
| What's our test coverage? | `uv run coverage run -m unittest discover -s tests && uv run coverage report` |
| What's our docstring coverage? | `uv run interrogate src/ --fail-under 0` |
| Are our tests effective? | `uv run mutmut run --paths-to-mutate src/` |
