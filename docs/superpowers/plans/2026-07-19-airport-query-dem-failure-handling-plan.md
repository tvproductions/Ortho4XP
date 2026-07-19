# Airport-Query and DEM Failure Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep vector-map construction safe and complete when the optional airport OSM query fails, without losing custom patches or exposing downstream stages to an uninitialized DEM.

**Architecture:** The vector-input preparation boundary owns required DEM initialization before `build_poly_file()` invokes airport or road processing. `include_airports()` keeps successful patch processing after airport smoothing, executes patches on the query-failure path, and returns airport and patch areas separately so the builder can form the road-exclusion union without conflating typed-empty airport data with valid patches.

**Tech Stack:** Python 3.13, standard-library `unittest` and `unittest.mock`, NumPy, Shapely, `uv`, Ruff, ty.

**Execution note:** Completed on 2026-07-19. Complexity feedback led to the
small `O4_Vector_Map_Inputs` preparation boundary and split deterministic test
helpers. The implementation also replaced deprecated Shapely `resolution`
keywords with `quad_segs` after the real empty geometry exposed the warning.
The final review added an ordering assertion so failure reporting is guaranteed
to precede custom-patch processing.

## Global Constraints

- Use Python 3.13.x through `uv` and standard-library `unittest` only.
- Tests must be deterministic and require no network, X-Plane installation, GDAL command-line tools, or imagery providers.
- Preserve current successful-path ordering: airport DEM smoothing occurs before custom-patch encoding.
- Remain strictly X-Plane 12 compatible.
- Do not alter DEM source selection, airport discovery policy, patch semantics, or road-leveling policy.
- Use the exact warning and structured event contract from the approved design.

---

### Task 1: Implement Typed Airport Failure and Required DEM Ordering

**Files:**
- Modify: `src/O4_Vector_Map.py:26-230`
- Modify: `src/O4_Vector_Utils.py`
- Create: `src/O4_Vector_Map_Inputs.py`
- Create: `tests/_vector_map_airport_helpers.py`
- Create: `tests/test_vector_map_airport_failure.py`
- Create: `tests/test_vector_map_dem_ordering.py`

**Interfaces:**
- Consumes: `DEM.DEM(lat, lon, custom_dem, fill_nodata, info_only=False)`, `include_patches(vector_map, tile) -> tuple[BaseGeometry, list[str]]`, and the existing airport discovery/encoding modules.
- Produces: `include_airports(vector_map, tile) -> tuple[numpy.ndarray, BaseGeometry, BaseGeometry]`, where the results are airport mask, airport area, and patch area respectively.
- Produces: `O4_Vector_Map_Inputs.prepare()` initializes `tile.dem`; `build_poly_file()` unions airport and patch areas and passes the combined area plus the airport mask to `include_roads()`.

- [x] **Step 1: Write the failing airport-query test**

Create `tests/test_vector_map_airport_failure.py` with a test that patches only the network query, logging surfaces, patch boundary, and airport-discovery boundary:

