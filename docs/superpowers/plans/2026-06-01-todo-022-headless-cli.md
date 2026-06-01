# TODO-022 Headless CLI Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a headless `build_job.toml` CLI path that validates and runs multi-tile build plans without GUI/config side effects during validation.

**Architecture:** Create neutral build models in `src/O4_Build_Models.py`, parse TOML jobs in `src/O4_CLI_Jobs.py`, orchestrate commands in `src/O4_CLI_Run.py`, and dispatch `validate-job` / `build-job` early from `Ortho4XP.py` before GUI/config imports. Extend `O4_Build_Core` with `build_batch(plan, on_tile_complete=None)` and migrate GUI batch through a small adapter so CLI and GUI share the core batch API.

**Tech Stack:** Python 3.13+, stdlib `tomllib`, stdlib `argparse`, stdlib `unittest`, existing Ortho4XP modules only.

---

## File Structure

- Create `src/O4_Build_Models.py`
  - Owns `BuildTilePlan`, `BuildPlan`, `BuildTileResult`, `BuildBatchResult`, and step constants.
  - Has no imports from CLI, GUI, config, or tile utilities.
- Create `src/O4_CLI_Jobs.py`
  - Parses TOML and returns `BuildPlan`.
  - Owns validation errors and human/JSON validation summaries.
  - Resolves relative `output_dir` values relative to the job file directory.
- Create `src/O4_CLI_Run.py`
  - Owns headless `argparse` command handling, provider dictionary initialization, dry-run behavior, build invocation, and exit-code mapping.
- Modify `Ortho4XP.py`
  - Adds early dispatch for `validate-job` and `build-job` before `O4_GUI_Utils` / `O4_Config_Utils` imports.
  - Preserves legacy positional CLI and GUI behavior.
- Modify `src/O4_Build_Core.py`
  - Adds `build_batch(plan, on_tile_complete=None)`.
  - Keeps `build_tile_all(tile)` behavior compatible.
- Modify `src/O4_GUI_Utils.py`
  - Adds a GUI batch plan adapter and routes batch builds through core batch API.
- Modify `src/O4_Tile_Utils.py`
  - Converts `build_tile_list(...)` into a compatibility wrapper over the core batch API or leaves it delegating to the same adapter.
- Create `tests/fixtures/build_job_minimal.toml`
  - CI validation fixture.
- Create `tests/test_build_models.py`
  - Neutral model tests.
- Create `tests/test_cli_jobs.py`
  - TOML schema, bounds, provider, path-resolution, and JSON summary tests.
- Create `tests/test_cli_run.py`
  - Headless command tests with mocked provider/core behavior.
- Create `tests/test_headless_launcher.py`
  - Subprocess tests proving early dispatch avoids GUI/config imports and artifacts.
- Extend `tests/test_build_core.py`
  - Batch execution tests with mocked build steps.
- Create or extend `tests/test_gui_batch_adapter.py`
  - GUI-state-to-plan and callback cleanup tests without Tk windows.
- Modify `.github/workflows/ci.yml`
  - Adds `validate-job` smoke check on all platforms.
- Modify `README.md` and `docs/development.md`
  - Documents job file shape, commands, exit codes, dry-run behavior, and output directory semantics.
- Modify `TODO.md` only after implementation and verification pass.

---

### Task 1: Add Neutral Build Models

**Files:**
- Create: `src/O4_Build_Models.py`
- Create: `tests/test_build_models.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_build_models.py`:

```python
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Models as MODELS


class BuildModelsTests(unittest.TestCase):
    def test_build_tile_plan_stores_normalized_values(self):
        plan = MODELS.BuildTilePlan(
            lat=43,
            lon=-79,
            provider="BI",
            zoom_level=16,
            output_dir="D:/jobs/Tiles",
            custom_build_dir="D:/jobs/Tiles/",
            steps=("vector", "mesh", "masks", "tile"),
            override_tile_config=False,
        )

        self.assertEqual(plan.lat, 43)
        self.assertEqual(plan.lon, -79)
        self.assertEqual(plan.provider, "BI")
        self.assertEqual(plan.zoom_level, 16)
        self.assertEqual(plan.steps, ("vector", "mesh", "masks", "tile"))

    def test_build_plan_groups_tile_plans(self):
        tile = MODELS.BuildTilePlan(
            lat=0,
            lon=0,
            provider="BI",
            zoom_level=16,
            output_dir="Tiles",
            custom_build_dir="Tiles/",
            steps=MODELS.DEFAULT_STEPS,
            override_tile_config=False,
        )

        plan = MODELS.BuildPlan(tiles=(tile,))

        self.assertEqual(plan.tiles, (tile,))

    def test_batch_result_ok_requires_all_tile_results_ok(self):
        success = MODELS.BuildTileResult(0, 0, True, "all")
        failure = MODELS.BuildTileResult(0, 1, False, "mesh", "mesh failed")

        self.assertTrue(MODELS.batch_ok((success,)))
        self.assertFalse(MODELS.batch_ok((success, failure)))

    def test_step_constants_are_in_execution_order(self):
        self.assertEqual(
            MODELS.ALL_STEPS,
            ("vector", "mesh", "masks", "tile", "overlays"),
        )
        self.assertEqual(
            MODELS.DEFAULT_STEPS,
            ("vector", "mesh", "masks", "tile"),
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest tests.test_build_models -v
```

Expected: fails with `ModuleNotFoundError: No module named 'O4_Build_Models'`.

- [ ] **Step 3: Add `O4_Build_Models.py`**

Create `src/O4_Build_Models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


ALL_STEPS = ("vector", "mesh", "masks", "tile", "overlays")
DEFAULT_STEPS = ("vector", "mesh", "masks", "tile")


@dataclass(frozen=True)
class BuildTilePlan:
    lat: int
    lon: int
    provider: str
    zoom_level: int
    output_dir: str
    custom_build_dir: str
    steps: tuple[str, ...]
    override_tile_config: bool


@dataclass(frozen=True)
class BuildPlan:
    tiles: tuple[BuildTilePlan, ...]


@dataclass(frozen=True)
class BuildTileResult:
    lat: int
    lon: int
    ok: bool
    step: str
    message: str = ""


@dataclass(frozen=True)
class BuildBatchResult:
    ok: bool
    tiles: tuple[BuildTileResult, ...]
    message: str = ""


def batch_ok(results: tuple[BuildTileResult, ...]) -> bool:
    return all(result.ok for result in results)
```

- [ ] **Step 4: Run model tests**

Run:

```bash
uv run python -m unittest tests.test_build_models -v
```

Expected: all tests pass.

- [ ] **Step 5: Run lint/type checks**

Run:

```bash
uv run ruff check src/O4_Build_Models.py tests/test_build_models.py
uv run ty check src/O4_Build_Models.py tests/test_build_models.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/O4_Build_Models.py tests/test_build_models.py
git commit -m "feat: add neutral build plan models"
```

---

### Task 2: Add TOML Job Parser And Validator

**Files:**
- Create: `src/O4_CLI_Jobs.py`
- Create: `tests/test_cli_jobs.py`

- [ ] **Step 1: Write failing parser/validator tests**

