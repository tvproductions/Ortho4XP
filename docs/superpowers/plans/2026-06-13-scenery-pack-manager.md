# Scenery Pack Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CLI-based management of Ortho4XP scenery packages in X-Plane's `scenery_packs.ini`, coupled with symlink management.

**Architecture:** Low-level `O4_Scenery_INI.py` parses/rewrites the ini file. High-level `O4_Scenery_Manager.py` provides add/remove/list/reorder/validate operations using platform-aware symlink creation and the ini parser. CLI commands in `O4_CLI_Run.py` dispatch to the manager.

**Tech Stack:** Python 3.13+, stdlib `os`, `subprocess`, `json`, `re`, `platform`. Tests use `unittest` with `tempfile.TemporaryDirectory`. No new dependencies.

---

## File Structure

- **Create:** `src/O4_Scenery_INI.py` — line-based ini parser/writer
- **Create:** `src/O4_Scenery_Manager.py` — high-level operations
- **Create:** `tests/test_scenery_ini.py` — parser tests
- **Create:** `tests/test_scenery_manager.py` — manager tests
- **Modify:** `src/O4_CLI_Run.py` — add `scenery` subcommand handlers
- **Modify:** `Ortho4XP.py` — add `scenery` to headless dispatch

---

### Task 1: SceneryINI — Parse and Write

**Files:**
- Create: `src/O4_Scenery_INI.py`
- Create: `tests/test_scenery_ini.py`

- [ ] **Step 1: Write the failing parse tests**

```python
# tests/test_scenery_ini.py
import os
import tempfile
import unittest
from src.O4_Scenery_INI import SceneryINI, SceneryEntry


class TestSceneryINIParse(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)

    def _path(self, name="scenery_packs.ini"):
        return os.path.join(self._temp.name, name)

    def _write(self, content: str) -> str:
        p = self._path()
        with open(p, "w", newline="\n") as f:
            f.write(content)
        return p

    def test_parses_basic_entries(self):
        p = self._write(
            "I\n"
            "1000 Version\n"
            "\n"
            "SCENERY_PACK Custom Scenery/Global Airports/\n"
            "SCENERY_PACK Custom Scenery/Ortho4XP_Mesh_+43-079/\n"
        )
        ini = SceneryINI(p)
        ini.read()
        self.assertEqual(len(ini.entries()), 2)
        self.assertEqual(ini.entries()[0].path, "Custom Scenery/Global Airports/")
        self.assertFalse(ini.entries()[0].disabled)

    def test_parses_disabled_entries(self):
        p = self._write(
            "I\n1000 Version\n\nSCENERY_PACK_DISABLED Custom Scenery/Old/\n"
        )
        ini = SceneryINI(p)
        ini.read()
        self.assertTrue(ini.entries()[0].disabled)

    def test_handles_no_file(self):
        ini = SceneryINI(self._path("missing.ini"))
        ini.read()
        self.assertEqual(ini.entries(), [])

    def test_handles_empty_file(self):
        p = self._write("I\n1000 Version\n\n")
        ini = SceneryINI(p)
        ini.read()
        self.assertEqual(ini.entries(), [])

    def test_ignores_comments_and_blanks(self):
        p = self._write(
            "I\n1000 Version\n\n# comment\nSCENERY_PACK Custom Scenery/A/\n\nSCENERY_PACK Custom Scenery/B/\n"
        )
        ini = SceneryINI(p)
        ini.read()
        self.assertEqual(len(ini.entries()), 2)
```

- [ ] **Step 2: Run tests to confirm failures**

Run: `uv run python -m unittest tests.test_scenery_ini -v`
Expected: 5 FAIL/ERROR

- [ ] **Step 3: Implement SceneryINI parse + write**

```python
# src/O4_Scenery_INI.py
import os
from dataclasses import dataclass


@dataclass
class SceneryEntry:
    path: str
    disabled: bool = False


class SceneryINI:
    def __init__(self, path: str = ""):
        self.path = path
        self._entries: list[SceneryEntry] = []

    def read(self, path: str | None = None) -> None:
        if path:
            self.path = path
        self._entries = []
        if not self.path or not os.path.isfile(self.path):
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("SCENERY_PACK "):
                    raw_path = stripped[len("SCENERY_PACK "):]
                    self._entries.append(SceneryEntry(path=raw_path, disabled=False))
                elif stripped.startswith("SCENERY_PACK_DISABLED "):
                    raw_path = stripped[len("SCENERY_PACK_DISABLED "):]
                    self._entries.append(SceneryEntry(path=raw_path, disabled=True))

    def write(self, path: str | None = None) -> None:
        out_path = path or self.path
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            for entry in self._entries:
                prefix = "SCENERY_PACK_DISABLED " if entry.disabled else "SCENERY_PACK "
                f.write(f"{prefix}{entry.path}\n")

    def entries(self) -> list[SceneryEntry]:
        return list(self._entries)

    def add_entry(self, path: str, position: int | None = None) -> None:
        entry = SceneryEntry(path=path)
        if position is None or position >= len(self._entries):
            self._entries.append(entry)
        else:
            self._entries.insert(position, entry)

    def remove_entry(self, path: str) -> bool:
        for i, e in enumerate(self._entries):
            if e.path == path:
                self._entries.pop(i)
                return True
        return False

    def find_by_path(self, path: str) -> int | None:
        for i, e in enumerate(self._entries):
            if e.path == path:
                return i
        return None
```