```python
import os
import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

import numpy
from shapely import geometry, ops

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Vector_Map as VMAP


WARNING = (
    "WARNING: Airport OSM query failed; continuing vector construction "
    "without airport data."
)


class AirportQueryFailureTests(unittest.TestCase):
    def test_failed_query_returns_typed_empty_airport_data_and_preserves_patches(self):
        tile = SimpleNamespace(lat=12, lon=-123, dem=object())
        vector_map = object()
        patch_area = geometry.box(0.1, 0.1, 0.2, 0.2)

        with (
            mock.patch.object(VMAP.OSM, "OSM_layer", return_value=object()),
            mock.patch.object(
                VMAP.OSM, "OSM_queries_to_OSM_layer", return_value=False
            ),
            mock.patch.object(
                VMAP, "include_patches", return_value=(patch_area, ["custom"])
            ) as include_patches,
            mock.patch.object(VMAP.APT_DISC, "discover_airport_names") as discover,
            mock.patch.object(VMAP.UI, "vprint") as vprint,
            mock.patch.object(VMAP.UI, "log_event") as log_event,
        ):
            airport_mask, airport_area, returned_patch_area = VMAP.include_airports(
                vector_map, tile
            )

        self.assertEqual(airport_mask.shape, (1001, 1001))
        self.assertEqual(airport_mask.dtype, numpy.dtype(bool))
        self.assertFalse(airport_mask.any())
        self.assertIsInstance(airport_area, geometry.Polygon)
        self.assertTrue(airport_area.is_empty)
        self.assertTrue(returned_patch_area.equals(patch_area))
        include_patches.assert_called_once_with(vector_map, tile)
        discover.assert_not_called()
        vprint.assert_any_call(1, WARNING)
        log_event.assert_called_once_with(
            "Airport OSM query failed",
            level="WARNING",
            context={
                "lat": 12,
                "lon": -123,
                "action": "continue_without_airport_data",
            },
        )

        excluded = VMAP.VECT.improved_buffer(airport_area, 15, 0, 0)
        road = geometry.LineString([(0, 0), (1, 1)])
        self.assertTrue(excluded.is_empty)
        self.assertTrue(road.difference(excluded).equals(road))


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run the focused test and verify RED**

Run:

```powershell
uv run python -m unittest tests.test_vector_map_airport_failure.AirportQueryFailureTests.test_failed_query_returns_typed_empty_airport_data_and_preserves_patches -v
```

Expected: FAIL because the current failure path returns two integer sentinels, does not process patches, and emits no warning event.

- [x] **Step 3: Implement the minimal failed-query contract**

In `include_airports()`, store the query result, emit the exact warning/event when false, skip discovery/smoothing, call `include_patches()` once, and return:

```python
airport_mask = numpy.zeros((1001, 1001), dtype=bool)
airport_area = geometry.Polygon()
return (airport_mask, airport_area, patches_area)
```

Use this exact event call:

```python
UI.log_event(
    "Airport OSM query failed",
    level="WARNING",
    context={
        "lat": tile.lat,
        "lon": tile.lon,
        "action": "continue_without_airport_data",
    },
)
```

- [x] **Step 4: Re-run the focused test and verify GREEN**

Run the command from Step 2.

Expected: PASS with the real NumPy mask, Shapely polygon, and geometry operations.

- [x] **Step 5: Write the failing successful-path regression test**

Add this second test to `AirportQueryFailureTests`:

```python
    def test_successful_query_reuses_dem_and_preserves_patch_order(self):
        tile = SimpleNamespace(lat=12, lon=-123, dem=object())
        vector_map = object()
        airport_layer = object()
        airport_mask = numpy.zeros((1001, 1001), dtype=bool)
        airport_mask[500, 500] = True
        airport_area = geometry.box(0.4, 0.4, 0.6, 0.6)
        patch_area = geometry.box(0.1, 0.1, 0.2, 0.2)
        patch_names = ["custom"]
        order = []

        with (
            mock.patch.object(VMAP.OSM, "OSM_layer", return_value=airport_layer),
            mock.patch.object(
                VMAP.OSM, "OSM_queries_to_OSM_layer", return_value=True
            ),
            mock.patch.object(VMAP.APT_DISC, "discover_airport_names"),
            mock.patch.object(VMAP.APT_DISC, "attach_surfaces_to_airports"),
            mock.patch.object(VMAP.APT_DISC, "sort_and_reconstruct_runways"),
            mock.patch.object(VMAP.APT_DISC, "discard_unwanted_airports"),
            mock.patch.object(VMAP.APT_DISC, "list_airports_and_runways"),
            mock.patch.object(VMAP.APT_GEOM, "build_hangar_areas"),
            mock.patch.object(VMAP.APT_GEOM, "build_apron_areas"),
            mock.patch.object(VMAP.APT_GEOM, "build_taxiway_areas"),
            mock.patch.object(VMAP.APT_GEOM, "update_airport_boundaries"),
            mock.patch.object(
                VMAP.APT_GEOM,
                "smooth_raster_over_airports",
                side_effect=lambda *_args: order.append("smooth"),
            ),
            mock.patch.object(
                VMAP,
                "include_patches",
                side_effect=lambda *_args: (
                    order.append("patches") or (patch_area, patch_names)
                ),
            ) as include_patches,
            mock.patch.object(
                VMAP.APT_ENC,
                "encode_runways_taxiways_and_aprons",
                return_value=airport_area,
            ) as encode_airports,
            mock.patch.object(VMAP.APT_ENC, "encode_hangars"),
            mock.patch.object(VMAP.APT_ENC, "flatten_helipads") as flatten_helipads,
            mock.patch.object(
                VMAP.APT_GEOM, "build_airport_array", return_value=airport_mask
            ),
            mock.patch.object(VMAP.DEM, "DEM") as dem_constructor,
            mock.patch.object(VMAP.UI, "vprint"),
        ):
            returned_mask, returned_airport_area, returned_patch_area = (
                VMAP.include_airports(vector_map, tile)
            )

        self.assertIs(returned_mask, airport_mask)
        self.assertTrue(returned_airport_area.equals(airport_area))
        self.assertTrue(returned_patch_area.equals(patch_area))
        self.assertEqual(order, ["smooth", "patches"])
        dem_constructor.assert_not_called()
        include_patches.assert_called_once_with(vector_map, tile)
        encode_airports.assert_called_once_with(
            tile, airport_layer, mock.ANY, vector_map, patch_names
        )
        flatten_helipads.assert_called_once()
        expected_union = ops.unary_union([patch_area, airport_area])
        self.assertTrue(flatten_helipads.call_args.args[-1].equals(expected_union))
