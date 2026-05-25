"""Shared deterministic fixtures for TODO-017 DSF header bridge tests."""

from pathlib import Path

from O4_DSF_Header_Models import DsfHeaderBridgeRequest


class FakeToolResult:
    def __init__(self, *, ok: bool, error_summary: str | None = None):
        self.ok = ok
        self.error_summary = error_summary
        self.returncode = 0 if ok else 1


class TextRoundTripTool:
    """Fake DSFTool/7z runner that writes the files each bridge step expects."""

    def __init__(
        self, default_text_source: Path, extracted_default: Path | None = None
    ):
        self.default_text_source = default_text_source
        self.extracted_default = extracted_default
        self.calls = []
        self.spliced_text = ""

    def run(self, tool_name, args, *, executable):
        self.calls.append((tool_name, tuple(args), executable))
        if tool_name == "7z":
            return self._extract_default_dsf()
        output_path = Path(args[-1])
        if args[0] == "--dsf2text":
            output_path.write_text(self._text_for_dsf(Path(args[1])), encoding="utf-8")
        elif args[0] == "--text2dsf":
            self.spliced_text = Path(args[1]).read_text(encoding="utf-8")
            output_path.write_bytes(b"spliced dsf")
        return FakeToolResult(ok=True)

    def _extract_default_dsf(self):
        if self.extracted_default is None:
            raise AssertionError("compressed fixture missing extracted path")
        self.extracted_default.write_bytes(b"default dsf")
        return FakeToolResult(ok=True)

    def _text_for_dsf(self, source: Path) -> str:
        if source == self.default_text_source:
            return DEFAULT_DSF_TEXT
        return GENERATED_DSF_TEXT


DEFAULT_DSF_TEXT = """PROPERTY sim/west -123
PROPERTY sim/season/winter_raster Resources/default scenery/winter.png
PROPERTY sim/vegetation_region pacific_northwest
PROPERTY sim/soundscape airport_terminal_small
PROPERTY sim/runway_friction 0.82
ATTR_season winter
PROPERTY sim/east -122
PROPERTY sim/unrelated keepout
TERRAIN_DEF terrain/default.ter
BEGIN_PATCH 0
PROPERTY sim/season/late_body ignored
END_PATCH
"""

GENERATED_DSF_TEXT = """PROPERTY sim/west -123
PROPERTY sim/east -122
PROPERTY sim/south 12
PROPERTY sim/north 13
TERRAIN_DEF terrain/ortho.ter
BEGIN_PATCH 0
END_PATCH
"""


def global_scenery_dsf_path(root: Path) -> Path:
    return root / "Earth nav data" / "+10-130" / "+12-123.dsf"


def bridge_request(
    *,
    tmp: Path,
    root: Path | str,
    generated_dsf: Path,
    run_external_tool,
) -> DsfHeaderBridgeRequest:
    return DsfHeaderBridgeRequest(
        lat=12,
        lon=-123,
        generated_dsf_path=generated_dsf,
        primary_overlay_src=str(root),
        alternate_overlay_src="",
        tmp_dir=tmp / "tmp",
        dsftool_executable="custom-DSFTool",
        unzip_executable="custom-7z",
        run_external_tool=run_external_tool,
    )