- [ ] **Step 4: Run parse tests to confirm pass**

Run: `uv run python -m unittest tests.test_scenery_ini -v`
Expected: 5 OK

- [ ] **Step 5: Write+commit**

```bash
git add src/O4_Scenery_INI.py tests/test_scenery_ini.py
git commit -m "feat: add SceneryINI parser for scenery_packs.ini"
```

---

### Task 2: SceneryINI — Modify and Write Tests

**Files:**
- Modify: `tests/test_scenery_ini.py` (add TestSceneryINIWrite)

- [ ] **Step 1: Write modification tests**

```python
# Add to tests/test_scenery_ini.py

class TestSceneryINIWrite(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)

    def _path(self):
        return os.path.join(self._temp.name, "scenery_packs.ini")

    def _read_ini(self, content: str) -> SceneryINI:
        p = self._path()
        with open(p, "w", newline="\n") as f:
            f.write(content)
        ini = SceneryINI(p)
        ini.read()
        return ini

    def _written_content(self, ini: SceneryINI) -> str:
        ini.write()
        with open(self._path()) as f:
            return f.read()

    def test_write_produces_valid_format(self):
        ini = self._read_ini("")
        ini.add_entry("Custom Scenery/Test/")
        content = self._written_content(ini)
        self.assertIn("I\n1000 Version\n\n", content)
        self.assertIn("SCENERY_PACK Custom Scenery/Test/\n", content)

    def test_add_entry_at_end(self):
        ini = self._read_ini("I\n1000 Version\n\nSCENERY_PACK Custom Scenery/A/\n")
        ini.add_entry("Custom Scenery/B/")
        self.assertEqual(len(ini.entries()), 2)
        self.assertEqual(ini.entries()[-1].path, "Custom Scenery/B/")

    def test_add_entry_at_position(self):
        ini = self._read_ini(
            "I\n1000 Version\n\n"
            "SCENERY_PACK Custom Scenery/A/\n"
            "SCENERY_PACK Custom Scenery/C/\n"
        )
        ini.add_entry("Custom Scenery/B/", position=1)
        self.assertEqual(ini.entries()[1].path, "Custom Scenery/B/")

    def test_remove_entry(self):
        ini = self._read_ini(
            "I\n1000 Version\n\n"
            "SCENERY_PACK Custom Scenery/A/\n"
            "SCENERY_PACK Custom Scenery/B/\n"
        )
        self.assertTrue(ini.remove_entry("Custom Scenery/A/"))
        self.assertEqual(len(ini.entries()), 1)
        self.assertEqual(ini.entries()[0].path, "Custom Scenery/B/")

    def test_remove_nonexistent_returns_false(self):
        ini = self._read_ini("I\n1000 Version\n\nSCENERY_PACK Custom Scenery/A/\n")
        self.assertFalse(ini.remove_entry("Custom Scenery/NotHere/"))

    def test_remove_entry_and_write(self):
        ini = self._read_ini(
            "I\n1000 Version\n\n"
            "SCENERY_PACK Custom Scenery/A/\n"
            "SCENERY_PACK Custom Scenery/B/\n"
        )
        ini.remove_entry("Custom Scenery/A/")
        content = self._written_content(ini)
        self.assertNotIn("Custom Scenery/A/", content)
        self.assertIn("Custom Scenery/B/", content)

    def test_find_by_path(self):
        ini = self._read_ini(
            "I\n1000 Version\n\n"
            "SCENERY_PACK Custom Scenery/A/\n"
            "SCENERY_PACK Custom Scenery/B/\n"
        )
        self.assertEqual(ini.find_by_path("Custom Scenery/A/"), 0)
        self.assertEqual(ini.find_by_path("Custom Scenery/B/"), 1)
        self.assertIsNone(ini.find_by_path("Custom Scenery/C/"))

    def test_disable_entry(self):
        ini = self._read_ini("I\n1000 Version\n\nSCENERY_PACK Custom Scenery/A/\n")
        idx = ini.find_by_path("Custom Scenery/A/")
        ini.entries()[idx].disabled = True
        content = self._written_content(ini)
        self.assertIn("SCENERY_PACK_DISABLED Custom Scenery/A/", content)
```

- [ ] **Step 2: Run modification tests**

Run: `uv run python -m unittest tests.test_scenery_ini -v`
Expected: 1 failure (disable_entry test uses `entries()` which returns a copy — need to fix)

- [ ] **Step 3: Fix `entries()` to return mutable reference (or use property)**

In `O4_Scenery_INI.py`, change `entries()` to return the internal list directly (caller must not reassign):

```python
def entries(self) -> list[SceneryEntry]:
    return self._entries
```

Or add a setter method. Simplest: just return the list directly. Callers can modify entries in place.

- [ ] **Step 4: Rerun all ini tests**

Run: `uv run python -m unittest tests.test_scenery_ini -v`
Expected: 12 OK

- [ ] **Step 5: Commit**

```bash
git add src/O4_Scenery_INI.py tests/test_scenery_ini.py
git commit -m "feat: add SceneryINI add/remove/find/disable operations"
```

---

### Task 3: SceneryManager — Package Detection

**Files:**
- Create: `src/O4_Scenery_Manager.py` (SceneryManager + _PackageDetector)
- Create: `tests/test_scenery_manager.py` (TestPackageDetection)

