# Native Sources

This directory contains the C sources for native mesh utilities that Ortho4XP
ships as platform-specific executables under `Utils/win`, `Utils/mac`, and
`Utils/lin`.

## Runtime Bindings

The Python runtime does not import or bind to these C files directly. It invokes
the built executables from `src/O4_Mesh_Utils.py`:

- `Triangle4XP.c` builds the `Triangle4XP` helper used for Ortho4XP mesh
  generation.
- `triangle.c` builds the generic `triangle` helper used during mesh
  reorganization.

Historical source snapshots should not remain as active CMake targets unless
the runtime or release process intentionally ships a corresponding executable.
