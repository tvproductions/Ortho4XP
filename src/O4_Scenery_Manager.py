import json
import os
import platform
import re
from dataclasses import dataclass

from O4_Scenery_INI import SceneryEntry, SceneryINI
import O4_Subprocess_Runtime as RUNTIME


class SceneryError(Exception):
    pass


@dataclass
class ValidationIssue:
    severity: str
    message: str
    entry_path: str | None = None


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
        return [e for i, e in enumerate(self.entries()) if i in self._ortho4xp_indices]

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
        return bool(re.match(r"^yOrtho4XP_(?:Overlays?)?$", dir_name))

    def reorder(self) -> None:
        self.refresh()
        entries = self._ini.entries()
        ortho_indices = sorted(self._ortho4xp_indices)
        if not ortho_indices:
            return

        ortho_entries = [entries[i] for i in ortho_indices]
        non_ortho_front = [entries[i] for i in range(ortho_indices[0]) if i not in ortho_indices]
        non_ortho_back = [entries[i] for i in range(ortho_indices[-1] + 1, len(entries)) if i not in ortho_indices]

        overlays = sorted(
            [e for e in ortho_entries if "Overlay" in e.path or "Overlays" in e.path],
            key=lambda e: e.path,
        )
        meshes = sorted(
            [e for e in ortho_entries if "Mesh" in e.path or "zOrtho4XP" in e.path],
            key=lambda e: e.path,
        )

        new_entries = non_ortho_front + overlays + meshes + non_ortho_back
        self._ini._entries = new_entries
        self._ini.write()
        self.refresh()

    def validate(self) -> list[ValidationIssue]:
        self.refresh()
        issues: list[ValidationIssue] = []
        entries = self._ini.entries()

        if not self.custom_scenery_dir:
            issues.append(ValidationIssue(
                severity="error",
                message="custom_scenery_dir is not set",
            ))
            return issues

        for i in sorted(self._ortho4xp_indices):
            entry = entries[i]
            dir_name = os.path.basename(entry.path.rstrip("/\\"))
            full_path = os.path.join(self.custom_scenery_dir, dir_name)
            if not os.path.isdir(full_path):
                issues.append(ValidationIssue(
                    severity="error",
                    message="Directory not found: " + full_path,
                    entry_path=entry.path,
                ))

        last_overlay_pos = -1
        first_mesh_pos = len(entries)
        for i in sorted(self._ortho4xp_indices):
            entry = entries[i]
            if "Overlay" in entry.path or "Overlays" in entry.path:
                last_overlay_pos = max(last_overlay_pos, i)
            if "Mesh" in entry.path or "zOrtho4XP" in entry.path:
                first_mesh_pos = min(first_mesh_pos, i)
        if last_overlay_pos > first_mesh_pos:
            issues.append(ValidationIssue(
                severity="warning",
                message="Overlay entries should appear above mesh entries in scenery_packs.ini. Run 'reorder' to fix.",
            ))

        for i in sorted(self._ortho4xp_indices):
            if entries[i].disabled:
                issues.append(ValidationIssue(
                    severity="warning",
                    message="Entry is disabled: " + entries[i].path,
                    entry_path=entries[i].path,
                ))

        seen: set[str] = set()
        for i in sorted(self._ortho4xp_indices):
            dir_name = os.path.basename(entries[i].path.rstrip("/\\"))
            if dir_name in seen:
                issues.append(ValidationIssue(
                    severity="error",
                    message="Duplicate entry: " + entries[i].path,
                    entry_path=entries[i].path,
                ))
            seen.add(dir_name)

        return issues

    def add_tile(self, lat: int, lon: int, build_dir: str | None = None) -> None:
        tile_name = self._resolve_tile_dir(lat, lon)
        tile_build_path = self._resolve_build_path(lat, lon, build_dir)
        if not os.path.isdir(tile_build_path):
            raise SceneryError("Tile directory not found: " + tile_build_path)
        if self.custom_scenery_dir and os.path.commonpath([tile_build_path, self.custom_scenery_dir]) != self.custom_scenery_dir:
            self._create_symlink(tile_build_path, tile_name)
        ini_path = os.path.join("Custom Scenery", tile_name)
        self.refresh()
        if self._ini.find_by_path(ini_path) is None:
            pos = self._mesh_insertion_position()
            self._ini.add_entry(ini_path, position=pos)
            self._ini.write()

    def add_overlay(self, overlay_dir: str | None = None) -> None:
        overlay_name = "Ortho4XP_Overlays"
        overlay_build_path = overlay_dir or ""
        if not overlay_build_path or not os.path.isdir(overlay_build_path):
            raise SceneryError("Overlay directory not found: " + str(overlay_build_path))
        if self.custom_scenery_dir and os.path.commonpath([overlay_build_path, self.custom_scenery_dir]) != self.custom_scenery_dir:
            self._create_symlink(overlay_build_path, overlay_name)
        ini_path = os.path.join("Custom Scenery", overlay_name)
        self.refresh()
        if self._ini.find_by_path(ini_path) is None:
            pos = self._overlay_insertion_position()
            self._ini.add_entry(ini_path, position=pos)
            self._ini.write()

    def remove_tile(self, lat: int, lon: int) -> bool:
        tile_name = self._resolve_tile_dir(lat, lon)
        ini_path = os.path.join("Custom Scenery", tile_name)
        self.refresh()
        removed_ini = self._ini.remove_entry(ini_path)
        self._ini.write()
        symlink_removed = self._remove_symlink(tile_name)
        return removed_ini or symlink_removed

    def remove_overlay(self) -> bool:
        overlay_name = "Ortho4XP_Overlays"
        ini_path = os.path.join("Custom Scenery", overlay_name)
        self.refresh()
        removed_ini = self._ini.remove_entry(ini_path)
        self._ini.write()
        symlink_removed = self._remove_symlink(overlay_name)
        return removed_ini or symlink_removed

    def _resolve_tile_dir(self, lat: int, lon: int) -> str:
        return "Ortho4XP_Mesh_{:+03d}{:+04d}".format(lat, lon)

    def _resolve_build_path(self, lat: int, lon: int, build_dir: str | None) -> str:
        tile_name = self._resolve_tile_dir(lat, lon)
        if build_dir:
            return os.path.join(os.path.normpath(build_dir), tile_name)
        raise SceneryError("build_dir required to locate tile: " + tile_name)

    def _create_symlink(self, target: str, link_name: str) -> None:
        link_path = os.path.join(self.custom_scenery_dir, link_name)
        if os.path.exists(link_path):
            return
        if platform.system() == "Windows":
            rc, out, err = RUNTIME.run_captured(
                ["cmd.exe", "/c", "mklink", "/J", link_path, target]
            )
            if rc != 0:
                raise SceneryError(
                    "Failed to create junction: " + err.strip()
                )
        else:
            os.symlink(target, link_path)

    def _remove_symlink(self, link_name: str) -> bool:
        link_path = os.path.join(self.custom_scenery_dir, link_name)
        if not os.path.exists(link_path):
            return False
        os.rmdir(link_path)
        return True

    def _overlay_insertion_position(self) -> int:
        entries = self._ini.entries()
        for i, e in enumerate(entries):
            if "Overlay" in e.path or "Overlays" in e.path:
                return i
        for i, e in enumerate(entries):
            if "Mesh" in e.path or "zOrtho4XP" in e.path:
                return i
        return len(entries)

    def _mesh_insertion_position(self) -> int:
        entries = self._ini.entries()
        last_overlay = -1
        for i, e in enumerate(entries):
            if "Overlay" in e.path or "Overlays" in e.path:
                last_overlay = i
        if last_overlay >= 0:
            return last_overlay + 1
        for i, e in enumerate(entries):
            if "Mesh" in e.path or "zOrtho4XP" in e.path:
                return i
        return len(entries)