```

- [x] **Step 6: Run the successful-path test and verify RED**

Run:

```powershell
uv run python -m unittest tests.test_vector_map_airport_failure.AirportQueryFailureTests.test_successful_query_reuses_dem_and_preserves_patch_order -v
```

Expected: FAIL because `include_airports()` still constructs the DEM itself and returns a two-value combined-area tuple.

- [x] **Step 7: Implement the successful three-value contract**

Remove `DEM.DEM(...)` from `include_airports()`, retain `smooth_raster_over_airports()` before `include_patches()`, and return:

```python
return (apt_array, runway_taxiway_apron_area, patches_area)
```

Continue using `ops.unary_union([patches_area, runway_taxiway_apron_area])` only for the existing `flatten_helipads()` exclusion input.

- [x] **Step 8: Re-run both direct airport tests and verify GREEN**

Run:

```powershell
uv run python -m unittest tests.test_vector_map_airport_failure.AirportQueryFailureTests -v
```

Expected: both tests PASS.

- [x] **Step 9: Write the failing builder-order integration test**

Add this class to the test module:

```python
class VectorMapDemOrderingTests(unittest.TestCase):
    def test_builder_initializes_dem_before_airports_and_roads(self):
        order = []
        dem = object()
        vector_map = SimpleNamespace(dico_edges={})
        airport_mask = numpy.zeros((1001, 1001), dtype=bool)
        airport_area = geometry.Polygon()
        patch_area = geometry.box(0.1, 0.1, 0.2, 0.2)
        ctx = SimpleNamespace(is_working=False, red_flag=False)

        def construct_dem(*_args, **_kwargs):
            order.append("dem")
            return dem

        def include_airports(_vector_map, tile):
            self.assertIs(tile.dem, dem)
            order.append("airports")
            return (airport_mask, airport_area, patch_area)

        def include_roads(_vector_map, tile, received_mask, treated_area):
            self.assertIs(tile.dem, dem)
            self.assertIs(received_mask, airport_mask)
            self.assertTrue(
                treated_area.equals(ops.unary_union([patch_area, airport_area]))
            )
            order.append("roads")
            ctx.red_flag = True

        with TemporaryDirectory() as tmpdir:
            tile = SimpleNamespace(
                lat=12,
                lon=-123,
                build_dir=os.path.join(tmpdir, "build"),
                custom_dem="custom-dem.tif",
                fill_nodata=None,
                road_level=1,
            )
            osm_dir = os.path.join(tmpdir, "osm")
            with (
                mock.patch.object(VMAP.VECT, "Vector_Map", return_value=vector_map),
                mock.patch.object(
                    VMAP.DEM, "DEM", side_effect=construct_dem
                ) as dem_constructor,
                mock.patch.object(
                    VMAP, "include_airports", side_effect=include_airports
                ),
                mock.patch.object(VMAP, "include_roads", side_effect=include_roads),
                mock.patch.object(VMAP.FNAMES, "osm_dir", return_value=osm_dir),
                mock.patch.object(
                    VMAP.FNAMES,
                    "input_node_file",
                    return_value=os.path.join(tmpdir, "tile.node"),
                ),
                mock.patch.object(
                    VMAP.FNAMES,
                    "input_poly_file",
                    return_value=os.path.join(tmpdir, "tile.poly"),
                ),
                mock.patch.object(VMAP.UI, "logprint"),
                mock.patch.object(VMAP.UI, "vprint"),
                mock.patch.object(VMAP.UI, "exit_message_and_bottom_line"),
            ):
                result = VMAP.build_poly_file(tile, ctx=ctx)

        self.assertEqual(result, 0)
        self.assertEqual(order, ["dem", "airports", "roads"])
        dem_constructor.assert_called_once_with(
            12,
            -123,
            "custom-dem.tif",
            "to zero",
            info_only=False,
        )
