from dataclasses import dataclass
from typing import Callable, Protocol

import O4_File_Names as FNAMES
import O4_UI_Utils as UI


ConvertTexture = Callable[[object, int, int, int, str], object]


class TextureConversionQueue(Protocol):
    def get(self, block: bool = True, timeout: float | None = None): ...

    def get_nowait(self): ...

    def qsize(self) -> int: ...


@dataclass(frozen=True)
class TextureConversionJob:
    tile: object
    til_x_left: int
    til_y_top: int
    zoomlevel: int
    provider_code: str

    @classmethod
    def from_queue_item(cls, item):
        tile, til_x_left, til_y_top, zoomlevel, provider_code = item
        return cls(tile, til_x_left, til_y_top, zoomlevel, provider_code)

    @property
    def display_name(self):
        return FNAMES.dds_file_name_from_attributes(
            self.til_x_left,
            self.til_y_top,
            self.zoomlevel,
            self.provider_code,
        )


@dataclass(frozen=True)
class TextureConversionBatchResult:
    completed: int
    failed: int
    interrupted: bool
    failures: tuple


@dataclass(frozen=True)
class TextureConversionSchedulerOptions:
    progress_bar: int = 3
    poll_interval: float = 0.05


def run_texture_conversion_queue(
    convert_queue,
    max_workers,
    *,
    convert_texture: ConvertTexture,
    options=None,
):
    import O4_Texture_Conversion_Runner as TCR

    scheduler = TCR.TextureConversionQueueRunner(
        convert_queue=convert_queue,
        max_workers=max_workers,
        convert_texture=convert_texture,
        options=options or TextureConversionSchedulerOptions(),
    )
    return scheduler.run()
