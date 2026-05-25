from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DsfHeaderBridgeResult:
    applied: bool
    reason: str
    supported_line_count: int = 0


@dataclass(frozen=True)
class DsfHeaderBridgeRequest:
    lat: int
    lon: int
    generated_dsf_path: Path
    primary_overlay_src: str
    alternate_overlay_src: str
    tmp_dir: Path
    dsftool_executable: str
    unzip_executable: str
    run_external_tool: Callable[..., object]