Create `tests/test_cli_jobs.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Models as MODELS
import O4_CLI_Jobs as JOBS


PROVIDERS = {"BI", "Arc"}
COMBINED = {"EUR"}
PROVIDER_METADATA = {
    "BI": {"max_zl": 19},
    "Arc": {},
}


def _job_path(directory, text):
    path = Path(directory, "build_job.toml")
    path.write_text(text, encoding="utf-8")
    return path


class CliJobsValidationTests(unittest.TestCase):
    def test_explicit_tile_job_parses_to_build_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 43
lon = -79
""",
            )

            plan = JOBS.load_build_plan(
                path,
                provider_keys=PROVIDERS,
                combined_provider_keys=COMBINED,
                provider_metadata=PROVIDER_METADATA,
            )

        self.assertEqual(len(plan.tiles), 1)
        tile = plan.tiles[0]
        self.assertIsInstance(tile, MODELS.BuildTilePlan)
        self.assertEqual((tile.lat, tile.lon), (43, -79))
        self.assertEqual(tile.provider, "BI")
        self.assertEqual(tile.zoom_level, 16)
        self.assertEqual(tile.steps, MODELS.DEFAULT_STEPS)
        self.assertEqual(Path(tile.output_dir), Path(temp_dir, "Tiles"))
        self.assertTrue(tile.custom_build_dir.endswith(("/", "\\")))

    def test_bounds_expand_inclusive_ranges(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[bounds]
lat_min = 1
lat_max = 2
lon_min = -1
lon_max = 0
""",
            )

            plan = JOBS.load_build_plan(
                path,
                provider_keys=PROVIDERS,
                combined_provider_keys=COMBINED,
                provider_metadata=PROVIDER_METADATA,
            )

        self.assertEqual(
            [(tile.lat, tile.lon) for tile in plan.tiles],
            [(1, -1), (1, 0), (2, -1), (2, 0)],
        )

    def test_tiles_and_bounds_are_deduplicated_and_sorted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 2
lon = 0

[[tiles]]
lat = 1
lon = -1

[bounds]
lat_min = 1
lat_max = 1
lon_min = -1
lon_max = 0
""",
            )

            plan = JOBS.load_build_plan(
                path,
                provider_keys=PROVIDERS,
                combined_provider_keys=COMBINED,
                provider_metadata=PROVIDER_METADATA,
            )

        self.assertEqual(
            [(tile.lat, tile.lon) for tile in plan.tiles],
            [(1, -1), (1, 0), (2, 0)],
        )

    def test_combined_provider_key_is_valid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "EUR"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
            )

            plan = JOBS.load_build_plan(
                path,
                provider_keys=PROVIDERS,
                combined_provider_keys=COMBINED,
                provider_metadata=PROVIDER_METADATA,
            )

        self.assertEqual(plan.tiles[0].provider, "EUR")

    def test_rejects_reversed_bounds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[bounds]
lat_min = 2
lat_max = 1
lon_min = 0
lon_max = 0
""",
            )

            with self.assertRaises(JOBS.JobValidationError) as caught:
                JOBS.load_build_plan(
                    path,
                    provider_keys=PROVIDERS,
                    combined_provider_keys=COMBINED,
                    provider_metadata=PROVIDER_METADATA,
                )

        self.assertEqual(caught.exception.errors[0].field, "bounds.lat_min")

    def test_rejects_lat_lon_outside_tile_ranges(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 90
lon = 180
""",
            )

            with self.assertRaises(JOBS.JobValidationError) as caught:
                JOBS.load_build_plan(
                    path,
                    provider_keys=PROVIDERS,
                    combined_provider_keys=COMBINED,
                    provider_metadata=PROVIDER_METADATA,
                )

        self.assertEqual(
            [error.field for error in caught.exception.errors],
            ["tiles[0].lat", "tiles[0].lon"],
        )

    def test_rejects_unknown_step_and_per_tile_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"
steps = ["vector", "bogus"]

[[tiles]]
lat = 0
lon = 0
provider = "Arc"
""",
            )

            with self.assertRaises(JOBS.JobValidationError) as caught:
                JOBS.load_build_plan(
                    path,
                    provider_keys=PROVIDERS,
                    combined_provider_keys=COMBINED,
                    provider_metadata=PROVIDER_METADATA,
                )

        self.assertEqual(
            [error.field for error in caught.exception.errors],
            ["steps[1]", "tiles[0].provider"],
        )

    def test_rejects_zoom_above_provider_max_zl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _job_path(
                temp_dir,
                """
provider = "BI"
zoom_level = 20
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
            )

            with self.assertRaises(JOBS.JobValidationError) as caught:
                JOBS.load_build_plan(
                    path,
                    provider_keys=PROVIDERS,
                    combined_provider_keys=COMBINED,
                    provider_metadata=PROVIDER_METADATA,
                )

        self.assertEqual(caught.exception.errors[0].field, "zoom_level")

    def test_json_success_and_failure_payloads_are_stable(self):
        tile = MODELS.BuildTilePlan(
            lat=0,
            lon=0,
            provider="BI",
            zoom_level=16,
            output_dir="Tiles",
            custom_build_dir="Tiles/",
            steps=MODELS.DEFAULT_STEPS,
            override_tile_config=False,
        )
        success = json.loads(JOBS.validation_success_json(MODELS.BuildPlan((tile,))))

        self.assertEqual(success["ok"], True)
        self.assertEqual(success["tile_count"], 1)
        self.assertEqual(success["provider"], "BI")
        self.assertEqual(success["tiles"], [{"lat": 0, "lon": 0}])

        failure = json.loads(
            JOBS.validation_failure_json(
                [JOBS.ValidationError("provider", "unknown provider", "NOPE")]
            )
        )
        self.assertEqual(
            failure,
            {
                "ok": False,
                "errors": [
                    {
                        "field": "provider",
                        "message": "unknown provider",
                        "value": "NOPE",
                    }
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest tests.test_cli_jobs -v
```

Expected: fails with `ModuleNotFoundError: No module named 'O4_CLI_Jobs'`.

- [ ] **Step 3: Add `O4_CLI_Jobs.py` implementation**

Create `src/O4_CLI_Jobs.py`:

