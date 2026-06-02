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
