# TODO-038 Smart Cache Design

## Goal

Add SHA256-based tile build caching so unchanged full tile builds can return
without rerunning the expensive vector, mesh, mask, and texture pipeline.

## Scope

The first cache gate applies to complete tile builds only:

- GUI and CLI all-in-one builds through `O4_Build_Core.build_tile_all()`.
- Batch tile builds only when their selected steps are exactly
  `("vector", "mesh", "masks", "tile")`.

Partial batch builds must always run because the caller explicitly selected a
targeted rebuild step. Overlay builds are excluded because they write a
separate package and are not part of the tile mesh/ortho output contract.

## Cache Contract

Each successful full tile build writes `tile_meta.json` in `tile.build_dir`.
The file contains:

- `schema_version`: cache metadata schema version.
- `tile`: latitude and longitude.
- `build_parameters`: deterministic snapshot of tile configuration values from
  `O4_Cfg_Vars.list_tile_vars`.
- `parameter_hash`: SHA256 of the canonical parameter payload.

The canonical hash input includes a cache schema version, lat/lon, and every
configured tile variable exposed on the tile object. Values are converted into
JSON-stable shapes before hashing so tuples/lists/dicts compare by value and
dict keys are sorted.

`O4_Build_Cache` owns the tile-facing cache API. `O4_Build_Cache_IO` owns the
low-level JSON reading, atomic writing, canonical value conversion, and SHA256
payload hashing so the orchestration-facing module stays small.

## Flow

Before a full build runs, `O4_Build_Core` asks the cache helper whether
`tile_meta.json` matches the current tile parameters. On a hit, the build
publishes `CACHE_HIT` with lat, lon, mode, metadata path, and hash, then returns
the same public success result as a completed full build. It does not emit
pipeline step or progress events because no steps were executed.

After a full build succeeds, the helper writes `tile_meta.json` atomically using
a same-directory temporary file and `os.replace()`. A write failure is logged
but does not turn a successful scenery build into a failed build.

Malformed, missing, or stale metadata is treated as a cache miss. The full
build runs and replaces stale metadata after success.

## Tests

Unit tests cover deterministic hash behavior, hit/miss behavior, malformed
metadata misses, metadata writes, all-in-one skip behavior, full batch skip
behavior, and partial batch non-skip behavior.