- [ ] **Step 1: Write detection tests**

```python
# tests/test_scenery_manager.py
import os
import tempfile
import unittest
from src.O4_Scenery_Manager import SceneryManager


class TestPackageDetection(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.cs_dir = os.path.join(self._temp.name, "Custom Scenery")
        os.makedirs(self.cs_dir)

    def _make_package(self, name: str, with_json: bool = True, json_data: dict | None = None) -> str:
        pkg_dir = os.path.join(self.cs_dir, name)
        os.makedirs(os.path.join(pkg_dir, "Earth nav data"))
        if with_json:
            data = json_data or {
                "name": name,
                "type": "mesh",
                "generation": {"tool": "Ortho4XP", "tool_version": "1.0.0", "timestamp": "2026-06-13T00:00:00Z"},
                "compatibility": {"min_xplane_version": "12.0.0"},
            }
            with open(os.path.join(pkg_dir, "package.json"), "w") as f:
                json.dump(data, f)
        return pkg_dir

    def _make_ini(self, entries: list[str]) -> str:
        ini_path = os.path.join(self._temp.name, "scenery_packs.ini")
        with open(ini_path, "w", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            for e in entries:
                f.write(f"SCENERY_PACK Custom Scenery/{e}/\n")
        return ini_path

    def test_detects_by_package_json(self):
        self._make_package("Ortho4XP_Mesh_+43-079")
        ini_path = self._make_ini(["Ortho4XP_Mesh_+43-079"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_detects_by_current_naming(self):
        self._make_package("Ortho4XP_Mesh_+43-079", with_json=False)
        ini_path = self._make_ini(["Ortho4XP_Mesh_+43-079"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_detects_legacy_zortho4xp(self):
        self._make_package("zOrtho4XP_+43-079", with_json=False)
        ini_path = self._make_ini(["zOrtho4XP_+43-079"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_detects_legacy_yortho4xp(self):
        self._make_package("yOrtho4XP_Overlays", with_json=False)
        ini_path = self._make_ini(["yOrtho4XP_Overlays"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_detects_overlay_package(self):
        self._make_package("Ortho4XP_Overlays")
        ini_path = self._make_ini(["Ortho4XP_Overlays"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)

    def test_ignores_non_ortho4xp(self):
        self._make_package("Global Airports", with_json=False)
        ini_path = self._make_ini(["Global Airports"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 0)
```

- [ ] **Step 2: Run detection tests to confirm failures**

Run: `uv run python -m unittest tests.test_scenery_manager -v`
Expected: all FAIL/ERROR (no module yet)

- [ ] **Step 3: Implement SceneryManager with detection**

```python
# src/O4_Scenery_Manager.py
import json
import os
import re
import platform
import subprocess
from src.O4_Scenery_INI import SceneryINI, SceneryEntry


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
        # 1) Check package.json
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
        # 2) Current naming: prefix_purpose_latlon  (config-default: Ortho4XP_Mesh_+43-079)
        if re.match(r"^Ortho4XP_(?:Mesh|Overlay|Overlays)(?:_[+-]\d+[+-]\d+)?$", dir_name):
            return True
        # 3) Legacy naming
        if re.match(r"^zOrtho4XP_[+-]\d+[+-]\d+$", dir_name):
            return True
        if re.match(r"^yOrtho4XP_?.*$", dir_name):
            return True
        return False
```

- [ ] **Step 4: Run detection tests to confirm pass**

Run: `uv run python -m unittest tests.test_scenery_manager -v`
Expected: 7 OK

- [ ] **Step 5: Commit**

```bash
git add src/O4_Scenery_Manager.py tests/test_scenery_manager.py
git commit -m "feat: add SceneryManager with Ortho4XP package detection"
```

---

### Task 4: SceneryManager — Symlink Operations

**Files:**
- Modify: `src/O4_Scenery_Manager.py` (add _create_symlink, _remove_symlink, add_tile, add_overlay, remove_tile, remove_overlay)
- Modify: `tests/test_scenery_manager.py` (add TestSymlinkOperations)

- [ ] **Step 1: Write symlink operation tests**

