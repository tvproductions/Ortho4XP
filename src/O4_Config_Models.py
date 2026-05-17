import ast
import copy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator


_ALLOWED_CONFIG_TYPES = {bool, float, int, list, str}
_TYPE_ADAPTERS = {
    bool: TypeAdapter(bool),
    float: TypeAdapter(float),
    int: TypeAdapter(int),
    list: TypeAdapter(list),
    str: TypeAdapter(str),
}


class ConfigVariableDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    type: type
    default: Any
    hint: str
    module: str | None = None
    values: list[Any] | tuple[Any, ...] | None = None
    short_name: str | None = None

    @field_validator("type")
    @classmethod
    def _validate_type(cls, value: type) -> type:
        if value not in _ALLOWED_CONFIG_TYPES:
            raise ValueError(f"unsupported config type: {value}")
        return value


class ZoneListDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zones: list[list[Any] | tuple[Any, Any, Any]] = Field(default_factory=list)

    @field_validator("zones")
    @classmethod
    def _validate_zone_entries(cls, value: list[Any]) -> list[Any]:
        for zone in value:
            if not isinstance(zone, (list, tuple)) or len(zone) != 3:
                raise ValueError("each zone_list entry must contain three items")
        return value


def validate_config_registry(registry: dict[str, dict[str, Any]]) -> None:
    for definition in registry.values():
        ConfigVariableDefinition.model_validate(definition)


def config_default(definition: dict[str, Any]) -> Any:
    return copy.deepcopy(definition["default"])


def parse_legacy_config_literal(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    value = value.strip()
    if len(value) >= 2 and value[0] in {"'", '"'} and value[-1] == value[0]:
        return value[1:-1]
    return value


def coerce_config_value(
    var: str, value: Any, registry: dict[str, dict[str, Any]]
) -> Any:
    definition = registry[var]
    expected_type = definition["type"]
    value = parse_legacy_config_literal(value)
    if expected_type in (bool, list) and isinstance(value, str):
        value = ast.literal_eval(value)
    if expected_type is list and var != "zone_list":
        return value
    coerced = _TYPE_ADAPTERS[expected_type].validate_python(value)
    if var == "zone_list":
        ZoneListDefinition.model_validate({"zones": coerced})
    allowed_values = definition.get("values")
    if allowed_values is not None and coerced not in allowed_values:
        raise ValueError(f"{var} must be one of {allowed_values}")
    return coerced


def parse_legacy_zone_append(line: str) -> list[Any] | None:
    prefix = "zone_list.append("
    suffix = ")"
    stripped = line.strip()
    if not stripped.startswith(prefix) or not stripped.endswith(suffix):
        return None
    entry = ast.literal_eval(stripped[len(prefix) : -len(suffix)])
    ZoneListDefinition.model_validate({"zones": [entry]})
    return entry
