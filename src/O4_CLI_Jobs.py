from __future__ import annotations

import json
import os
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, cast

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
    if not coordinates and "tiles" not in raw and "bounds" not in raw:
        errors.append(
            ValidationError("tiles", "at least one tile or bounds block is required")
        )

    if errors:
        raise JobValidationError(errors)

    assert output_dir is not None
    assert provider is not None
    assert zoom_level is not None
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


def validation_failure_json(
    errors: list[ValidationError] | tuple[ValidationError, ...],
) -> str:
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
    raw: Mapping[str, Any], field: str, errors: list[ValidationError]
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
    raw: Mapping[str, Any], field: str, errors: list[ValidationError]
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
        errors.append(
            ValidationError("zoom_level", "must be greater than zero", zoom_level)
        )
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


def _coordinates(
    raw: dict[str, Any], errors: list[ValidationError]
) -> tuple[TileCoordinate, ...]:
    coordinates: set[TileCoordinate] = set()
    coordinates.update(_explicit_tiles(raw.get("tiles", []), errors))
    bounds = raw.get("bounds")
    if bounds is not None:
        coordinates.update(_bounds_tiles(bounds, errors))
    return tuple(sorted(coordinates, key=lambda coord: (coord.lat, coord.lon)))


def _explicit_tiles(
    value: object, errors: list[ValidationError]
) -> list[TileCoordinate]:
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
        item_mapping = cast(Mapping[str, Any], item)
        for key in sorted(set(item) - {"lat", "lon"}):
            errors.append(
                ValidationError(
                    f"tiles[{index}].{key}",
                    "per-tile override is not supported",
                    item[key],
                )
            )
        lat = _coordinate_field(item_mapping, f"tiles[{index}].lat", "lat", errors)
        lon = _coordinate_field(item_mapping, f"tiles[{index}].lon", "lon", errors)
        if lat is not None and lon is not None:
            coordinates.append(TileCoordinate(lat, lon))
    return coordinates


def _bounds_tiles(value: object, errors: list[ValidationError]) -> list[TileCoordinate]:
    if not isinstance(value, dict):
        errors.append(ValidationError("bounds", "must be a table", value))
        return []
    value_mapping = cast(Mapping[str, Any], value)
    lat_min = _coordinate_field(value_mapping, "bounds.lat_min", "lat_min", errors)
    lat_max = _coordinate_field(value_mapping, "bounds.lat_max", "lat_max", errors)
    lon_min = _coordinate_field(value_mapping, "bounds.lon_min", "lon_min", errors)
    lon_max = _coordinate_field(value_mapping, "bounds.lon_max", "lon_max", errors)
    for key in sorted(set(value) - {"lat_min", "lat_max", "lon_min", "lon_max"}):
        errors.append(ValidationError(f"bounds.{key}", "unknown field", value[key]))
    if lat_min is None or lat_max is None or lon_min is None or lon_max is None:
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
    raw: Mapping[str, Any],
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
                ValidationError(
                    field, f"must be between {MIN_LAT} and {MAX_LAT}", value
                )
            )
            return None
    if key.startswith("lon") or field.endswith(".lon"):
        if value < MIN_LON or value > MAX_LON:
            errors.append(
                ValidationError(
                    field, f"must be between {MIN_LON} and {MAX_LON}", value
                )
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