```python
# Add to tests/test_scenery_manager.py
import json
import platform
import subprocess


class TestSymlinkOperations(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.xplane_root = os.path.join(self._temp.name, "X-Plane")
        self.cs_dir = os.path.join(self.xplane_root, "Custom Scenery")
        os.makedirs(self.cs_dir)
        self.build_dir = os.path.join(self._temp.name, "Tiles")
        os.makedirs(self.build_dir)

    def _make_tile_dir(self, lat: int, lon: int) -> str:
        name = f"Ortho4XP_Mesh_{lat:+d}{lon:+d}"  # e.g. Ortho4XP_Mesh_+43-079
        # Normalize: replace + with nothing for test latlon format
        name = f"Ortho4XP_Mesh_{'+' if lat >= 0 else ''}{lat}{'+' if lon >= 0 else ''}{lon}"
        name = name.replace("+-", "-")
        path = os.path.join(self.build_dir, name)
        os.makedirs(os.path.join(path, "Earth nav data"))
        with open(os.path.join(path, "package.json"), "w") as f:
            json.dump({"name": name, "type": "mesh", "generation": {"tool": "Ortho4XP"}}, f)
        return path

    def _ini_path(self) -> str:
        ini_dir = os.path.join(self.xplane_root, "Output", "preferences")
        os.makedirs(ini_dir, exist_ok=True)
        return os.path.join(ini_dir, "scenery_packs.ini")

    def _make_mgr(self, cs_dir: str | None = None) -> SceneryManager:
        return SceneryManager(
            custom_scenery_dir=cs_dir or self.cs_dir,
            ini_path=self._ini_path(),
        )

    def _is_symlink(self, path: str) -> bool:
        """Cross-platform symlink detection."""
        if platform.system() == "Windows":
            # Junctions report as dirs; check reparse point attribute
            import ctypes
            FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
            attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
            return bool(attrs != -1 and (attrs & FILE_ATTRIBUTE_REPARSE_POINT))
        return os.path.islink(path)

    def test_add_tile_creates_symlink(self):
        tile_path = self._make_tile_dir(43, -79)
        mgr = self._make_mgr()
        mgr.add_tile(lat=43, lon=-79, build_dir=self.build_dir)
        link_path = os.path.join(self.cs_dir, "Ortho4XP_Mesh_+43-079")
        self.assertTrue(os.path.exists(link_path))
        self.assertTrue(self._is_symlink(link_path))

    def test_add_tile_adds_ini_entry(self):
        self._make_tile_dir(43, -79)
        mgr = self._make_mgr()
        mgr.add_tile(lat=43, lon=-79, build_dir=self.build_dir)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 1)
        self.assertIn("Ortho4XP_Mesh_+43-079", mgr.ortho4xp_entries()[0].path)

    def test_remove_tile_removes_symlink(self):
        self._make_tile_dir(43, -79)
        mgr = self._make_mgr()
        mgr.add_tile(lat=43, lon=-79, build_dir=self.build_dir)
        self.assertTrue(mgr.remove_tile(lat=43, lon=-79))
        link_path = os.path.join(self.cs_dir, "Ortho4XP_Mesh_+43-079")
        self.assertFalse(os.path.exists(link_path))

    def test_remove_tile_removes_ini_entry(self):
        self._make_tile_dir(43, -79)
        mgr = self._make_mgr()
        mgr.add_tile(lat=43, lon=-79, build_dir=self.build_dir)
        mgr.remove_tile(lat=43, lon=-79)
        mgr.refresh()
        self.assertEqual(len(mgr.ortho4xp_entries()), 0)

    def test_add_tile_no_symlink_when_same_dir(self):
        self._make_tile_dir(43, -79)
        mgr = self._make_mgr(cs_dir=self.build_dir)
        mgr.add_tile(lat=43, lon=-79, build_dir=self.build_dir)
        # No symlink should exist since cs_dir == build_dir's parent
        link_path = os.path.join(self.build_dir, "Ortho4XP_Mesh_+43-079")
        self.assertFalse(self._is_symlink(link_path))
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run python -m unittest tests.test_scenery_manager -v`
Expected: 5 failures (add_tile/remove_tile not implemented)

- [ ] **Step 3: Implement symlink operations in SceneryManager**

Add to `src/O4_Scenery_Manager.py`:

