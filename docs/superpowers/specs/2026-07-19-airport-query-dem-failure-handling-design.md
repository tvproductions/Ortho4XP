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

The change is limited to vector-map dependency ordering and airport-query
failure handling in `src/O4_Vector_Map.py`, plus deterministic coverage in
`tests/`. Moving custom-patch processing out of the airport-success branch is
part of this correction because patches are independent vector inputs. The
change does not alter patch semantics, airport discovery, DEM source selection,
road-leveling policy, or any X-Plane 12 scenery semantics.

## Control Flow

`build_poly_file()` initializes `tile.dem` immediately after creating the
vector map. DEM construction continues to use the tile latitude, longitude,
`custom_dem`, and `fill_nodata` settings already used by the existing airport
path. Loading the DEM at this point is intentional: patches, roads, coastline,
water, and the orthogrid all consume elevation data, so it is a required vector
build dependency even when optional airport data is unavailable. This may move
the existing DEM cost earlier, but it does not add a second construction.

`include_airports()` no longer owns DEM initialization. It attempts the airport
query and, when successful, retains the existing airport discovery, geometry
construction, and DEM smoothing behavior. It then calls `include_patches()`
exactly once regardless of query success. Keeping patch processing after
airport smoothing on the successful path preserves the elevations currently
used by custom patches, while placing it outside the success-only branch keeps
patches available during an airport-query outage.

On success, airport encoding retains the patch-name conflict input and helipad
flattening retains the union of patch and airport areas. `include_airports()`
returns three values with separate meanings: the airport boolean mask, the
runway/taxiway/apron-area geometry, and the patch-area geometry. The builder
unions the two areas before passing the combined treated area to road
processing.

When the airport query fails, `include_airports()`:

- emits this exact human-readable message through `UI.vprint(1, ...)`:

  ```text
  WARNING: Airport OSM query failed; continuing vector construction without airport data.
  ```

- records an `Airport OSM query failed` event through `UI.log_event()` with
  level `WARNING` and context fields `lat`, `lon`, and
  `action="continue_without_airport_data"`;
- returns a `1001 x 1001` NumPy boolean array containing only `False` values;
- returns an empty Shapely `Polygon` for the airport area; and
- returns the independently processed patch area as its third result; and
- skips airport discovery, geometry, smoothing, and airport encoding work.

The builder still retains and encodes custom patches when the airport query
fails. It unions the empty airport area with the patch area, passes the boolean
airport mask and combined treated area to `include_roads()`, and continues the
remaining vector stages. With no patches, that union remains empty. The values
preserve the successful-path contracts: road indexing remains valid, and
geometric buffer/difference operations treat the airport area as empty.

## Error Handling

Airport-query failure remains non-fatal because other vector inputs can still
produce a usable tile. Coordinates are machine-readable in the structured
event context, while the human message states that vector construction is
continuing without airport data. The failure does not set the build context red
flag. Separate UI and event calls are deliberate: `vprint()` does not write a
structured event, and `log_event()` does not guarantee console visibility.

DEM construction failures retain their existing behavior and are not converted
into airport-query failures. This prevents a required elevation dependency
from being silently treated as optional.

## Testing

Deterministic standard-library `unittest` coverage will mock the network-facing
OSM query boundary and the DEM constructor without performing network or GDAL
command-line operations.

Tests will verify observable contracts rather than incidental call counts or
entire log-line serialization:

- a failed airport query returns the exact boolean mask shape and an empty
  Shapely polygon rather than `(0, 0)`;
- the failure emits the exact human warning and a `WARNING` event with the
  specified message and context, then bypasses airport processing;
- `build_poly_file()` initializes the DEM before airport and road processing;
- road processing receives the typed empty airport values and an initialized
  `tile.dem`;
- custom patches are processed once and remain in the road-exclusion area when
  the airport query fails;
- successful builds continue processing patches after airport DEM smoothing;
- an empty airport `Polygon` passes through the real Shapely
  buffer/difference path used by road processing without a type error; and
- the successful airport path reuses the builder-initialized DEM rather than
  constructing a second DEM, preserves patch-aware airport encoding, and
  produces the same combined treated area.

Mocks are restricted to external or expensive boundaries such as OSM queries,
DEM construction, and file output. Assertions target ordering only where the
ordering is itself the requirement; geometry and array assertions exercise the
real NumPy and Shapely values.

Focused tests will run first during each red/green cycle. Completion requires
the full `unittest` suite, changed-file Ruff formatting and linting, changed-file
`ty`, and the repository quality check.

## Repository and Issue Updates

After verification, `TODO-041-1` will be marked done with implementation and
verification evidence. GitHub issue #38 will receive the same evidence and be
closed. The change remains strictly X-Plane 12 compatible.
