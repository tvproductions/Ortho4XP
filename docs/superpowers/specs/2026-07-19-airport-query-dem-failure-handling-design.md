# Airport-Query and DEM Failure Handling Design

## Purpose

Vector-map construction must continue safely when the non-fatal OpenStreetMap
airport query fails. The current control flow returns integer sentinels before
initializing the tile DEM, so road processing and later vector stages receive
invalid airport values and can dereference an uninitialized `tile.dem`.

This design separates the required elevation dependency from optional airport
data and replaces ambiguous failure sentinels with the same concrete types the
successful path returns.

## Scope

The change is limited to vector-map airport-query failure handling in
`src/O4_Vector_Map.py` and deterministic coverage in `tests/`. It does not
change airport discovery, DEM source selection, road-leveling policy, or any
X-Plane 12 scenery semantics.

## Control Flow

`build_poly_file()` initializes `tile.dem` immediately after creating the
vector map and before calling `include_airports()`. DEM construction continues
to use the tile latitude, longitude, `custom_dem`, and `fill_nodata` settings
already used by the existing airport path.

`include_airports()` no longer initializes the DEM. When its OSM query
succeeds, it retains the existing airport discovery, geometry construction,
DEM smoothing, patch inclusion, encoding, and airport-mask behavior.

When the airport query fails, `include_airports()`:

- emits a human-readable warning through the normal UI output;
- records the failure through the structured logging surface;
- returns a `1001 x 1001` NumPy boolean array containing only `False` values;
- returns an empty Shapely `Polygon` for the treated airport area; and
- skips airport discovery, geometry, smoothing, patch, and encoding work.

`build_poly_file()` then passes those typed empty values to `include_roads()`
and continues the remaining vector stages. The empty values preserve the
successful-path contracts: road indexing remains valid, and geometric
buffer/difference operations treat the airport area as empty.

## Error Handling

Airport-query failure remains non-fatal because other vector inputs can still
produce a usable tile. The warning identifies the tile coordinates and states
that vector construction is continuing without airport data. The failure does
not set the build context red flag.

DEM construction failures retain their existing behavior and are not converted
into airport-query failures. This prevents a required elevation dependency
from being silently treated as optional.

## Testing

Deterministic standard-library `unittest` coverage will mock the network-facing
OSM query boundary and the DEM constructor without performing network or GDAL
command-line operations.

Tests will verify that:

- a failed airport query returns the exact boolean mask shape and an empty
  Shapely polygon rather than `(0, 0)`;
- the failure emits the expected warning and bypasses airport processing;
- `build_poly_file()` initializes the DEM before airport and road processing;
- road processing receives the typed empty airport values and an initialized
  `tile.dem`; and
- the successful airport path reuses the builder-initialized DEM rather than
  constructing a second DEM.

Focused tests will run first during each red/green cycle. Completion requires
the full `unittest` suite, changed-file Ruff formatting and linting, changed-file
`ty`, and the repository quality check.

## Repository and Issue Updates

After verification, `TODO-041-1` will be marked done with implementation and
verification evidence. GitHub issue #38 will receive the same evidence and be
closed. The change remains strictly X-Plane 12 compatible.