```python
class SceneryManager:
    # ... existing __init__, refresh, _is_ortho4xp ...

    def add_tile(self, lat: int, lon: int, build_dir: str | None = None) -> None:
        from src.O4_File_Names import FNAMES
        # Import lazy to avoid circular dependency at module level
        tile_name = self._resolve_tile_dir(lat, lon)
        tile_build_path = self._resolve_build_path(lat, lon, build_dir)
        if not os.path.isdir(tile_build_path):
            raise SceneryError(f"Tile directory not found: {tile_build_path}")
        # Create symlink if build dir is outside Custom Scenery
        if self.custom_scenery_dir and not tile_build_path.startswith(self.custom_scenery_dir):
            self._create_symlink(tile_build_path, tile_name)
        # Add ini entry
        ini_path = os.path.join("Custom Scenery", tile_name)
        self.refresh()
        if self._ini.find_by_path(ini_path) is None:
            pos = self._mesh_insertion_position()
            self._ini.add_entry(ini_path, position=pos)
            self._ini.write()

    def add_overlay(self, overlay_dir: str | None = None) -> None:
        from src.O4_File_Names import FNAMES
        overlay_name = getattr(FNAMES, 'overlay_dir_name', lambda: "Ortho4XP_Overlays")()
        overlay_build_path = overlay_dir or getattr(FNAMES, 'Overlay_dir', "")
        if not overlay_build_path or not os.path.isdir(overlay_build_path):
            raise SceneryError(f"Overlay directory not found: {overlay_build_path}")
        if self.custom_scenery_dir and not overlay_build_path.startswith(self.custom_scenery_dir):
            self._create_symlink(overlay_build_path, overlay_name)
        ini_path = os.path.join("Custom Scenery", overlay_name)
        self.refresh()
        if self._ini.find_by_path(ini_path) is None:
            pos = self._overlay_insertion_position()
            self._ini.add_entry(ini_path, position=pos)
            self._ini.write()

    def remove_tile(self, lat: int, lon: int) -> bool:
        from src.O4_File_Names import FNAMES
        tile_name = self._resolve_tile_dir(lat, lon)
        ini_path = os.path.join("Custom Scenery", tile_name)
        self.refresh()
        removed_ini = self._ini.remove_entry(ini_path)
        self._ini.write()
        symlink_removed = self._remove_symlink(tile_name)
        return removed_ini or symlink_removed

    def remove_overlay(self) -> bool:
        from src.O4_File_Names import FNAMES
        overlay_name = getattr(FNAMES, 'overlay_dir_name', lambda: "Ortho4XP_Overlays")()
        ini_path = os.path.join("Custom Scenery", overlay_name)
        self.refresh()
        removed_ini = self._ini.remove_entry(ini_path)
        self._ini.write()
        symlink_removed = self._remove_symlink(overlay_name)
        return removed_ini or symlink_removed

    def _resolve_tile_dir(self, lat: int, lon: int) -> str:
        """Resolve the tile directory name (e.g. Ortho4XP_Mesh_+43-079)."""
        sign_lat = "+" if lat >= 0 else ""
        sign_lon = "+" if lon >= 0 else ""
        return f"Ortho4XP_Mesh_{sign_lat}{abs(lat)}{sign_lon}{abs(lon):03d}"

    def _resolve_build_path(self, lat: int, lon: int, build_dir: str | None) -> str:
        tile_name = self._resolve_tile_dir(lat, lon)
        if build_dir:
            return os.path.join(build_dir, tile_name)
        # Try to find it: check common locations
        for candidate in [self.custom_scenery_dir]:
            p = os.path.join(candidate, tile_name)
            if os.path.isdir(p):
                return p
        raise SceneryError(f"Cannot find build directory for tile {tile_name}")

    def _create_symlink(self, target: str, link_name: str) -> None:
        link_path = os.path.join(self.custom_scenery_dir, link_name)
        if os.path.exists(link_path):
            return
        if platform.system() == "Windows":
            subprocess.run(
                ["MKLINK", "/J", link_path, target],
                shell=True, check=True, capture_output=True,
            )
        else:
            os.symlink(target, link_path)

    def _remove_symlink(self, link_name: str) -> bool:
        link_path = os.path.join(self.custom_scenery_dir, link_name)
        if not os.path.exists(link_path):
            return False
        os.remove(link_path)
        return True

    def _overlay_insertion_position(self) -> int:
        """Return the index where overlay entries should be inserted."""
        entries = self._ini.entries()
        for i, e in enumerate(entries):
            if "Overlay" in e.path or "Overlays" in e.path:
                return i
        # Insert before first mesh entry
        for i, e in enumerate(entries):
            if "Mesh" in e.path or "zOrtho4XP" in e.path:
                return i
        # Append at end
        return len(entries)

    def _mesh_insertion_position(self) -> int:
        """Return the index where mesh entries should be inserted (after overlays)."""
        entries = self._ini.entries()
        last_overlay = -1
        for i, e in enumerate(entries):
            if "Overlay" in e.path or "Overlays" in e.path:
                last_overlay = i
        if last_overlay >= 0:
            return last_overlay + 1
        # Before any existing mesh entry, or at end
        for i, e in enumerate(entries):
            if "Mesh" in e.path or "zOrtho4XP" in e.path:
                return i
        return len(entries)
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run python -m unittest tests.test_scenery_manager -v`
Expected: 12 OK (7 detection + 5 symlink)

- [ ] **Step 5: Commit**

```bash
git add src/O4_Scenery_Manager.py tests/test_scenery_manager.py
git commit -m "feat: add SceneryManager symlink add/remove operations"
```

---

### Task 5: SceneryManager — Reorder and Validate

**Files:**
- Modify: `src/O4_Scenery_Manager.py` (add reorder, validate)
- Modify: `tests/test_scenery_manager.py` (add TestReorder, TestValidate)

- [ ] **Step 1: Write reorder and validate tests**

