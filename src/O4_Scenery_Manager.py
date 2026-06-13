import json
import os
import re

from O4_Scenery_INI import SceneryEntry, SceneryINI


class SceneryError(Exception):
    pass


class SceneryManager:
    def __init__(self, custom_scenery_dir: str = "", ini_path: str | None = None):
        self.custom_scenery_dir = os.path.normpath(custom_scenery_dir) if custom_scenery_dir else ""
        self._ini_path = ini_path or ""
        self._ini = SceneryINI(self._ini_path)
        self._ortho4xp_indices: set[int] = set()

    def refresh(self) -> None:
        self._ini.read()
        self._ortho4xp_indices = set()
        for i, entry in enumerate(self._ini.entries()):
            if self._is_ortho4xp(entry):
                self._ortho4xp_indices.add(i)

    def entries(self) -> list[SceneryEntry]:
        return self._ini.entries()

    def ortho4xp_entries(self) -> list[SceneryEntry]:
        return [e for i, e in enumerate(self._ini.entries()) if i in self._ortho4xp_indices]

    def _is_ortho4xp(self, entry: SceneryEntry) -> bool:
        dir_name = os.path.basename(entry.path.rstrip("/\\"))
        full_path = os.path.join(self.custom_scenery_dir, dir_name)
        pkg_json = os.path.join(full_path, "package.json")
        if os.path.isfile(pkg_json):
            try:
                with open(pkg_json) as f:
                    data = json.load(f)
                if data.get("generation", {}).get("tool") == "Ortho4XP":
                    return True
            except (json.JSONDecodeError, OSError):
                pass
        if re.match(r"^Ortho4XP_(?:Mesh|Overlay|Overlays)(?:_[+-]\d+[+-]\d+)?$", dir_name):
            return True
        if re.match(r"^zOrtho4XP_[+-]\d+[+-]\d+$", dir_name):
            return True
        return bool(re.match(r"^yOrtho4XP_?.*$", dir_name))
