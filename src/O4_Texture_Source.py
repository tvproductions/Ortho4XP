"""In-memory texture source contracts for the imagery conversion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from PIL import Image

TextureAttributes: TypeAlias = tuple[int, int, int, str]


@dataclass(frozen=True)
class TextureSource:
    tile: object
    attrs: TextureAttributes
    image: Image.Image
    cache_path: str | None = None
    wrote_cache: bool = False

    @property
    def til_x_left(self) -> int:
        return self.attrs[0]

    @property
    def til_y_top(self) -> int:
        return self.attrs[1]

    @property
    def zoomlevel(self) -> int:
        return self.attrs[2]

    @property
    def provider_code(self) -> str:
        return self.attrs[3]


@dataclass(frozen=True)
class TextureBuildResult:
    attrs: TextureAttributes
    provider_code: str
    source: TextureSource | None = None
    error_summary: str | None = None
    incomplete: bool = False
    interrupted: bool = False

    @classmethod
    def success(
        cls,
        source: TextureSource,
        *,
        incomplete: bool = False,
    ) -> TextureBuildResult:
        return cls(
            attrs=source.attrs,
            provider_code=source.provider_code,
            source=source,
            incomplete=incomplete,
        )

    @classmethod
    def failure(
        cls,
        attrs: TextureAttributes,
        provider_code: str,
        error_summary: str,
        *,
        incomplete: bool = False,
        interrupted: bool = False,
    ) -> TextureBuildResult:
        return cls(
            attrs=attrs,
            provider_code=provider_code,
            error_summary=error_summary,
            incomplete=incomplete,
            interrupted=interrupted,
        )

    @property
    def ok(self) -> int:
        return 1 if self.source is not None and not self.interrupted else 0
