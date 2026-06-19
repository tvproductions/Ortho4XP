"""In-memory texture source contracts for the imagery conversion pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

type TextureAttributes = tuple[int, int, int, str]


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
        error_summary: str,
        **flags: bool,
    ) -> TextureBuildResult:
        return cls(
            attrs=attrs,
            provider_code=attrs[3],
            error_summary=error_summary,
            incomplete=flags.get("incomplete", False),
            interrupted=flags.get("interrupted", False),
        )

    @property
    def ok(self) -> int:
        return 1 if self.source is not None and not self.interrupted else 0
