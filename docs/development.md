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
