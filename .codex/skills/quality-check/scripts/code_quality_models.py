from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


MODULE_SOFT_LINE_LIMIT = 600
MODULE_HARD_LINE_LIMIT = 1000
CLASS_LINE_LIMIT = 300
MODULE_SIZE_WAIVERS = {
    "src/O4_Airport_Discovery.py": "Decomposed airport discovery module; sort_and_reconstruct_runways is 322 lines and resists further splitting without coupling overhead.",
    "src/O4_Config_Utils.py": "Legacy config persistence and GUI bridge module; schema split tracked separately.",
    "src/O4_DSF_Utils.py": "Legacy DSF writer module; phased extraction tracked separately.",
    "src/O4_GUI_Utils.py": "Legacy Tk GUI module; GUI modernization tracked separately.",
    "src/O4_Imagery_Utils.py": "Legacy imagery pipeline module; provider/imagery extraction tracked separately.",
    "src/O4_Mask_Utils.py": "Legacy mask-generation module; extraction tracked separately.",
    "src/O4_Vector_Utils.py": "Legacy vector geometry module; extraction tracked separately.",
}
CLASS_SIZE_WAIVERS = {
    "src/O4_Config_Utils.py::Ortho4XP_Config": "Legacy mutable config aggregate; schema/model migration is tracked separately.",
    "src/O4_GUI_Utils.py::Ortho4XP_Custom_ZL": "Legacy Tk custom-zoom editor; GUI modernization is tracked separately.",
    "src/O4_GUI_Utils.py::Ortho4XP_Earth_Preview": "Legacy Tk preview controller; GUI modernization is tracked separately.",
    "src/O4_GUI_Utils.py::Ortho4XP_GUI": "Legacy Tk application shell; GUI modernization is tracked separately.",
    "src/O4_OSM_Utils.py::OSM_layer": "Legacy OSM layer accumulator; OSM pipeline split is tracked separately.",
    "src/O4_Vector_Utils.py::Vector_Map": "Legacy vector-map aggregate; vector pipeline split is tracked separately.",
}
CODE_QUALITY_SCAN_BASES = [
    "Ortho4XP.py",
    "src",
    "tests",
    ".codex/skills/quality-check/scripts",
    ".codex/skills/repo-hygiene/scripts",
    ".codex/skills/git-sync/scripts",
]


class CodeQualityFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check: str = Field(min_length=1)
    path: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = Field(pattern="^(warn|block)$")
    line: int | None = None

    @property
    def location(self) -> str:
        return f"{self.path}:{self.line}" if self.line is not None else self.path


def relative_project_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def line_count(path: Path) -> int:
    try:
        with path.open(encoding="utf-8") as handle:
            return sum(1 for _line in handle)
    except UnicodeDecodeError:
        return 0


def python_files_from_base(base_path: Path) -> list[Path]:
    if not base_path.exists():
        return []
    if base_path.is_file():
        return [base_path] if base_path.suffix == ".py" else []
    return [
        item
        for item in base_path.rglob("*.py")
        if "__pycache__" not in item.parts and "Unused" not in item.parts
    ]


def scan_python_files(project_root: Path) -> list[Path]:
    paths = [
        path
        for base in CODE_QUALITY_SCAN_BASES
        for path in python_files_from_base(project_root / base)
    ]
    return sorted(dict.fromkeys(paths))


def stale_waiver_findings(
    check: str, label: str, waivers: dict[str, str], existing: set[str]
) -> list[CodeQualityFinding]:
    return [
        CodeQualityFinding(
            check=check,
            path=f"{label}::{stale}",
            message="Waiver references an item that is no longer scanned.",
            severity="block",
        )
        for stale in sorted(set(waivers) - existing)
    ]
