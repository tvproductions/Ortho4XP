import os
import sys

import O4_File_Names as FNAMES


def resolve_tool(tool_name: str) -> str:
    normalized = tool_name.lower()
    if normalized == "7z" and _platform_key() == "mac":
        bundled_7z = _tool_path("mac", "7zz")
        return bundled_7z if os.path.exists(bundled_7z) else "7z"
    return _platform_tools().get(normalized, _common_tools().get(normalized, tool_name))


def _platform_key() -> str:
    if "dar" in sys.platform:
        return "mac"
    if "win" in sys.platform:
        return "win"
    return "lin"


def _platform_tools() -> dict[str, str]:
    nvcompress_win = _tool_path("win", "nvcompress", "nvcompress.exe")
    return {
        "mac": {
            "triangle4xp": _tool_path("mac", "Triangle4XP"),
            "triangle": _tool_path("mac", "triangle"),
            "moulinette": _tool_path("mac", "moulinette"),
            "nvcompress": _tool_path("mac", "DDSTool"),
            "ddstool": _tool_path("mac", "DDSTool"),
            "dsftool": _tool_path("mac", "DSFTool"),
        },
        "win": {
            "triangle4xp": _tool_path("win", "Triangle4XP.exe"),
            "triangle": _tool_path("win", "triangle.exe"),
            "moulinette": _tool_path("win", "moulinette.exe"),
            "nvcompress": nvcompress_win,
            "ddstool": nvcompress_win,
            "7z": _tool_path("win", "7z.exe"),
            "dsftool": _tool_path("win", "DSFTool.exe"),
        },
        "lin": {
            "triangle4xp": _tool_path("lin", "Triangle4XP"),
            "triangle": _tool_path("lin", "triangle"),
            "moulinette": _tool_path("lin", "moulinette"),
            "nvcompress": _tool_path("lin", "nvcompress"),
            "ddstool": _tool_path("lin", "nvcompress"),
            "7z": "7z",
            "dsftool": _tool_path("lin", "DSFTool"),
        },
    }[_platform_key()]


def _common_tools() -> dict[str, str]:
    return {}


def _tool_path(*parts: str) -> str:
    return os.path.join(FNAMES.Utils_dir, *parts)
