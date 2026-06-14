from pathlib import Path
from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationInfo,
    field_validator,
    model_validator,
)


class ProviderDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_type: Literal["wms", "wmts", "tms", "local_tms"] | None = None
    grid_type: Literal["webmercator"] | None = None
    fake_headers: dict[str, str] | None = None
    epsg_code: int | None = None
    in_GUI: bool | None = None
    image_type: str | None = None
    url_prefix: str | None = None
    url_template: str | None = None
    layers: str | None = None
    wms_size: int | None = None
    tile_size: int | None = None
    wms_version: str | None = None
    wmts_version: str | None = None
    top_left_corner: list[float] | None = Field(
        default=None, min_length=2, max_length=2
    )
    scaledenominator: list[float] | None = None
    tilematrixset: str | None = None
    resolutions: list[float] | None = None
    max_threads: int | None = None
    max_zl: int | None = None
    extent: str | None = None
    color_filters: str | None = None
    imagery_dir: Literal["grouped", "normal", "code"] | None = None

    @field_validator("wms_size", "tile_size")
    @classmethod
    def _validate_size(cls, value: int | None) -> int | None:
        if value is not None and (value < 100 or value > 10000):
            raise ValueError("must be between 100 and 10000")
        return value

    @field_validator("wms_version", "wmts_version")
    @classmethod
    def _validate_version(cls, value: str | None) -> str | None:
        if value is not None and len(value.split(".")) < 2:
            raise ValueError("must include at least major and minor version numbers")
        return value

    @field_validator("color_filters")
    @classmethod
    def _validate_color_filter(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        if value is None:
            return value
        color_filters = _context_set(info.context, "color_filters")
        if color_filters is not None and value not in color_filters:
            raise ValueError("unknown color filter; load Filters/*.flt.json first")
        return value

    @model_validator(mode="after")
    def _validate_request_shape(self) -> Self:
        if self.request_type is None and self.grid_type != "webmercator":
            raise ValueError("missing request_type or grid_type=webmercator")
        return self

    def to_runtime_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ExtentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    epsg_code: int | None = None
    mask_bounds: list[float] | None = Field(default=None, min_length=4, max_length=4)
    buffer_width: float | None = None
    mask_width: float | None = None
    blur_width: float | None = None

    def to_runtime_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class ColorFilterStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    operation: str
    parameters: list[float] = Field(default_factory=list)

    def to_runtime_list(self) -> list[Any]:
        return [self.operation, *self.parameters]


class ColorFilterDefinition(RootModel[list[ColorFilterStep]]):
    def to_runtime_list(self) -> list[list[Any]]:
        return [step.to_runtime_list() for step in self.root]


class CombinedProviderLayer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    layer_code: str
    extent_code: str
    color_code: str
    priority: Literal["low", "medium", "high", "mask"]


class CombinedProviderDefinition(RootModel[list[CombinedProviderLayer]]):
    def to_runtime_list(self) -> list[dict[str, str]]:
        return [layer.model_dump() for layer in self.root]


def source_code_from_path(source_path: Path, legacy_extension: str) -> str:
    name = source_path.name
    double_extension = f".{legacy_extension}.json"
    if name.endswith(double_extension):
        return name[: -len(double_extension)]
    return source_path.stem


def _context_set(context: Any, key: str) -> set[str] | None:
    if not isinstance(context, dict):
        return None
    value = context.get(key)
    if value is None:
        return None
    return set(value)