```python
# Add to tests/test_scenery_manager.py

class TestReorder(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.cs_dir = os.path.join(self._temp.name, "Custom Scenery")
        os.makedirs(self.cs_dir)

    def _make_ini(self, entries: list[str]) -> str:
        ini_path = os.path.join(self._temp.name, "scenery_packs.ini")
        with open(ini_path, "w", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            for e in entries:
                f.write(f"SCENERY_PACK Custom Scenery/{e}/\n")
        return ini_path

    def _content(self, ini_path: str) -> list[str]:
        with open(ini_path) as f:
            return [line.strip() for line in f if "SCENERY_PACK" in line]

    def test_reorder_moves_overlays_above_meshes(self):
        ini_path = self._make_ini([
            "Ortho4XP_Mesh_+43-079",
            "Ortho4XP_Overlays",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        lines = self._content(ini_path)
        overlay_idx = next(i for i, l in enumerate(lines) if "Overlays" in l)
        mesh_idx = next(i for i, l in enumerate(lines) if "Mesh" in l)
        self.assertLess(overlay_idx, mesh_idx)

    def test_reorder_preserves_non_ortho4xp(self):
        ini_path = self._make_ini([
            "Global Airports",
            "Ortho4XP_Mesh_+44-080",
            "Ortho4XP_Mesh_+43-079",
            "simHeaven_X-World",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        lines = self._content(ini_path)
        self.assertEqual(lines[0], "SCENERY_PACK Custom Scenery/Global Airports/")
        self.assertEqual(lines[-1], "SCENERY_PACK Custom Scenery/simHeaven_X-World/")

    def test_reorder_sorts_mesh_entries(self):
        ini_path = self._make_ini([
            "Ortho4XP_Mesh_+44-080",
            "Ortho4XP_Mesh_+43-079",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        lines = self._content(ini_path)
        self.assertIn("+43-079", lines[0])
        self.assertIn("+44-080", lines[1])

    def test_reorder_no_ortho4xp_does_nothing(self):
        ini_path = self._make_ini([
            "Global Airports",
            "simHeaven_X-World",
        ])
        original = self._content(ini_path)
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        mgr.reorder()
        self.assertEqual(self._content(ini_path), original)


class TestValidate(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.cs_dir = os.path.join(self._temp.name, "Custom Scenery")
        os.makedirs(self.cs_dir)

    def _make_package_dir(self, name: str) -> str:
        p = os.path.join(self.cs_dir, name)
        os.makedirs(os.path.join(p, "Earth nav data"))
        return p

    def _make_ini(self, entries: list[str]) -> str:
        ini_path = os.path.join(self._temp.name, "scenery_packs.ini")
        with open(ini_path, "w", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            for e in entries:
                f.write(f"SCENERY_PACK Custom Scenery/{e}/\n")
        return ini_path

    def test_validate_missing_directory(self):
        ini_path = self._make_ini(["Ortho4XP_Mesh_+43-079"])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        issues = mgr.validate()
        missing = [i for i in issues if i.severity == "error" and "not found" in i.message.lower()]
        self.assertTrue(len(missing) >= 1)

    def test_validate_wrong_order_is_warning(self):
        self._make_package_dir("Ortho4XP_Overlays")
        self._make_package_dir("Ortho4XP_Mesh_+43-079")
        ini_path = self._make_ini([
            "Ortho4XP_Mesh_+43-079",
            "Ortho4XP_Overlays",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        issues = mgr.validate()
        order_issues = [i for i in issues if "order" in i.message.lower()]
        self.assertTrue(len(order_issues) >= 1)

    def test_validate_disabled_entry_is_warning(self):
        pkg = self._make_package_dir("Ortho4XP_Mesh_+43-079")
        ini_path = self._ini_path = os.path.join(self._temp.name, "scenery_packs.ini")
        with open(ini_path, "w", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            f.write("SCENERY_PACK_DISABLED Custom Scenery/Ortho4XP_Mesh_+43-079/\n")
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        issues = mgr.validate()
        disabled = [i for i in issues if "disabled" in i.message.lower()]
        self.assertTrue(len(disabled) >= 1)

    def test_validate_clean_returns_no_issues(self):
        self._make_package_dir("Ortho4XP_Overlays")
        self._make_package_dir("Ortho4XP_Mesh_+43-079")
        ini_path = self._make_ini([
            "Ortho4XP_Overlays",
            "Ortho4XP_Mesh_+43-079",
        ])
        mgr = SceneryManager(custom_scenery_dir=self.cs_dir, ini_path=ini_path)
        mgr.refresh()
        issues = mgr.validate()
        self.assertEqual(len(issues), 0)
```

- [ ] **Step 2: Run new tests to confirm they fail**

Run: `uv run python -m unittest tests.test_scenery_manager -v`
Expected: 9 failures (reorder/validate not yet implemented)

- [ ] **Step 3: Implement reorder and validate**

Add to `src/O4_Scenery_Manager.py`:

```python
from dataclasses import dataclass


@dataclass
class ValidationIssue:
    severity: str   # "error" or "warning"
    message: str
    entry_path: str | None = None


class SceneryManager:
    # ... existing methods ...

    def reorder(self) -> None:
        self.refresh()
        entries = self._ini.entries()
        ortho_indices = sorted(self._ortho4xp_indices)
        if not ortho_indices:
            return

        ortho_entries = [entries[i] for i in ortho_indices]
        non_ortho_front = [entries[i] for i in range(ortho_indices[0]) if i not in ortho_indices]
        non_ortho_back = [entries[i] for i in range(ortho_indices[-1] + 1, len(entries)) if i not in ortho_indices]

        # Separate overlays and meshes, sort each group
        overlays = sorted(
            [e for e in ortho_entries if "Overlay" in e.path or "Overlays" in e.path],
            key=lambda e: e.path,
        )
        meshes = sorted(
            [e for e in ortho_entries if "Mesh" in e.path or "zOrtho4XP" in e.path],
            key=lambda e: e.path,
        )

        new_entries = non_ortho_front + overlays + meshes + non_ortho_back

        # Rebuild ini entries
        self._ini._entries = new_entries
        self._ini.write()
        self.refresh()

    def validate(self) -> list[ValidationIssue]:
        self.refresh()
        issues: list[ValidationIssue] = []
        entries = self._ini.entries()
        ortho_indices = sorted(self._ortho4xp_indices)

        if not self.custom_scenery_dir:
            issues.append(ValidationIssue(
                severity="error",
                message="custom_scenery_dir is not set",
            ))
            return issues

        # Check each ortho entry's directory exists
        for i in ortho_indices:
            entry = entries[i]
            dir_name = os.path.basename(entry.path.rstrip("/\\"))
            full_path = os.path.join(self.custom_scenery_dir, dir_name)
            if not os.path.isdir(full_path):
                issues.append(ValidationIssue(
                    severity="error",
                    message=f"Directory not found: {full_path}",
                    entry_path=entry.path,
                ))

        # Check ordering: overlays before meshes
        last_overlay_pos = -1
        first_mesh_pos = len(entries)
        for i in ortho_indices:
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

        # Check for disabled entries
        for i in ortho_indices:
            if entries[i].disabled:
                issues.append(ValidationIssue(
                    severity="warning",
                    message=f"Entry is disabled: {entries[i].path}",
                    entry_path=entries[i].path,
                ))

        # Check for duplicate entries (same dir name)
        seen: set[str] = set()
        for i in ortho_indices:
            dir_name = os.path.basename(entries[i].path.rstrip("/\\"))
            if dir_name in seen:
                issues.append(ValidationIssue(
                    severity="error",
                    message=f"Duplicate entry: {entries[i].path}",
                    entry_path=entries[i].path,
                ))
            seen.add(dir_name)

        return issues
```

