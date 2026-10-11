---
name: maintenance-qa
description: Run explicitly requested deeper quality, security, dependency, coverage, dead-code, docstring, complexity, import-boundary or mutation assessments.
---

# Maintenance QA

Deep hygiene is an explicit maintenance action. Never add these tools to
pre-commit, manual hooks, CI, or automatically invoke them after routine edits.

```powershell
uv run --group hygiene python .codex/skills/maintenance-qa/scripts/maintenance_qa.py
```

The command independently assesses complexity, pip-audit, deptry, Import Linter,
Bandit, Vulture, Coverage.py and Interrogate. It saves command receipts and a
summary in a new `tmp/maintenance-hygiene-*` directory. Failed tools and invalid
measurements remain FAIL; other independent dimensions still run. Legacy
absolute complexity findings and unresolved dependency/security/dead-code
findings remain failed hygiene and need precise tracking evidence.

- Ruff C901 ceiling 20 and complexipy ceiling 15 are independent metrics.
  Lizard's function, module arithmetic mean, and function-weighted overall mean
  ceilings are 20 under `lizard-functions-v1`. Preserve the project's stricter
  Lizard ratchet and actual Cohesion percentage receipts. The historical LCOM4
  policy is unverified and remains a failed measurement-policy gap.
  No baseline can waive absolute failures.
- Bandit reports severity/confidence/context. Never blanket-suppress results.
- Vulture retains reviewed public-consumer whitelist entries. Investigate
  external and dynamic consumers before deleting a candidate.
- Coverage measures source statements and branches through unittest. Preserve
  `coverage-baseline.json`; assess changed measurement semantics explicitly.
- Interrogate measures presence; review docstrings for correctness/usefulness.
  Preserve `interrogate-baseline.json`; never add filler to raise a score.
- deptry inspects `src` with actual project metadata and explicit package/module
  mappings. Findings do not authorize removing domain dependencies.
- pip-audit audits the host-selected complete runtime/dev/hygiene lock export
  with hashes, `--no-deps --disable-pip`, without a second resolver. Local-wheel
  exact identities and byte hashes are appended to the derived requirements
  receipt; any skipped identity or advisory is FAIL. This is a known-advisory
  assessment, not a claim that vulnerabilities are absent.
- Import Linter's standard forbidden contract checks a source-only graph of the
  actual flat O4 modules, including conditional and indirect edges. The adapter
  avoids the CLI's package-only limitation without repackaging application code.
  All active O4 modules must match the explicit roots in `importlinter.ini`.
  The reviewed pure configuration/source definition boundary prohibits UI,
  orchestration, HTTP and GDAL adapter imports. Dynamic imports require separate
  consumer review.

Cosmic Ray 8.7.0 is selected after an actual Python 3.14.8 synthetic unittest
probe: clean baseline; 13 mutants killed; zero tool errors. Mutation is bounded
and additionally requested:

```powershell
uv run --group hygiene python .codex/skills/maintenance-qa/scripts/maintenance_qa.py --mutation-config tmp/ASSESSMENT/cosmic-ray.toml --mutation-workdir tmp/ASSESSMENT
```

Prepare an unused disposable directory with copied selected code/tests and a
config for one file, unittest, and per-test timeout at most 60 seconds. At most
200 jobs and 600 seconds per analyzer execution are allowed. Source and
operational data are never mutation targets. Retain baseline/session databases
and outcome counts. Classify survivors, equivalent mutants, timeouts and worker
errors separately; a broken baseline or missing result is a failure.

See [project Python engineering](../../../docs/agents/python-engineering.md)
for exact semantics and migration evidence. No application-wide mutation scope
or transplanted upstream percentage threshold is authorized.