```python
from __future__ import annotations

import json
import os
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import O4_Build_Models as MODELS


MIN_LAT = -90
MAX_LAT = 89
MIN_LON = -180
MAX_LON = 179
_MISSING = object()


@dataclass(frozen=True)
class TileCoordinate:
    lat: int
    lon: int


@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str
    value: object | None = None


class JobValidationError(ValueError):
    def __init__(self, errors: list[ValidationError]):
        super().__init__("build job validation failed")
        self.errors = tuple(errors)


def load_build_plan(
    path: str | os.PathLike[str],
    *,
    provider_keys: set[str],
    combined_provider_keys: set[str],
    provider_metadata: dict[str, dict[str, Any]] | None = None,
) -> MODELS.BuildPlan:
    job_path = Path(path)
    try:
        raw = tomllib.loads(job_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise JobValidationError(
            [ValidationError("build_job", f"TOML parse error: {exc}", None)]
        ) from exc
    except OSError as exc:
        raise JobValidationError(
            [ValidationError("build_job", f"could not read file: {exc}", str(job_path))]
        ) from exc
    return build_plan_from_mapping(
        raw,
        job_dir=job_path.resolve().parent,
        provider_keys=provider_keys,
        combined_provider_keys=combined_provider_keys,
        provider_metadata=provider_metadata or {},
    )


def build_plan_from_mapping(
    raw: dict[str, Any],
    *,
    job_dir: Path,
    provider_keys: set[str],
    combined_provider_keys: set[str],
    provider_metadata: dict[str, dict[str, Any]],
) -> MODELS.BuildPlan:
    errors: list[ValidationError] = []
    provider = _string_field(raw, "provider", errors)
    zoom_level = _int_field(raw, "zoom_level", errors)
    output_dir = _string_field(raw, "output_dir", errors)
    steps = _steps(raw.get("steps", MODELS.DEFAULT_STEPS), errors)
    override_tile_config = _bool_field(
        raw, "override_tile_config", errors, default=False
    )
    _reject_unknown_top_level_keys(raw, errors)

    if provider is not None:
        _validate_provider(
            provider,
            provider_keys=provider_keys,
            combined_provider_keys=combined_provider_keys,
            errors=errors,
        )
    if provider is not None and zoom_level is not None:
        _validate_zoom_level(provider, zoom_level, provider_metadata, errors)

    coordinates = _coordinates(raw, errors)
    if not coordinates:
        errors.append(
            ValidationError("tiles", "at least one tile or bounds block is required")
        )

    if errors:
        raise JobValidationError(errors)

    resolved_output_dir = _resolve_output_dir(str(output_dir), job_dir)
    custom_build_dir = _as_base_custom_build_dir(resolved_output_dir)
    tile_plans = tuple(
        MODELS.BuildTilePlan(
            lat=coord.lat,
            lon=coord.lon,
            provider=str(provider),
            zoom_level=int(zoom_level),
            output_dir=resolved_output_dir,
            custom_build_dir=custom_build_dir,
            steps=steps,
            override_tile_config=bool(override_tile_config),
        )
        for coord in coordinates
    )
    return MODELS.BuildPlan(tile_plans)


def validation_success_json(plan: MODELS.BuildPlan) -> str:
    first = plan.tiles[0] if plan.tiles else None
    payload = {
        "ok": True,
        "tile_count": len(plan.tiles),
        "provider": first.provider if first else None,
        "zoom_level": first.zoom_level if first else None,
        "output_dir": first.output_dir if first else None,
        "steps": list(first.steps) if first else [],
        "tiles": [{"lat": tile.lat, "lon": tile.lon} for tile in plan.tiles],
    }
    return json.dumps(payload, sort_keys=True)


def validation_failure_json(errors: list[ValidationError] | tuple[ValidationError, ...]) -> str:
    payload = {
        "ok": False,
        "errors": [asdict(error) for error in errors],
    }
    return json.dumps(payload, sort_keys=True)


def human_validation_summary(plan: MODELS.BuildPlan) -> str:
    if not plan.tiles:
        return "Build job valid: 0 tiles"
    first = plan.tiles[0]
    preview = ", ".join(f"{tile.lat:+03d}{tile.lon:+04d}" for tile in plan.tiles[:5])
    remaining = len(plan.tiles) - 5
    suffix = "" if remaining <= 0 else f", ... {remaining} more"
    return (
        f"Build job valid: {len(plan.tiles)} tile(s); "
        f"provider={first.provider}; zoom_level={first.zoom_level}; "
        f"output_dir={first.output_dir}; steps={','.join(first.steps)}; "
        f"tiles={preview}{suffix}"
    )


def human_validation_errors(errors: tuple[ValidationError, ...]) -> str:
    lines = ["Build job validation failed:"]
    for error in errors:
        if error.value is None:
            lines.append(f"- {error.field}: {error.message}")
        else:
            lines.append(f"- {error.field}: {error.message} ({error.value!r})")
    return "\n".join(lines)


def _string_field(
    raw: dict[str, Any], field: str, errors: list[ValidationError]
) -> str | None:
    value = raw.get(field, _MISSING)
    if value is _MISSING:
        errors.append(ValidationError(field, "is required"))
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(ValidationError(field, "must be a non-empty string", value))
        return None
    return value


def _int_field(
    raw: dict[str, Any], field: str, errors: list[ValidationError]
) -> int | None:
    value = raw.get(field, _MISSING)
    if value is _MISSING:
        errors.append(ValidationError(field, "is required"))
        return None
    if not isinstance(value, int):
        errors.append(ValidationError(field, "must be an integer", value))
        return None
    return value


def _bool_field(
    raw: dict[str, Any],
    field: str,
    errors: list[ValidationError],
    *,
    default: bool,
) -> bool | None:
    value = raw.get(field, default)
    if not isinstance(value, bool):
        errors.append(ValidationError(field, "must be a boolean", value))
        return None
    return value


def _steps(value: object, errors: list[ValidationError]) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        errors.append(ValidationError("steps", "must be a list", value))
        return MODELS.DEFAULT_STEPS
    steps: list[str] = []
    for index, step in enumerate(value):
        if not isinstance(step, str) or step not in MODELS.ALL_STEPS:
            errors.append(
                ValidationError(
                    f"steps[{index}]",
                    f"must be one of {MODELS.ALL_STEPS}",
                    step,
                )
            )
            continue
        steps.append(step)
    return tuple(steps)


def _reject_unknown_top_level_keys(
    raw: dict[str, Any], errors: list[ValidationError]
) -> None:
    allowed = {
        "provider",
        "zoom_level",
        "output_dir",
        "steps",
        "override_tile_config",
        "tiles",
        "bounds",
    }
    for key in sorted(set(raw) - allowed):
        errors.append(ValidationError(key, "unknown field", raw[key]))


def _validate_provider(
    provider: str,
    *,
    provider_keys: set[str],
    combined_provider_keys: set[str],
    errors: list[ValidationError],
) -> None:
    if provider not in provider_keys and provider not in combined_provider_keys:
        errors.append(ValidationError("provider", "unknown provider", provider))


def _validate_zoom_level(
    provider: str,
    zoom_level: int,
    provider_metadata: dict[str, dict[str, Any]],
    errors: list[ValidationError],
) -> None:
    if zoom_level <= 0:
        errors.append(ValidationError("zoom_level", "must be greater than zero", zoom_level))
        return
    max_zl = provider_metadata.get(provider, {}).get("max_zl")
    if max_zl is not None and zoom_level > int(max_zl):
        errors.append(
            ValidationError(
                "zoom_level",
                f"must be less than or equal to provider max_zl {max_zl}",
                zoom_level,
            )
        )


def _coordinates(raw: dict[str, Any], errors: list[ValidationError]) -> tuple[TileCoordinate, ...]:
    coordinates: set[TileCoordinate] = set()
    coordinates.update(_explicit_tiles(raw.get("tiles", []), errors))
    bounds = raw.get("bounds")
    if bounds is not None:
        coordinates.update(_bounds_tiles(bounds, errors))
    return tuple(sorted(coordinates, key=lambda coord: (coord.lat, coord.lon)))


def _explicit_tiles(value: object, errors: list[ValidationError]) -> list[TileCoordinate]:
    if value in (None, []):
        return []
    if not isinstance(value, list):
        errors.append(ValidationError("tiles", "must be a list of tables", value))
        return []
    coordinates: list[TileCoordinate] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(ValidationError(f"tiles[{index}]", "must be a table", item))
            continue
        for key in sorted(set(item) - {"lat", "lon"}):
            errors.append(
                ValidationError(f"tiles[{index}].{key}", "per-tile override is not supported", item[key])
            )
        lat = _coordinate_field(item, f"tiles[{index}].lat", "lat", errors)
        lon = _coordinate_field(item, f"tiles[{index}].lon", "lon", errors)
        if lat is not None and lon is not None:
            coordinates.append(TileCoordinate(lat, lon))
    return coordinates


def _bounds_tiles(value: object, errors: list[ValidationError]) -> list[TileCoordinate]:
    if not isinstance(value, dict):
        errors.append(ValidationError("bounds", "must be a table", value))
        return []
    lat_min = _coordinate_field(value, "bounds.lat_min", "lat_min", errors)
    lat_max = _coordinate_field(value, "bounds.lat_max", "lat_max", errors)
    lon_min = _coordinate_field(value, "bounds.lon_min", "lon_min", errors)
    lon_max = _coordinate_field(value, "bounds.lon_max", "lon_max", errors)
    for key in sorted(set(value) - {"lat_min", "lat_max", "lon_min", "lon_max"}):
        errors.append(ValidationError(f"bounds.{key}", "unknown field", value[key]))
    if None in (lat_min, lat_max, lon_min, lon_max):
        return []
    if lat_min > lat_max:
        errors.append(
            ValidationError(
                "bounds.lat_min",
                "must be less than or equal to bounds.lat_max",
                lat_min,
            )
        )
        return []
    if lon_min > lon_max:
        errors.append(
            ValidationError(
                "bounds.lon_min",
                "must be less than or equal to bounds.lon_max",
                lon_min,
            )
        )
        return []
    return [
        TileCoordinate(lat, lon)
        for lat in range(lat_min, lat_max + 1)
        for lon in range(lon_min, lon_max + 1)
    ]


def _coordinate_field(
    raw: dict[str, Any],
    field: str,
    key: str,
    errors: list[ValidationError],
) -> int | None:
    value = raw.get(key, _MISSING)
    if value is _MISSING:
        errors.append(ValidationError(field, "is required"))
        return None
    if not isinstance(value, int):
        errors.append(ValidationError(field, "must be an integer", value))
        return None
    if key.startswith("lat") or field.endswith(".lat"):
        if value < MIN_LAT or value > MAX_LAT:
            errors.append(
                ValidationError(field, f"must be between {MIN_LAT} and {MAX_LAT}", value)
            )
            return None
    if key.startswith("lon") or field.endswith(".lon"):
        if value < MIN_LON or value > MAX_LON:
            errors.append(
                ValidationError(field, f"must be between {MIN_LON} and {MAX_LON}", value)
            )
            return None
    return value


def _resolve_output_dir(output_dir: str, job_dir: Path) -> str:
    path = Path(output_dir)
    if not path.is_absolute():
        path = job_dir / path
    return str(path)


def _as_base_custom_build_dir(output_dir: str) -> str:
    if output_dir.endswith(("/", "\\")):
        return output_dir
    return output_dir + os.sep
```