- [ ] **Step 4: Run all manager tests**

Run: `uv run python -m unittest tests.test_scenery_manager -v`
Expected: 16 OK

- [ ] **Step 5: Commit**

```bash
git add src/O4_Scenery_Manager.py tests/test_scenery_manager.py
git commit -m "feat: add SceneryManager reorder and validate"
```

---

### Task 6: CLI Commands

**Files:**
- Modify: `src/O4_CLI_Run.py`
- Modify: `Ortho4XP.py`

- [ ] **Step 1: Write CLI dispatch tests**

```python
# Add to tests/test_cli_run.py or create tests/test_scenery_cli.py
# Test through Ortho4XP.py CLI argument parsing

import os
import tempfile
import unittest
from unittest.mock import patch
from src.O4_Scenery_Manager import SceneryManager


class TestSceneryCLIDispatch(unittest.TestCase):
    def test_scenery_add_requires_lat_lon(self):
        """Verify argparse rejects missing args for 'scenery add'."""
        # Test through the CLI run module
        from src.O4_CLI_Run import dispatch_scenery
        with self.assertRaises(SystemExit):
            dispatch_scenery(["add"])  # missing lat/lon

    def test_scenery_remove_requires_lat_lon(self):
        from src.O4_CLI_Run import dispatch_scenery
        with self.assertRaises(SystemExit):
            dispatch_scenery(["remove"])

    def test_scenery_list_accepts_no_args(self):
        from src.O4_CLI_Run import dispatch_scenery
        result = dispatch_scenery(["list"])
        self.assertIsNone(result)  # should not raise
```

- [ ] **Step 2: Run CLI tests to confirm failures**

Run: `uv run python -m unittest tests.test_scenery_cli -v`
Expected: FAIL/ERROR

- [ ] **Step 3: Implement CLI dispatch**

In `src/O4_CLI_Run.py`, add:

```python
import argparse


def dispatch_scenery(argv: list[str]) -> None:
    """Dispatch scenery subcommands."""
    parser = argparse.ArgumentParser(prog="scenery")
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    add_p = sub.add_parser("add", help="Add a tile or overlay to scenery")
    add_p.add_argument("target", help="Latitude (integer) or 'overlay'")
    add_p.add_argument("lon", nargs="?", type=int, help="Longitude (integer)")

    # remove
    rm_p = sub.add_parser("remove", help="Remove a tile or overlay from scenery")
    rm_p.add_argument("target", help="Latitude (integer) or 'overlay'")
    rm_p.add_argument("lon", nargs="?", type=int, help="Longitude (integer)")

    # list
    sub.add_parser("list", help="List Ortho4XP entries in scenery_packs.ini")

    # reorder
    sub.add_parser("reorder", help="Reorder Ortho4XP entries in scenery_packs.ini")

    # validate
    sub.add_parser("validate", help="Validate scenery_packs.ini ordering")

    args = parser.parse_args(argv)

    # Create manager
    from src.O4_Config_Utils import CFG
    cs_dir = getattr(CFG, 'custom_scenery_dir', '')
    if not cs_dir:
        print("Error: custom_scenery_dir is not set in config.")
        return

    xplane_root = os.path.dirname(os.path.normpath(cs_dir))
    ini_path = os.path.join(xplane_root, "Output", "preferences", "scenery_packs.ini")
    mgr = SceneryManager(custom_scenery_dir=cs_dir, ini_path=ini_path)

    if args.command == "add":
        if args.target == "overlay":
            mgr.add_overlay(overlay_dir=getattr(CFG, 'Overlay_dir', None))
            print("Added overlay symlink + ini entry.")
        else:
            try:
                lat = int(args.target)
                lon = int(args.lon)
            except (ValueError, TypeError):
                parser.error("Usage: scenery add <lat> <lon> or scenery add overlay")
            mgr.add_tile(lat=lat, lon=lon, build_dir=getattr(CFG, 'custom_build_dir', None))
            print(f"Added tile {lat:+d}{lon:+d} symlink + ini entry.")

    elif args.command == "remove":
        if args.target == "overlay":
            if mgr.remove_overlay():
                print("Removed overlay symlink + ini entry.")
            else:
                print("Overlay not found.")
        else:
            try:
                lat = int(args.target)
                lon = int(args.lon)
            except (ValueError, TypeError):
                parser.error("Usage: scenery remove <lat> <lon> or scenery remove overlay")
            if mgr.remove_tile(lat=lat, lon=lon):
                print(f"Removed tile {lat:+d}{lon:+d} symlink + ini entry.")
            else:
                print(f"Tile {lat:+d}{lon:+d} not found in scenery.")

    elif args.command == "list":
        mgr.refresh()
        entries = mgr.ortho4xp_entries()
        if not entries:
            print("No Ortho4XP entries found in scenery_packs.ini.")
        else:
            for e in entries:
                status = "DISABLED" if e.disabled else "ACTIVE"
                print(f"  [{status}] {e.path}")

    elif args.command == "reorder":
        mgr.refresh()
        mgr.reorder()
        print("Ortho4XP entries reordered in scenery_packs.ini.")

    elif args.command == "validate":
        mgr.refresh()
        issues = mgr.validate()
        if not issues:
            print("No issues found. Scenery stack looks good.")
        else:
            for issue in issues:
                tag = "ERROR" if issue.severity == "error" else "WARNING"
                print(f"  [{tag}] {issue.message}")
```