```

- [x] **Step 10: Run the builder-order test and verify RED**

Run:

```powershell
uv run python -m unittest tests.test_vector_map_airport_failure.VectorMapDemOrderingTests.test_builder_initializes_dem_before_airports_and_roads -v
```

Expected: FAIL because the existing builder calls airports before DEM initialization and expects only two return values.

- [x] **Step 11: Move required DEM construction into the builder**

Immediately after `vector_map = VECT.Vector_Map()`, add:

```python
UI.vprint(1, "   Loading elevation data.")
tile.dem = DEM.DEM(
    tile.lat,
    tile.lon,
    tile.custom_dem,
    tile.fill_nodata or "to zero",
    info_only=False,
)
```

Replace the airport/road handoff with:

```python
apt_array, airport_area, patches_area = include_airports(vector_map, tile)
treated_area = ops.unary_union([patches_area, airport_area])
include_roads(vector_map, tile, apt_array, treated_area)
```

- [x] **Step 12: Run the focused module and verify GREEN**

Run:

```powershell
uv run python -m unittest tests.test_vector_map_airport_failure -v
```

Expected: all tests PASS with no warnings or errors.

- [x] **Step 13: Run changed-file checks**

Run:

```powershell
uv run ruff check src/O4_Vector_Map.py tests/test_vector_map_airport_failure.py
uv run ruff format --check src/O4_Vector_Map.py tests/test_vector_map_airport_failure.py
uv run ty check src/O4_Vector_Map.py tests/test_vector_map_airport_failure.py
```

Expected: all commands exit 0.

- [x] **Step 14: Commit the tested implementation**

```powershell
git add src/O4_Vector_Map.py tests/test_vector_map_airport_failure.py docs/superpowers/specs/2026-07-19-airport-query-dem-failure-handling-design.md
git commit -m "fix: continue vector build after airport query failure"
```

---

### Task 2: Verify the Repository and Close the Backlog Item

**Files:**
- Modify: `TODO.md:1171-1192`
- Modify: `docs/superpowers/plans/2026-07-19-airport-query-dem-failure-handling-plan.md`

**Interfaces:**
- Consumes: the verified behavior and test counts from Task 1.
- Produces: completed `TODO-041-1` evidence and a closed GitHub issue #38.

- [x] **Step 1: Run full repository verification**

Run:

```powershell
uv run python -m unittest discover -s tests
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected: the complete unit suite and every quality stage pass, including Ruff, formatting, ty, whitespace, complexity, and native LLVM/CMake verification.

- [x] **Step 2: Record observed evidence in `TODO.md`**

Change `TODO-041-1` to `Status: Done` and add a completion note naming the separated DEM ownership, typed empty airport values, preserved patches, and non-fatal continuation. Add a verification note containing only the observed commands, test count, and quality-gate result from Step 1.

- [x] **Step 3: Mark this plan complete and run documentation checks**

Check every plan box that was actually completed, then run:

```powershell
git diff --check
uv run ruff check src/O4_Vector_Map.py tests/test_vector_map_airport_failure.py
uv run ruff format --check src/O4_Vector_Map.py tests/test_vector_map_airport_failure.py
```

Expected: all commands exit 0.

- [x] **Step 4: Commit completion evidence**

```powershell
git add TODO.md docs/superpowers/plans/2026-07-19-airport-query-dem-failure-handling-plan.md
git commit -m "docs: complete airport failure backlog item"
```

- [ ] **Step 5: Update and close GitHub issue #38**

Post a comment summarizing the implementation, exact verification commands, observed test count, quality-gate result, and the two implementation/evidence commit SHAs. Then close issue #38 as completed.

- [ ] **Step 6: Confirm final repository and issue state**

Run:

```powershell
git status --short --branch
gh issue view 38 --repo tvproductions/Ortho4XP --json number,title,state,stateReason,url
gh issue list --repo tvproductions/Ortho4XP --state open --limit 100 --json number,title,url
```

Expected: clean workspace, issue #38 closed as completed, and remaining open issues #39 through #43 available for the final report.
