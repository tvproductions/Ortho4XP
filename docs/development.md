# Development Guide

## Testing Without Config Initialization

Set `ORTHO4XP_SKIP_CONFIG_INIT=1` to import `O4_Config_Utils` without
triggering config file reads or global state mutation. This is useful for
unit tests that need to control config values explicitly.

Example:

```python
import os
os.environ['ORTHO4XP_SKIP_CONFIG_INIT'] = '1'
import O4_Config_Utils  # No file I/O, no global mutation
```

## Headless CLI Validation Tests

`validate-job` and `build-job --dry-run` must not import GUI modules, import
`O4_Config_Utils`, create `Ortho4XP.cfg`, or create generated runtime
directories. Tests should run these commands from a temporary non-repository
working directory to prove provider resources are resolved from the application
root rather than the process current working directory.