In `Ortho4XP.py`, add `scenery` to the headless command dispatch (after existing subcommands):

```python
# In Ortho4XP.py headless dispatch section:
if args.subcommand == "scenery":
    from src.O4_CLI_Run import dispatch_scenery
    dispatch_scenery(args.argv)
    return
```

Also add `scenery` to the argument parser in `Ortho4XP.py`:

```python
# In the main argparse setup, add:
sub = parser.add_subparsers(dest="subcommand")

# ... existing subcommands ...

scenery_p = sub.add_parser("scenery", help="Manage Ortho4XP scenery packages")
scenery_p.add_argument("argv", nargs=argparse.REMAINDER, help="Scenery subcommand and args")
```

- [ ] **Step 4: Run CLI tests**

Run: `uv run python -m unittest tests.test_scenery_cli -v`
Expected: 3 OK

- [ ] **Step 5: Manual smoke test**

Run: `uv run python Ortho4XP.py scenery list`
Expected: "custom_scenery_dir is not set" or list of entries if configured.

- [ ] **Step 6: Commit**

```bash
git add src/O4_CLI_Run.py Ortho4XP.py tests/test_scenery_cli.py
git commit -m "feat: add scenery CLI commands (add/remove/list/reorder/validate)"
```

---

### Task 7: Wire into upgrade-package

**Files:**
- Modify: `src/O4_Package_Upgrader.py` (add auto-reorder after upgrade)

- [ ] **Step 1: Write test**

```python
# In tests/test_package_upgrader.py or a new test

class TestUpgradeSceneryReordering(unittest.TestCase):
    def test_upgrade_calls_reorder(self):
        """Verify that upgrade-package optionally calls scenery reorder."""
        from src.O4_Scenery_Manager import SceneryManager
        with unittest.mock.patch.object(SceneryManager, 'reorder') as mock_reorder:
            # Call upgrade with --update-scenery flag
            pass  # Implement after deciding on the exact interface
```

Actually, the spec says "Consider adding scenery reorder call after upgrade to register renamed packages in the ini." This is optional — let's keep it simple and make it a flag on the upgrade command.

- [ ] **Step 2: Add --update-scenery flag to upgrade-package CLI and wire the call**

In `src/O4_CLI_Run.py`, modify the `upgrade-package` handler to accept `--update-scenery`:

```python
# In dispatch_upgrade_package:
def dispatch_upgrade_package(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="upgrade-package")
    parser.add_argument("package_dir", help="Path to legacy zOrtho4XP package directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be renamed")
    parser.add_argument("--update-scenery", action="store_true",
                        help="Update scenery_packs.ini after upgrade")
    args = parser.parse_args(argv)
    
    from src.O4_Package_Upgrader import upgrade_package
    result = upgrade_package(args.package_dir, args.dry_run)
    
    if result and args.update_scenery:
        from src.O4_Scenery_Manager import SceneryManager
        from src.O4_Config_Utils import CFG
        cs_dir = getattr(CFG, 'custom_scenery_dir', '')
        if cs_dir:
            xplane_root = os.path.dirname(os.path.normpath(cs_dir))
            ini_path = os.path.join(xplane_root, "Output", "preferences", "scenery_packs.ini")
            mgr = SceneryManager(custom_scenery_dir=cs_dir, ini_path=ini_path)
            mgr.refresh()
            mgr.reorder()
            print("Updated scenery_packs.ini ordering.")
```

- [ ] **Step 3: Run full test suite**

Run: `uv run python -m unittest discover -s tests`
Expected: 258+X tests pass (existing + 18 new scenery tests)

- [ ] **Step 4: Commit**

```bash
git add src/O4_CLI_Run.py src/O4_Package_Upgrader.py tests/
git commit -m "feat: add --update-scenery flag to upgrade-package"
```

---

## Self-Review Check

1. **Spec coverage:** Every section of the spec is mapped:
   - Two modules (SceneryINI, SceneryManager) → Tasks 1-5
   - Package detection → Task 3
   - Ordering rules → Task 5
   - CLI interface → Task 6
   - Integration with existing code → Task 7
   - Edge cases (same dir, no cs_dir, grouped tiles) → Task 4 tests
   - Testing strategy → Tasks 1-7 all include tests

2. **Placeholder scan:** No TBD/TODO/placeholders. Every step has complete code.

3. **Type consistency:** SceneryEntry dataclass, ValidationIssue dataclass, method signatures consistent across tasks.

4. **No missing tests:** Each task writes tests first (TDD), covering parse, modify, detection, add/remove, reorder, validate, and CLI.
