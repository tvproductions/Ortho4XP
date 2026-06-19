# Superpowers Source

Vendored into this repository from:

- Repository: https://github.com/obra/superpowers
- Commit: 896224c4b1879920ab573417e68fd51d2ccc9072
- Codex install reference: https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/.codex/INSTALL.md

The upstream `.git` directory is intentionally not vendored inside this
repository. Update by fetching upstream into a temporary directory and replacing
this `.agents/skills/superpowers` working tree.

Local hygiene patch after vendoring:

- Removed trailing whitespace from `README.md` and `RELEASE-NOTES.md` so the
  repository `git diff --check` gate remains clean.
- Applied `ruff format` and explicit `TypedDict` annotations to
  `tests/claude-code/analyze-token-usage.py` so the repository format and type
  gates remain clean.
