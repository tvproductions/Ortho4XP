# Development Guide

## Testing Without Config Initialization

`O4_Config_Utils` is import-safe by default. Importing it validates static
configuration metadata, but does not read `Ortho4XP.cfg`, create config files,
or mutate config-backed globals in other modules.

Runtime code that needs user/default config values must call
`initialize_global_config()` before reading config-backed module globals.
`CFG.Tile` construction performs this lazily for tile-build workflows.

Example:

```python
import O4_Config_Utils  # No file I/O, no global mutation

O4_Config_Utils.initialize_global_config()
```

## Headless CLI Validation Tests

`validate-job` and `build-job --dry-run` must not import GUI modules, import
`O4_Config_Utils`, create `Ortho4XP.cfg`, or create generated runtime
directories. Tests should run these commands from a temporary non-repository
working directory to prove provider resources are resolved from the application
root rather than the process current working directory.

## Sister-Project Upstream Watch

The upstream-watch chore treats the repositories as two different surfaces:

- `Ypsos/ORTHO4XP_V3` is the authoritative engineering source.
- `tvproductions/ORTHO4XP_V3` is a passive synchronization fork. Normal fork
  lag is informational and does not block audit acceptance. Unexpected fork
  commits or divergence are configuration anomalies.

The weekly and manually dispatched
`.github/workflows/upstream-watch.yml` workflow performs lightweight detection
and manages one issue labeled `upstream-watch`. Substantive engineering audits
run locally. The audit parser reads Git blobs, parses Python with `ast`, and
runs targeted static analysis; it never imports or executes upstream code,
installers, hooks, scripts, or submodules.

Check current remote heads without mutating GitHub:

```powershell
uv run python scripts/upstream_watch.py check `
  --state .github/upstream-watch.json `
  --json
```

Generate a retained local report for an explicit author range:

```powershell
uv run python scripts/upstream_watch.py audit `
  --state .github/upstream-watch.json `
  --base 4ca0a8d404b078ad899979bafde84769a0fb235b `
  --head 8a25af093af758292b4ef4c2caff93719cb1a54a `
  --output .upstream-watch/2026-07-19-4ca0a8d-8a25af0.json
```

Raw reports under `.upstream-watch/` are ignored local evidence. The durable
decisions belong in `docs/upstream/ORTHO4XP_V3-audit.md` as exact single-line
`upstream-watch:audit`, `upstream-watch:finding`, and
`upstream-watch:reviewed-no-action` records.

Validate exact path coverage and evidence consistency:

```powershell
uv run python scripts/upstream_watch.py validate `
  --state .github/upstream-watch.json `
  --report .upstream-watch/2026-07-19-4ca0a8d-8a25af0.json `
  --ledger docs/upstream/ORTHO4XP_V3-audit.md `
  --json
```

Accept a completed audit only after every changed path has exactly one final
disposition and no finding remains `investigate`:

```powershell
uv run python scripts/upstream_watch.py accept `
  --state .github/upstream-watch.json `
  --report .upstream-watch/2026-07-19-4ca0a8d-8a25af0.json `
  --ledger docs/upstream/ORTHO4XP_V3-audit.md `
  --date 2026-07-19
```

`accept` verifies the explicit SHA range, manifest digest, path count, ledger
coverage, and current accepted baseline before replacing the state file
atomically. Never run it merely because the detector found new commits.

Exit statuses are stable:

- `0`: author baseline is current and the passive fork is synchronized or
  normally behind;
- `1`: an operational or validation failure prevented a trustworthy result;
- `2`: author changes require engineering review;
- `3`: author baseline is current but the passive fork has unexpected commits
  or divergence;
- `4`: rewritten author history requires manual intervention and a full-tree
  audit.

The workflow treats statuses `2`, `3`, and `4` as managed review states rather
than infrastructure failures. Only status `1` fails the scheduled job.