- [ ] **Step 4: Run parser/validator tests**

Run:

```bash
uv run python -m unittest tests.test_cli_jobs -v
```

Expected: all tests pass.

- [ ] **Step 5: Run lint/type checks**

Run:

```bash
uv run ruff check src/O4_CLI_Jobs.py tests/test_cli_jobs.py
uv run ty check src/O4_CLI_Jobs.py tests/test_cli_jobs.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/O4_CLI_Jobs.py tests/test_cli_jobs.py
git commit -m "feat: parse and validate build job TOML"
```

---

### Task 3: Add Headless CLI Runner And Early Launcher Dispatch

**Files:**
- Create: `src/O4_CLI_Run.py`
- Create: `tests/test_cli_run.py`
- Create: `tests/test_headless_launcher.py`
- Modify: `Ortho4XP.py`

- [ ] **Step 1: Write CLI runner unit tests**

Create `tests/test_cli_run.py`:

```python
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Models as MODELS
import O4_CLI_Run as RUN


class CliRunTests(unittest.TestCase):
    def _job_file(self, temp_dir):
        path = Path(temp_dir, "build_job.toml")
        path.write_text(
            """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
            encoding="utf-8",
        )
        return path

    def _plan(self):
        tile = MODELS.BuildTilePlan(
            lat=0,
            lon=0,
            provider="BI",
            zoom_level=16,
            output_dir="Tiles",
            custom_build_dir="Tiles/",
            steps=MODELS.DEFAULT_STEPS,
            override_tile_config=False,
        )
        return MODELS.BuildPlan((tile,))

    def test_validate_job_prints_human_summary_and_returns_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(RUN, "_provider_inventory", return_value=({"BI"}, set(), {"BI": {}})),
                mock.patch.object(RUN.JOBS, "load_build_plan", return_value=self._plan()),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["validate-job", str(job_file)])

        self.assertEqual(code, 0)
        self.assertIn("Build job valid: 1 tile", stdout.getvalue())

    def test_validate_job_json_prints_json_and_returns_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(RUN, "_provider_inventory", return_value=({"BI"}, set(), {"BI": {}})),
                mock.patch.object(RUN.JOBS, "load_build_plan", return_value=self._plan()),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["validate-job", str(job_file), "--json"])

        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])

    def test_validation_error_returns_two(self):
        error = RUN.JOBS.ValidationError("provider", "unknown provider", "NOPE")
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(RUN, "_provider_inventory", return_value=(set(), set(), {})),
                mock.patch.object(
                    RUN.JOBS,
                    "load_build_plan",
                    side_effect=RUN.JOBS.JobValidationError([error]),
                ),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["validate-job", str(job_file)])

        self.assertEqual(code, 2)
        self.assertIn("provider", stdout.getvalue())

    def test_build_job_dry_run_does_not_import_runtime_modules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(RUN, "_provider_inventory", return_value=({"BI"}, set(), {"BI": {}})),
                mock.patch.object(RUN.JOBS, "load_build_plan", return_value=self._plan()),
                mock.patch.object(RUN, "_run_build", side_effect=AssertionError("should not build")),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["build-job", str(job_file), "--dry-run"])

        self.assertEqual(code, 0)
        self.assertIn("Build job valid: 1 tile", stdout.getvalue())

    def test_build_job_maps_failed_batch_to_exit_one(self):
        failed = MODELS.BuildBatchResult(
            ok=False,
            tiles=(MODELS.BuildTileResult(0, 0, False, "mesh", "mesh failed"),),
            message="mesh failed",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(RUN, "_provider_inventory", return_value=({"BI"}, set(), {"BI": {}})),
                mock.patch.object(RUN.JOBS, "load_build_plan", return_value=self._plan()),
                mock.patch.object(RUN, "_run_build", return_value=failed),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["build-job", str(job_file)])

        self.assertEqual(code, 1)
        self.assertIn("mesh failed", stdout.getvalue())

    def test_build_job_maps_success_to_exit_zero(self):
        result = MODELS.BuildBatchResult(
            ok=True,
            tiles=(MODELS.BuildTileResult(0, 0, True, "all"),),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = self._job_file(temp_dir)
            stdout = io.StringIO()
            with (
                mock.patch.object(RUN, "_provider_inventory", return_value=({"BI"}, set(), {"BI": {}})),
                mock.patch.object(RUN.JOBS, "load_build_plan", return_value=self._plan()),
                mock.patch.object(RUN, "_run_build", return_value=result),
                contextlib.redirect_stdout(stdout),
            ):
                code = RUN.main(["build-job", str(job_file)])

        self.assertEqual(code, 0)
        self.assertIn("Build job completed: 1 tile", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Write headless launcher subprocess tests**

Create `tests/test_headless_launcher.py`:

```python
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class HeadlessLauncherTests(unittest.TestCase):
    def test_validate_job_from_non_repo_cwd_does_not_create_generated_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            job_file = temp_path / "build_job.toml"
            job_file.write_text(
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(_path.ROOT_DIR / "Ortho4XP.py"),
                    "validate-job",
                    str(job_file),
                ],
                cwd=temp_dir,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Build job valid", result.stdout)
            for generated in (
                "Ortho4XP.cfg",
                "Tiles",
                "OSM_data",
                "Masks",
                "Orthophotos",
                "Elevation_data",
                "Geotiffs",
                "tmp",
                "yOrtho4XP_Overlays",
            ):
                self.assertFalse((temp_path / generated).exists(), generated)

    def test_validate_job_json_failure_returns_two(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job_file = Path(temp_dir) / "build_job.toml"
            job_file.write_text(
                """
provider = "NOPE"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(_path.ROOT_DIR / "Ortho4XP.py"),
                    "validate-job",
                    str(job_file),
                    "--json",
                ],
                cwd=temp_dir,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn('"ok": false', result.stdout.lower())
            self.assertIn("provider", result.stdout)

    def test_build_job_dry_run_from_non_repo_cwd_creates_no_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            job_file = temp_path / "build_job.toml"
            job_file.write_text(
                """
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
""",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(_path.ROOT_DIR / "Ortho4XP.py"),
                    "build-job",
                    str(job_file),
                    "--dry-run",
                ],
                cwd=temp_dir,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((temp_path / "Tiles").exists())
            self.assertFalse((temp_path / "Ortho4XP.cfg").exists())

    def test_legacy_help_mentions_headless_commands(self):
        result = subprocess.run(
            [sys.executable, str(_path.ROOT_DIR / "Ortho4XP.py"), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("validate-job", result.stdout)
        self.assertIn("build-job", result.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify failures**

Run:

```bash
uv run python -m unittest tests.test_cli_run tests.test_headless_launcher -v
```

Expected:
- `tests.test_cli_run` fails with `ModuleNotFoundError: No module named 'O4_CLI_Run'`.
- `tests.test_headless_launcher` fails because `Ortho4XP.py` does not support `validate-job`.

- [ ] **Step 4: Add `O4_CLI_Run.py`**

Create `src/O4_CLI_Run.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

import O4_Build_Models as MODELS
import O4_CLI_Jobs as JOBS


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        provider_keys, combined_provider_keys, provider_metadata = _provider_inventory()
        plan = JOBS.load_build_plan(
            args.job_file,
            provider_keys=provider_keys,
            combined_provider_keys=combined_provider_keys,
            provider_metadata=provider_metadata,
        )
    except JOBS.JobValidationError as exc:
        _print_validation_failure(exc.errors, json_output=args.json)
        return 2

    if args.command == "validate-job" or args.dry_run:
        _print_validation_success(plan, json_output=args.json)
        return 0

    try:
        result = _run_build(plan)
    except Exception as exc:
        _log_build_exception(exc)
        print(f"Build job failed: {exc}")
        return 1
    _print_build_result(result)
    return 0 if result.ok else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="Ortho4XP.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-job")
    validate.add_argument("job_file")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(dry_run=True)

    build = subparsers.add_parser("build-job")
    build.add_argument("job_file")
    build.add_argument("--dry-run", action="store_true")
    build.add_argument("--json", action="store_true")

    return parser


def _provider_inventory() -> tuple[set[str], set[str], dict[str, dict]]:
    import O4_Imagery_Utils as IMG

    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()
    return (
        set(IMG.providers_dict),
        set(IMG.combined_providers_dict),
        IMG.providers_dict,
    )


def _run_build(plan: MODELS.BuildPlan) -> MODELS.BuildBatchResult:
    import Ortho4XP
    import O4_Build_Core as CORE

    if not Ortho4XP.ensure_runtime_dirs():
        return MODELS.BuildBatchResult(False, (), "runtime directory setup failed")
    return CORE.build_batch(plan)


def _log_build_exception(exc: Exception) -> None:
    import O4_UI_Utils as UI

    UI.log_exception(exc)


def _print_validation_success(plan: MODELS.BuildPlan, *, json_output: bool) -> None:
    if json_output:
        print(JOBS.validation_success_json(plan))
    else:
        print(JOBS.human_validation_summary(plan))


def _print_validation_failure(
    errors: tuple[JOBS.ValidationError, ...], *, json_output: bool
) -> None:
    if json_output:
        print(JOBS.validation_failure_json(errors))
    else:
        print(JOBS.human_validation_errors(errors))


def _print_build_result(result: MODELS.BuildBatchResult) -> None:
    if result.ok:
        print(f"Build job completed: {len(result.tiles)} tile(s)")
        return
    failed = next((tile for tile in result.tiles if not tile.ok), None)
    if failed:
        print(
            f"Build job failed at {failed.lat:+03d}{failed.lon:+04d} "
            f"step={failed.step}: {failed.message}"
        )
    elif result.message:
        print(f"Build job failed: {result.message}")
    else:
        print("Build job failed")
```

- [ ] **Step 5: Refactor `Ortho4XP.py` for early dispatch**

In `Ortho4XP.py`, replace the current top section through imports with this structure. Keep existing runtime imports below `_legacy_main()` so headless commands return before GUI/config imports:

```python
#!/usr/bin/env python3
import os
import sys

Ortho4XP_dir = ".." if getattr(sys, "frozen", False) else "."
cmd_line = (
    "USAGE: Ortho4XP.py lat lon imagery zl (won't read a tile config)\n"
    "  OR:  Ortho4XP.py lat lon (with existing tile config file)\n"
    "  OR:  Ortho4XP.py validate-job build_job.toml [--json]\n"
    "  OR:  Ortho4XP.py build-job build_job.toml [--dry-run] [--json]"
)


def _source_root() -> str:
    if getattr(sys, "frozen", False):
        return Ortho4XP_dir
    return os.path.dirname(os.path.abspath(__file__))


def _ensure_src_path() -> None:
    src_path = os.path.join(_source_root(), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def _is_headless_command(argv: list[str]) -> bool:
    return len(argv) > 1 and argv[1] in {"validate-job", "build-job"}


def _dispatch_headless(argv: list[str]) -> int:
    cli_argv = list(argv[1:])
    if len(cli_argv) >= 2:
        cli_argv[1] = os.path.abspath(cli_argv[1])
    os.chdir(_source_root())
    _ensure_src_path()
    import O4_CLI_Run as CLI_RUN

    return CLI_RUN.main(cli_argv)


if __name__ == "__main__" and len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
    print(cmd_line)
    sys.exit(0)


if __name__ == "__main__" and _is_headless_command(sys.argv):
    sys.exit(_dispatch_headless(sys.argv))


if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _proj_data_path = os.path.join(sys._MEIPASS, "pyproj", "proj_dir", "share", "proj")
    _lib_path = os.path.join(sys._MEIPASS, "_internal")
    os.environ["PROJ_DATA"] = _proj_data_path
    os.environ["DYLD_LIBRARY_PATH"] = (
        _lib_path + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")
    )

from pyproj import datadir

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    datadir.set_data_dir(_proj_data_path)

_ensure_src_path()
```

Leave the existing imports from `O4_File_Names` onward after `_ensure_src_path()`:

```python
import O4_File_Names as FNAMES

sys.path.append(FNAMES.Provider_dir)
```

Keep the existing `ensure_runtime_dirs()` function and the legacy `if __name__ == "__main__":` body below unchanged except the help text is now updated.

- [ ] **Step 6: Run CLI runner and launcher tests**

Run:

```bash
uv run python -m unittest tests.test_cli_run tests.test_headless_launcher -v
```

Expected: all tests pass.

- [ ] **Step 7: Run startup and launcher regression tests**

Run:

```bash
uv run python -m unittest tests.test_startup tests.test_launcher_core tests.test_cli_utils -v
```

Expected: all tests pass.

- [ ] **Step 8: Run lint/type checks**

Run:

```bash
uv run ruff check Ortho4XP.py src/O4_CLI_Run.py tests/test_cli_run.py tests/test_headless_launcher.py
uv run ty check Ortho4XP.py src/O4_CLI_Run.py tests/test_cli_run.py tests/test_headless_launcher.py
```

Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add Ortho4XP.py src/O4_CLI_Run.py tests/test_cli_run.py tests/test_headless_launcher.py
git commit -m "feat: add headless build job CLI dispatch"
```

---

### Task 4: Add Core Batch API

**Files:**
- Modify: `src/O4_Build_Core.py`
- Modify: `tests/test_build_core.py`

- [ ] **Step 1: Add failing batch tests**

Append these tests to `tests/test_build_core.py` before the `if __name__ == "__main__":` block:

```python
def _tile_plan(
    lat=12,
    lon=-123,
    *,
    steps=("vector", "mesh", "masks", "tile"),
    override_tile_config=False,
):
    import O4_Build_Models as MODELS

    return MODELS.BuildTilePlan(
        lat=lat,
        lon=lon,
        provider="BI",
        zoom_level=16,
        output_dir="Tiles",
        custom_build_dir="Tiles/",
        steps=steps,
        override_tile_config=override_tile_config,
    )


class BuildCoreBatchTests(unittest.TestCase):
    def test_build_batch_runs_selected_steps_in_order(self):
        import O4_Build_Models as MODELS

        calls = []

        def record(name):
            def _inner(tile, ctx=None):
                calls.append((name, tile.lat, tile.lon))
                return 1

            return _inner

        with (
            mock.patch.object(CORE.CFG, "Tile") as tile_class,
            mock.patch.object(CORE.VMAP, "build_poly_file", side_effect=record("vector")),
            mock.patch.object(CORE.MESH, "build_mesh", side_effect=record("mesh")),
            mock.patch.object(CORE.MASK, "build_masks", side_effect=record("masks")),
            mock.patch.object(CORE.TILE, "build_tile", side_effect=record("tile")),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
        ):
            tile_class.side_effect = lambda lat, lon, custom: SimpleNamespace(
                lat=lat,
                lon=lon,
                custom_build_dir=custom,
                build_dir=f"build-{lat}-{lon}",
                dem=None,
                default_website="",
                default_zl=0,
                make_dirs=mock.Mock(),
                read_from_config=mock.Mock(return_value=1),
            )
            result = CORE.build_batch(MODELS.BuildPlan((_tile_plan(),)))

        self.assertTrue(result.ok)
        self.assertEqual(
            calls,
            [
                ("vector", 12, -123),
                ("mesh", 12, -123),
                ("masks", 12, -123),
                ("tile", 12, -123),
            ],
        )

    def test_build_batch_calls_overlays_step(self):
        import O4_Build_Models as MODELS

        with (
            mock.patch.object(CORE.CFG, "Tile") as tile_class,
            mock.patch.object(CORE.OVL, "build_overlay", return_value=1) as overlay,
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
        ):
            tile_class.side_effect = lambda lat, lon, custom: SimpleNamespace(
                lat=lat,
                lon=lon,
                custom_build_dir=custom,
                build_dir=f"build-{lat}-{lon}",
                dem=None,
                default_website="",
                default_zl=0,
                make_dirs=mock.Mock(),
                read_from_config=mock.Mock(return_value=1),
            )
            result = CORE.build_batch(
                MODELS.BuildPlan((_tile_plan(steps=("overlays",)),))
            )

        self.assertTrue(result.ok)
        overlay.assert_called_once_with(12, -123)

    def test_build_batch_maps_falsey_step_return_to_failure(self):
        import O4_Build_Models as MODELS

        with (
            mock.patch.object(CORE.CFG, "Tile") as tile_class,
            mock.patch.object(CORE.MESH, "build_mesh", return_value=0),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
        ):
            tile_class.side_effect = lambda lat, lon, custom: SimpleNamespace(
                lat=lat,
                lon=lon,
                custom_build_dir=custom,
                build_dir=f"build-{lat}-{lon}",
                dem=None,
                default_website="",
                default_zl=0,
                make_dirs=mock.Mock(),
                read_from_config=mock.Mock(return_value=1),
            )
            result = CORE.build_batch(MODELS.BuildPlan((_tile_plan(steps=("mesh",)),)))

        self.assertFalse(result.ok)
        self.assertEqual(result.tiles[0].step, "mesh")
        self.assertEqual(result.tiles[0].message, "mesh failed")

    def test_build_batch_uses_override_config_flag(self):
        import O4_Build_Models as MODELS

        tile = SimpleNamespace(
            lat=0,
            lon=0,
            custom_build_dir="Tiles/",
            build_dir="build",
            dem=None,
            default_website="",
            default_zl=0,
            make_dirs=mock.Mock(),
            read_from_config=mock.Mock(return_value=1),
        )
        with (
            mock.patch.object(CORE.CFG, "Tile", return_value=tile),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
        ):
            CORE.build_batch(
                MODELS.BuildPlan(
                    (
                        _tile_plan(
                            lat=0,
                            lon=0,
                            steps=("vector",),
                            override_tile_config=True,
                        ),
                    )
                )
            )

        tile.read_from_config.assert_called_once_with(use_global=True)

    def test_build_batch_invokes_completion_callback(self):
        import O4_Build_Models as MODELS

        completed = []
        with (
            mock.patch.object(CORE.CFG, "Tile") as tile_class,
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.UI, "lvprint"),
        ):
            tile_class.side_effect = lambda lat, lon, custom: SimpleNamespace(
                lat=lat,
                lon=lon,
                custom_build_dir=custom,
                build_dir=f"build-{lat}-{lon}",
                dem=None,
                default_website="",
                default_zl=0,
                make_dirs=mock.Mock(),
                read_from_config=mock.Mock(return_value=1),
            )
            result = CORE.build_batch(
                MODELS.BuildPlan((_tile_plan(steps=("vector",)),)),
                on_tile_complete=completed.append,
            )

        self.assertTrue(result.ok)
        self.assertEqual(completed, result.tiles)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest tests.test_build_core -v
```

Expected: failures because `O4_Build_Core` has no `build_batch`, no `CFG` import, and no `OVL` import.

- [ ] **Step 3: Update `O4_Build_Core.py` imports**

Add these imports near existing imports in `src/O4_Build_Core.py`:

```python
from collections.abc import Callable

import O4_Build_Models as MODELS
import O4_Config_Utils as CFG
import O4_Overlay_Utils as OVL
```

Add this type alias after `BuildResult`:

```python
TileCompleteCallback = Callable[[MODELS.BuildTileResult], None]
```

- [ ] **Step 4: Add batch helpers to `O4_Build_Core.py`**

Append these functions after `_report_remaining_incomplete_textures()`:

```python
def build_batch(
    plan: MODELS.BuildPlan,
    *,
    on_tile_complete: TileCompleteCallback | None = None,
) -> MODELS.BuildBatchResult:
    """Run a validated multi-tile build plan and return aggregate results."""
    ctx = BC.BuildContext()
    if ctx.is_working:
        return MODELS.BuildBatchResult(False, (), "build already in progress")
    results: list[MODELS.BuildTileResult] = []
    for tile_plan in plan.tiles:
        result = _build_tile_plan(tile_plan, ctx)
        results.append(result)
        if on_tile_complete is not None:
            on_tile_complete(result)
        if not result.ok:
            return MODELS.BuildBatchResult(False, tuple(results), result.message)
    _report_remaining_incomplete_textures()
    return MODELS.BuildBatchResult(MODELS.batch_ok(tuple(results)), tuple(results))


def _build_tile_plan(
    tile_plan: MODELS.BuildTilePlan, ctx: BC.BuildContext
) -> MODELS.BuildTileResult:
    tile = CFG.Tile(tile_plan.lat, tile_plan.lon, tile_plan.custom_build_dir)
    tile.default_website = tile_plan.provider
    tile.default_zl = tile_plan.zoom_level
    tile.custom_build_dir = tile_plan.custom_build_dir
    tile.dem = None
    if tile_plan.override_tile_config:
        tile.read_from_config(use_global=True)
    else:
        tile.read_from_config()
    if _steps_need_tile_directory(tile_plan.steps):
        tile.make_dirs()
    for step in MODELS.ALL_STEPS:
        if step not in tile_plan.steps:
            continue
        ok = _run_batch_step(step, tile, ctx)
        if ctx.red_flag:
            UI.exit_message_and_bottom_line("")
            return MODELS.BuildTileResult(
                tile_plan.lat,
                tile_plan.lon,
                False,
                step,
                "interrupted",
            )
        if not ok:
            return MODELS.BuildTileResult(
                tile_plan.lat,
                tile_plan.lon,
                False,
                step,
                f"{step} failed",
            )
    return MODELS.BuildTileResult(tile_plan.lat, tile_plan.lon, True, "all")


def _steps_need_tile_directory(steps: tuple[str, ...]) -> bool:
    return bool({"vector", "mesh", "tile"}.intersection(steps))


def _run_batch_step(step: str, tile, ctx: BC.BuildContext) -> int:
    if step == "vector":
        return VMAP.build_poly_file(tile, ctx=ctx)
    if step == "mesh":
        return MESH.build_mesh(tile, ctx=ctx)
    if step == "masks":
        return MASK.build_masks(tile, ctx=ctx)
    if step == "tile":
        return _run_batch_tile_step(tile, ctx)
    if step == "overlays":
        return OVL.build_overlay(tile.lat, tile.lon)
    raise ValueError(f"unknown build step: {step}")


def _run_batch_tile_step(tile, ctx: BC.BuildContext) -> int:
    result = TILE.build_tile(tile, ctx=ctx)
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    if tile_coords in IMG.incomplete_imgs:
        _retry_incomplete_textures(tile, ctx, tile_coords)
    if ctx.red_flag:
        return 0
    return result
```

- [ ] **Step 5: Run focused build core tests**

Run:

```bash
uv run python -m unittest tests.test_build_core tests.test_build_core_interrupts tests.test_build_core_wrapper -v
```

Expected: all tests pass.

- [ ] **Step 6: Run lint/type checks**

Run:

```bash
uv run ruff check src/O4_Build_Core.py tests/test_build_core.py
uv run ty check src/O4_Build_Core.py tests/test_build_core.py
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add src/O4_Build_Core.py tests/test_build_core.py
git commit -m "feat: add core batch build API"
```

---

### Task 5: Route GUI Batch Through Core Batch API

**Files:**
- Modify: `src/O4_GUI_Utils.py`
- Modify: `src/O4_Tile_Utils.py`
- Create: `tests/test_gui_batch_adapter.py`

- [ ] **Step 1: Write GUI adapter tests**

Create `tests/test_gui_batch_adapter.py`:

```python
import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Models as MODELS
import O4_GUI_Utils as GUI


class GuiBatchAdapterTests(unittest.TestCase):
    def test_batch_plan_from_gui_state_maps_steps_and_tiles(self):
        state = SimpleNamespace(
            custom_build_dir="D:/Tiles/",
            list_lat_lon=[(2, 3), (1, 4)],
            do_osm=True,
            do_mesh=False,
            do_mask=True,
            do_dsf=True,
            do_ovl=False,
            override_cfg=True,
            provider="BI",
            zoom_level=16,
        )

        plan = GUI.batch_plan_from_state(state)

        self.assertIsInstance(plan, MODELS.BuildPlan)
        self.assertEqual([(tile.lat, tile.lon) for tile in plan.tiles], [(1, 4), (2, 3)])
        self.assertEqual(plan.tiles[0].steps, ("vector", "masks", "tile"))
        self.assertTrue(plan.tiles[0].override_tile_config)

    def test_completion_callback_removes_completed_gui_tile(self):
        canvas = mock.Mock()
        dico_tiles_todo = {(1, 2): "rect-id"}
        gui = SimpleNamespace(
            earth_window=SimpleNamespace(
                canvas=canvas,
                dico_tiles_todo=dico_tiles_todo,
            )
        )
        callback = GUI.batch_completion_callback(gui)

        callback(MODELS.BuildTileResult(1, 2, True, "all"))

        canvas.delete.assert_called_once_with("rect-id")
        self.assertEqual(dico_tiles_todo, {})

    def test_completion_callback_does_not_remove_failed_tile(self):
        canvas = mock.Mock()
        dico_tiles_todo = {(1, 2): "rect-id"}
        gui = SimpleNamespace(
            earth_window=SimpleNamespace(
                canvas=canvas,
                dico_tiles_todo=dico_tiles_todo,
            )
        )
        callback = GUI.batch_completion_callback(gui)

        callback(MODELS.BuildTileResult(1, 2, False, "mesh", "mesh failed"))

        canvas.delete.assert_not_called()
        self.assertEqual(dico_tiles_todo, {(1, 2): "rect-id"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run python -m unittest tests.test_gui_batch_adapter -v
```

Expected: fails because `batch_plan_from_state` and `batch_completion_callback` do not exist.

- [ ] **Step 3: Add GUI batch adapter helpers**

In `src/O4_GUI_Utils.py`, add imports near existing imports:

```python
import O4_Build_Core as CORE
import O4_Build_Models as MODELS
```

Add these module-level helpers near other non-class helpers:

```python
def batch_plan_from_state(state) -> MODELS.BuildPlan:
    steps = _batch_steps_from_state(state)
    custom_build_dir = state.custom_build_dir
    if custom_build_dir and not custom_build_dir.endswith(("/", "\\")):
        custom_build_dir += "/"
    tiles = tuple(
        MODELS.BuildTilePlan(
            lat=lat,
            lon=lon,
            provider=state.provider,
            zoom_level=state.zoom_level,
            output_dir=custom_build_dir or FNAMES.Tile_dir,
            custom_build_dir=custom_build_dir,
            steps=steps,
            override_tile_config=state.override_cfg,
        )
        for lat, lon in sorted(state.list_lat_lon)
    )
    return MODELS.BuildPlan(tiles)


def _batch_steps_from_state(state) -> tuple[str, ...]:
    steps: list[str] = []
    if state.do_osm:
        steps.append("vector")
    if state.do_mesh:
        steps.append("mesh")
    if state.do_mask:
        steps.append("masks")
    if state.do_dsf:
        steps.append("tile")
    if state.do_ovl:
        steps.append("overlays")
    return tuple(steps)


def batch_completion_callback(gui):
    def _callback(result: MODELS.BuildTileResult) -> None:
        if not result.ok:
            return
        try:
            tile_id = gui.earth_window.dico_tiles_todo[(result.lat, result.lon)]
            gui.earth_window.canvas.delete(tile_id)
            gui.earth_window.dico_tiles_todo.pop((result.lat, result.lon), None)
        except (AttributeError, KeyError) as exc:
            UI.vprint(3, exc)

    return _callback
```

- [ ] **Step 4: Update GUI earth-window `batch_build`**

In `src/O4_GUI_Utils.py`, replace the body of `Ortho4XP_Earth_Preview.batch_build` after the empty-selection guard with:

```python
        state = SimpleNamespace(
            custom_build_dir=self.custom_build_dir,
            list_lat_lon=list_lat_lon,
            do_osm=self.v_["Assemble vector data"].get(),
            do_mesh=self.v_["Triangulate 3D mesh"].get(),
            do_mask=self.v_["Draw water masks"].get(),
            do_dsf=self.v_["Build imagery/DSF"].get(),
            do_ovl=self.v_["Extract overlays"].get(),
            override_cfg=self.v_["Override tile configs"].get(),
            provider=str(self.parent.default_website.get()),
            zoom_level=int(self.parent.default_zl.get()),
        )
        plan = batch_plan_from_state(state)
        threading.Thread(
            target=CORE.build_batch,
            args=[plan],
            kwargs={"on_tile_complete": batch_completion_callback(self.parent)},
        ).start()
        return
```

Also add `from types import SimpleNamespace` near the top if it is not already imported.

- [ ] **Step 5: Convert `O4_Tile_Utils.build_tile_list` to compatibility wrapper**

In `src/O4_Tile_Utils.py`, add import near existing imports:

```python
import O4_Build_Models as MODELS
```

Replace `build_tile_list(...)` with:

```python
def build_tile_list(
    tile, list_lat_lon, do_osm, do_mesh, do_mask, do_dsf, do_ovl, override_cfg
):
    import O4_Build_Core as CORE

    steps = _batch_steps(do_osm, do_mesh, do_mask, do_dsf, do_ovl)
    plans = tuple(
        MODELS.BuildTilePlan(
            lat=lat,
            lon=lon,
            provider=getattr(tile, "default_website", ""),
            zoom_level=getattr(tile, "default_zl", 0),
            output_dir=tile.custom_build_dir or FNAMES.Tile_dir,
            custom_build_dir=tile.custom_build_dir,
            steps=steps,
            override_tile_config=override_cfg,
        )
        for lat, lon in sorted(list_lat_lon)
    )
    result = CORE.build_batch(MODELS.BuildPlan(plans))
    return 1 if result.ok else 0


def _batch_steps(do_osm, do_mesh, do_mask, do_dsf, do_ovl) -> tuple[str, ...]:
    steps: list[str] = []
    if do_osm:
        steps.append("vector")
    if do_mesh:
        steps.append("mesh")
    if do_mask:
        steps.append("masks")
    if do_dsf:
        steps.append("tile")
    if do_ovl:
        steps.append("overlays")
    return tuple(steps)
```

- [ ] **Step 6: Run GUI and compatibility tests**

Run:

```bash
uv run python -m unittest tests.test_gui_batch_adapter tests.test_build_core tests.test_build_core_wrapper -v
```

Expected: all tests pass.

- [ ] **Step 7: Run lint/type checks**

Run:

```bash
uv run ruff check src/O4_GUI_Utils.py src/O4_Tile_Utils.py tests/test_gui_batch_adapter.py
uv run ty check src/O4_GUI_Utils.py src/O4_Tile_Utils.py tests/test_gui_batch_adapter.py
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add src/O4_GUI_Utils.py src/O4_Tile_Utils.py tests/test_gui_batch_adapter.py
git commit -m "refactor: route GUI batch builds through core"
```

---

### Task 6: Add Fixture, CI Smoke Check, Docs, And Tracking

**Files:**
- Create: `tests/fixtures/build_job_minimal.toml`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `docs/development.md`
- Modify: `TODO.md`

- [ ] **Step 1: Add fixture**

Create `tests/fixtures/build_job_minimal.toml`:

```toml
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 0
lon = 0
```

- [ ] **Step 2: Add CI smoke checks**

In `.github/workflows/ci.yml`, after each existing `CLI startup smoke test` step, add:

```yaml
      - name: Headless build job validation smoke test
        run: uv run python Ortho4XP.py validate-job tests/fixtures/build_job_minimal.toml
```

Add the step once under Linux, once under Windows x64, and once under macOS.

- [ ] **Step 3: Document headless commands in README**

In `README.md`, add a section near the existing CLI/logging/build documentation:

```markdown
## Headless Build Jobs

Batch automation can validate or run a structured `build_job.toml` file without
opening the GUI:

```bash
python Ortho4XP.py validate-job build_job.toml
python Ortho4XP.py validate-job build_job.toml --json
python Ortho4XP.py build-job build_job.toml --dry-run
python Ortho4XP.py build-job build_job.toml
```

Minimal job file:

```toml
provider = "BI"
zoom_level = 16
output_dir = "Tiles"

[[tiles]]
lat = 43
lon = -79
```

`output_dir` is a base directory. Relative paths are resolved relative to the
job file. The tile above writes to `Tiles/zOrtho4XP_+43-079` relative to the
job file directory.

Tile selection can use explicit `[[tiles]]` entries, inclusive `[bounds]`, or
both. Provider keys may be normal imagery provider keys or combined provider
keys. Exit codes are `0` for success, `1` for build failure or interruption,
and `2` for usage or validation errors.
```

- [ ] **Step 4: Document testing behavior in development guide**

In `docs/development.md`, append:

```markdown
## Headless CLI Validation Tests

`validate-job` and `build-job --dry-run` must not import GUI modules, import
`O4_Config_Utils`, create `Ortho4XP.cfg`, or create generated runtime
directories. Tests should run these commands from a temporary non-repository
working directory to prove provider resources are resolved from the application
root rather than the process current working directory.
```

- [ ] **Step 5: Mark TODO-022 done after verification**

In `TODO.md`, under `### TODO-022: Execute Headless CLI Transition`, insert `Status: Done` and a completion paragraph:

```markdown
Status: Done

Completed by adding early-dispatched `validate-job` and `build-job` headless
subcommands, a tested `build_job.toml` parser, neutral build plan/result
models, and `O4_Build_Core.build_batch()` for multi-tile execution. Validation
runs without GUI/config side effects, supports explicit tiles plus inclusive
bounds, validates normal and combined provider keys, resolves relative output
directories from the job file, and returns deterministic exit codes. GUI batch
work now routes through the same core batch API.
```

Do this step only after all verification in Task 7 passes. If any acceptance
criterion is not met, do not mark the TODO done.

- [ ] **Step 6: Run docs/fixture tests**

Run:

```bash
uv run python Ortho4XP.py validate-job tests/fixtures/build_job_minimal.toml
uv run python Ortho4XP.py validate-job tests/fixtures/build_job_minimal.toml --json
uv run python Ortho4XP.py build-job tests/fixtures/build_job_minimal.toml --dry-run
```

Expected:
- all commands exit `0`;
- human commands print `Build job valid`;
- JSON command prints `"ok": true`;
- no tile build directories are created by `build-job --dry-run`.

- [ ] **Step 7: Commit docs, CI, fixture, and TODO tracking**

```bash
git add tests/fixtures/build_job_minimal.toml .github/workflows/ci.yml README.md docs/development.md TODO.md
git commit -m "docs: document headless build job CLI"
```

---

### Task 7: Full Verification And Issue Evidence

**Files:**
- Validate all changed Python, docs, tests, and CI files.
- GitHub issue: `#17`

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run python -m unittest tests.test_build_models tests.test_cli_jobs tests.test_cli_run tests.test_headless_launcher tests.test_build_core tests.test_gui_batch_adapter -v
```

Expected: all tests pass.

- [ ] **Step 2: Run full unittest discovery**

Run:

```bash
uv run python -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 3: Run Ruff**

Run:

```bash
uv run ruff check Ortho4XP.py src tests
```

Expected: no errors.

- [ ] **Step 4: Run Ruff format check**

Run:

```bash
uv run ruff format --check Ortho4XP.py src tests
```

Expected: no files would be reformatted. If formatting fails, run `uv run ruff format Ortho4XP.py src tests`, inspect the diff, rerun the check, and include formatting changes in the final commit.

- [ ] **Step 5: Run ty on changed Python files**

Run:

```bash
uv run ty check Ortho4XP.py src/O4_Build_Models.py src/O4_CLI_Jobs.py src/O4_CLI_Run.py src/O4_Build_Core.py src/O4_GUI_Utils.py src/O4_Tile_Utils.py tests/test_build_models.py tests/test_cli_jobs.py tests/test_cli_run.py tests/test_headless_launcher.py tests/test_build_core.py tests/test_gui_batch_adapter.py
```

Expected: no errors.

- [ ] **Step 6: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 7: Run repository quality check**

Run:

```bash
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected: full quality check passes. If native tooling is unavailable on the local machine, rerun with `--skip-native`, record the blocker, and do not claim full native verification.

- [ ] **Step 8: Add GitHub issue evidence**

Run:

```bash
gh issue comment 17 --repo tvproductions/Ortho4XP --body "Implemented TODO-022 headless CLI transition. Evidence: focused headless CLI, TOML validation, core batch, launcher, and GUI adapter tests passed; full unittest discovery passed; Ruff check and format check passed; ty passed on changed Python files; git diff --check passed; repository quality check passed. The implementation adds early-dispatched validate-job/build-job commands, deterministic build_job.toml validation with explicit tiles and inclusive bounds, normal and combined provider validation, job-file-relative output directories, dry-run validation without generated artifacts, structured batch results, and GUI batch routing through the same core batch API."
```

Expected: issue comment is created.

- [ ] **Step 9: Close GitHub issue**

Run:

```bash
gh issue close 17 --repo tvproductions/Ortho4XP --comment "Closing after TODO-022 acceptance criteria and repository quality verification passed."
```

Expected: issue #17 is closed.

- [ ] **Step 10: Final status check**

Run:

```bash
git status --short
git log --oneline -8
```

Expected:
- worktree is clean;
- recent commits show the scoped TODO-022 implementation sequence.

## Self-Review Notes

- Spec coverage: Tasks 1-2 cover neutral models, TOML parsing, bounds, provider keys, zoom, output directories, validation errors, and JSON output. Task 3 covers early headless CLI dispatch, dry-run, exit codes, and no GUI/config side effects. Task 4 covers core multi-tile batch execution, selected steps, overlays, config override, incomplete imagery retry, falsey return mapping, callbacks, and aggregate results. Task 5 covers GUI as presentation over the same core API. Task 6 covers docs, CI, fixture, TODO tracking. Task 7 covers verification and GitHub issue evidence.
- Placeholder scan: no placeholder implementation sections are intended. Any task marked as "after verification" names the exact condition and exact text to apply.
- Type consistency: `BuildPlan`, `BuildTilePlan`, `BuildTileResult`, and `BuildBatchResult` are defined in `O4_Build_Models` and imported by CLI/core/GUI consumers.
