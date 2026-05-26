# Build Core Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested core all-in-one tile build API and route the CLI and existing GUI-facing wrapper through it.

**Architecture:** Create `src/O4_Build_Core.py` as the narrow orchestration boundary for the current Step 1, Step 2, Step 2.5, and Step 3 sequence. Keep `src/O4_Tile_Utils.py::build_all()` as an integer-return compatibility wrapper, and make `Ortho4XP.py` use the new structured result for command-line all-in-one builds.

**Tech Stack:** Python 3.13, standard-library `dataclasses`, `types.SimpleNamespace`, `unittest`, `unittest.mock`, existing `O4_UI_Utils`, Ruff, ty.

---

## File Structure

- Create `src/O4_Build_Core.py`
  - Owns `BuildResult`.
  - Owns `build_tile_all(tile)`.
  - Calls existing Step 1, Step 2, Step 2.5, and Step 3 functions.
  - Owns all-in-one red-flag checks and incomplete-imagery retry orchestration.
- Modify `src/O4_Tile_Utils.py`
  - Replace the current `build_all(tile)` body with a compatibility wrapper around `O4_Build_Core.build_tile_all(tile)`.
  - Keep `build_tile()`, `build_tile_list()`, and `delete_incomplete_imgs()` in this module.
  - Keep `O4_Vector_Map`, `O4_Mesh_Utils`, and `O4_Mask_Utils` imports because batch builds still use them.
- Modify `Ortho4XP.py`
  - Import `O4_Build_Core as CORE`.
  - Remove direct Step 1, Step 2, Step 2.5, and Step 3 imports from the launcher.
  - Replace direct build calls with `CORE.build_tile_all(tile)`.
- No code change in `src/O4_GUI_Utils.py`
  - The GUI "All in one" button already targets `TILE.build_all`.
  - After the wrapper change, that GUI path reaches the same core API without changing Tk behavior.
- Create `tests/test_build_core.py`
  - Tests core call order, red-flag stopping, incomplete-imagery retry behavior, remaining incomplete imagery reporting, and wrapper compatibility.
- Create `tests/test_launcher_core.py`
  - Runs `Ortho4XP.py` with fake imported modules to prove the CLI path calls the core API and does not call direct legacy step functions.
- Modify `TODO.md`
  - Mark work item 019 done only after implementation and verification.

---

### Task 1: Add Failing Core And Launcher Tests

**Files:**
- Create: `tests/test_build_core.py`
- Create: `tests/test_launcher_core.py`

- [ ] **Step 1: Create `tests/test_build_core.py`**

Create `tests/test_build_core.py` with this full content:

```python
import unittest
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Core as CORE
import O4_Tile_Utils as TILE


def _tile():
    return SimpleNamespace(lat=12, lon=-123, build_dir="build")


class BuildCoreAllInOneTests(unittest.TestCase):
    def test_build_tile_all_runs_steps_in_order_and_returns_success(self):
        tile = _tile()
        calls = []

        def record(name):
            def _inner(_tile):
                calls.append(name)
                return 1

            return _inner

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", {}),
            mock.patch.object(CORE.VMAP, "build_poly_file", side_effect=record("vector")),
            mock.patch.object(CORE.MESH, "build_mesh", side_effect=record("mesh")),
            mock.patch.object(CORE.MASK, "build_masks", side_effect=record("masks")),
            mock.patch.object(CORE.TILE, "build_tile", side_effect=record("tile")),
            mock.patch.object(CORE.UI, "lvprint") as lvprint,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(calls, ["vector", "mesh", "masks", "tile"])
        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        lvprint.assert_not_called()
        exit_line.assert_not_called()

    def test_build_tile_all_stops_after_vector_when_red_flag_is_set(self):
        tile = _tile()
        calls = []

        def vector(_tile):
            calls.append("vector")
            CORE.UI.red_flag = True
            return 1

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.VMAP, "build_poly_file", side_effect=vector),
            mock.patch.object(CORE.MESH, "build_mesh") as build_mesh,
            mock.patch.object(CORE.MASK, "build_masks") as build_masks,
            mock.patch.object(CORE.TILE, "build_tile") as build_tile,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(calls, ["vector"])
        self.assertEqual(result, CORE.BuildResult(False, "vector", "interrupted"))
        build_mesh.assert_not_called()
        build_masks.assert_not_called()
        build_tile.assert_not_called()
        exit_line.assert_called_once_with("")

    def test_build_tile_all_stops_after_mesh_when_red_flag_is_set(self):
        tile = _tile()
        calls = []

        def vector(_tile):
            calls.append("vector")
            return 1

        def mesh(_tile):
            calls.append("mesh")
            CORE.UI.red_flag = True
            return 1

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.VMAP, "build_poly_file", side_effect=vector),
            mock.patch.object(CORE.MESH, "build_mesh", side_effect=mesh),
            mock.patch.object(CORE.MASK, "build_masks") as build_masks,
            mock.patch.object(CORE.TILE, "build_tile") as build_tile,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line") as exit_line,
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(calls, ["vector", "mesh"])
        self.assertEqual(result, CORE.BuildResult(False, "mesh", "interrupted"))
        build_masks.assert_not_called()
        build_tile.assert_not_called()
        exit_line.assert_called_once_with("")

    def test_build_tile_all_retries_step_three_for_incomplete_imagery(self):
        tile = _tile()
        tile_coords = "+12-123"
        incomplete = {tile_coords: [{"file_name": "bad.jpg"}]}

        def clear_incomplete(_tile):
            incomplete.pop(tile_coords, None)

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", incomplete),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=1),
            mock.patch.object(CORE.MASK, "build_masks", return_value=1),
            mock.patch.object(CORE.TILE, "build_tile", return_value=1) as build_tile,
            mock.patch.object(
                CORE.TILE,
                "delete_incomplete_imgs",
                side_effect=clear_incomplete,
            ) as delete_incomplete,
            mock.patch.object(
                CORE.IMG,
                "incomplete_texture_file_names",
                return_value=["bad.jpg"],
            ),
            mock.patch.object(CORE.UI, "lvprint") as lvprint,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        self.assertEqual(build_tile.call_count, 2)
        delete_incomplete.assert_called_once_with(tile)
        lvprint.assert_any_call(
            1,
            "Attempting to rebuild textures with white squares: ['bad.jpg']",
        )

    def test_build_tile_all_reports_remaining_incomplete_imagery(self):
        tile = _tile()
        tile_coords = "+12-123"
        incomplete = {tile_coords: [{"file_name": "still_bad.jpg"}]}

        with (
            mock.patch.object(CORE.UI, "red_flag", False),
            mock.patch.object(CORE.IMG, "incomplete_imgs", incomplete),
            mock.patch.object(CORE.VMAP, "build_poly_file", return_value=1),
            mock.patch.object(CORE.MESH, "build_mesh", return_value=1),
            mock.patch.object(CORE.MASK, "build_masks", return_value=1),
            mock.patch.object(CORE.TILE, "build_tile", return_value=1),
            mock.patch.object(CORE.TILE, "delete_incomplete_imgs", return_value=None),
            mock.patch.object(
                CORE.IMG,
                "incomplete_texture_file_names",
                return_value=["still_bad.jpg"],
            ),
            mock.patch.object(
                CORE.IMG,
                "incomplete_texture_file_names_by_tile",
                return_value={tile_coords: ["still_bad.jpg"]},
            ),
            mock.patch.object(CORE.UI, "lvprint") as lvprint,
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
        ):
            result = CORE.build_tile_all(tile)

        self.assertEqual(result, CORE.BuildResult(ok=True, step="all"))
        lvprint.assert_any_call(
            0,
            "\nERROR: Parts of the following images could not be obtained "
            "and have been filled with white: "
            "{'+12-123': ['still_bad.jpg']}",
        )


class TileBuildAllWrapperTests(unittest.TestCase):
    def test_tile_utils_build_all_preserves_integer_success(self):
        with mock.patch.object(
            CORE,
            "build_tile_all",
            return_value=CORE.BuildResult(True, "all"),
        ) as build_tile_all:
            self.assertEqual(TILE.build_all(_tile()), 1)

        build_tile_all.assert_called_once()

    def test_tile_utils_build_all_preserves_integer_failure(self):
        with mock.patch.object(
            CORE,
            "build_tile_all",
            return_value=CORE.BuildResult(False, "mesh", "interrupted"),
        ) as build_tile_all:
            self.assertEqual(TILE.build_all(_tile()), 0)

        build_tile_all.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Create `tests/test_launcher_core.py`**

Create `tests/test_launcher_core.py` with this full content:

```python
import contextlib
import io
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


def _module(name):
    return types.ModuleType(name)


def _fake_file_names(temp_dir):
    module = _module("O4_File_Names")
    for name in (
        "Preview_dir",
        "Provider_dir",
        "Extent_dir",
        "Filter_dir",
        "OSM_dir",
        "Mask_dir",
        "Imagery_dir",
        "Elevation_dir",
        "Geotiff_dir",
        "Patch_dir",
        "Tile_dir",
        "Tmp_dir",
        "Utils_dir",
    ):
        setattr(module, name, str(Path(temp_dir, name)))
    Path(module.Utils_dir).mkdir()
    return module


def _fake_imagery():
    module = _module("O4_Imagery_Utils")
    module.initialize_extents_dict = mock.Mock()
    module.initialize_color_filters_dict = mock.Mock()
    module.initialize_providers_dict = mock.Mock()
    module.initialize_combined_providers_dict = mock.Mock()
    return module


def _fake_config():
    module = _module("O4_Config_Utils")

    class FakeTile:
        def __init__(self, lat, lon, custom_build_dir):
            self.lat = lat
            self.lon = lon
            self.custom_build_dir = custom_build_dir

    module.Tile = FakeTile
    return module


def _legacy_step_module(module_name, function_name):
    module = _module(module_name)
    setattr(
        module,
        function_name,
        mock.Mock(side_effect=AssertionError(f"{function_name} should not be called")),
    )
    return module


def _fake_modules(temp_dir, *, build_result):
    fake_pyproj = _module("pyproj")
    fake_pyproj.datadir = SimpleNamespace(set_data_dir=mock.Mock())

    fake_core = _module("O4_Build_Core")
    fake_core.build_tile_all = mock.Mock(return_value=build_result)

    return {
        "pyproj": fake_pyproj,
        "O4_File_Names": _fake_file_names(temp_dir),
        "O4_Imagery_Utils": _fake_imagery(),
        "O4_Build_Core": fake_core,
        "O4_GUI_Utils": _module("O4_GUI_Utils"),
        "O4_Config_Utils": _fake_config(),
        "O4_Vector_Map": _legacy_step_module("O4_Vector_Map", "build_poly_file"),
        "O4_Mesh_Utils": _legacy_step_module("O4_Mesh_Utils", "build_mesh"),
        "O4_Mask_Utils": _legacy_step_module("O4_Mask_Utils", "build_masks"),
        "O4_Tile_Utils": _legacy_step_module("O4_Tile_Utils", "build_tile"),
    }


class LauncherCoreTests(unittest.TestCase):
    def test_cli_all_in_one_uses_core_api(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            modules = _fake_modules(
                temp_dir,
                build_result=SimpleNamespace(ok=True, message=""),
            )
            with (
                mock.patch.dict(sys.modules, modules),
                mock.patch.object(
                    sys,
                    "argv",
                    ["Ortho4XP.py", "12", "-123", "BI", "16"],
                ),
                mock.patch.object(sys, "path", list(sys.path)),
                contextlib.redirect_stdout(stdout),
            ):
                runpy.run_path(str(_path.ROOT_DIR / "Ortho4XP.py"), run_name="__main__")

        core = modules["O4_Build_Core"]
        core.build_tile_all.assert_called_once()
        tile = core.build_tile_all.call_args[0][0]
        self.assertEqual(tile.lat, 12)
        self.assertEqual(tile.lon, -123)
        self.assertEqual(tile.custom_build_dir, "")
        self.assertEqual(tile.default_website, "BI")
        self.assertEqual(tile.default_zl, 16)
        self.assertIn("Bon vol!", stdout.getvalue())
        modules["O4_Vector_Map"].build_poly_file.assert_not_called()
        modules["O4_Mesh_Utils"].build_mesh.assert_not_called()
        modules["O4_Mask_Utils"].build_masks.assert_not_called()
        modules["O4_Tile_Utils"].build_tile.assert_not_called()

    def test_cli_all_in_one_failure_prints_crash_without_bon_vol(self):
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            modules = _fake_modules(
                temp_dir,
                build_result=SimpleNamespace(ok=False, message="interrupted"),
            )
            with (
                mock.patch.dict(sys.modules, modules),
                mock.patch.object(sys, "argv", ["Ortho4XP.py", "12", "-123"]),
                mock.patch.object(sys, "path", list(sys.path)),
                contextlib.redirect_stdout(stdout),
            ):
                runpy.run_path(str(_path.ROOT_DIR / "Ortho4XP.py"), run_name="__main__")

        output = stdout.getvalue()
        modules["O4_Build_Core"].build_tile_all.assert_called_once()
        self.assertIn("interrupted", output)
        self.assertIn("Crash!", output)
        self.assertNotIn("Bon vol!", output)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the new tests and verify they fail for the expected reasons**

Run:

```powershell
uv run python -m unittest tests.test_build_core tests.test_launcher_core -q
```

Expected result:

- `tests.test_build_core` errors with `ModuleNotFoundError: No module named 'O4_Build_Core'`.
- `tests.test_launcher_core.LauncherCoreTests.test_cli_all_in_one_uses_core_api` fails until `Ortho4XP.py` calls `O4_Build_Core.build_tile_all`.

Do not commit after this step. The failing tests are the TDD guard for the implementation tasks.

---

### Task 2: Implement The Core Build Boundary And Wrapper

**Files:**
- Create: `src/O4_Build_Core.py`
- Modify: `src/O4_Tile_Utils.py:333`
- Test: `tests/test_build_core.py`

- [ ] **Step 1: Create `src/O4_Build_Core.py`**

Create `src/O4_Build_Core.py` with this full content:

```python
from dataclasses import dataclass

import O4_File_Names as FNAMES
import O4_Imagery_Utils as IMG
import O4_Mask_Utils as MASK
import O4_Mesh_Utils as MESH
import O4_Tile_Utils as TILE
import O4_UI_Utils as UI
import O4_Vector_Map as VMAP


@dataclass(frozen=True)
class BuildResult:
    ok: bool
    step: str
    message: str = ""


def build_tile_all(tile) -> BuildResult:
    """Run the current all-in-one tile sequence and return its structured result."""
    VMAP.build_poly_file(tile)
    if UI.red_flag:
        return _interrupted("vector")

    MESH.build_mesh(tile)
    if UI.red_flag:
        return _interrupted("mesh")

    MASK.build_masks(tile)
    if UI.red_flag:
        return _interrupted("masks")

    TILE.build_tile(tile)
    if UI.red_flag:
        return _interrupted("tile")

    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    if tile_coords in IMG.incomplete_imgs:
        _retry_incomplete_textures(tile, tile_coords)
        if UI.red_flag:
            return _interrupted("retry")

    UI.is_working = 0  # ty:ignore[invalid-assignment]
    _report_remaining_incomplete_textures()
    return BuildResult(ok=True, step="all")


def _interrupted(step: str) -> BuildResult:
    UI.exit_message_and_bottom_line("")
    return BuildResult(False, step, "interrupted")


def _retry_incomplete_textures(tile, tile_coords: str) -> None:
    UI.lvprint(
        1,
        f"Attempting to rebuild textures with white squares: "
        f"{IMG.incomplete_texture_file_names(tile_coords)}",
    )
    TILE.delete_incomplete_imgs(tile)
    TILE.build_tile(tile)


def _report_remaining_incomplete_textures() -> None:
    if IMG.incomplete_imgs:
        UI.lvprint(
            0,
            f"\nERROR: Parts of the following images could not be obtained "
            f"and have been filled with white: "
            f"{IMG.incomplete_texture_file_names_by_tile()}",
        )
```

- [ ] **Step 2: Replace `O4_Tile_Utils.build_all()` with the compatibility wrapper**

In `src/O4_Tile_Utils.py`, replace the entire current `build_all(tile)` function with:

```python
################################################################################
def build_all(tile):
    import O4_Build_Core as CORE

    result = CORE.build_tile_all(tile)
    return 1 if result.ok else 0
```

Keep the surrounding `download_textures`, `build_tile`, `build_tile_list`, `remove_unwanted_textures`, and `delete_incomplete_imgs` functions unchanged.

- [ ] **Step 3: Run the core tests and verify they pass**

Run:

```powershell
uv run python -m unittest tests.test_build_core -q
```

Expected result: output includes `Ran 7 tests` and ends with `OK`.

- [ ] **Step 4: Run the existing Step 3 integration tests to catch wrapper regressions**

Run:

```powershell
uv run python -m unittest tests.test_tile_texture_conversion -q
```

Expected result: output includes `Ran 6 tests` and ends with `OK`.

- [ ] **Step 5: Commit the core API and wrapper**

Run:

```powershell
git add src\O4_Build_Core.py src\O4_Tile_Utils.py tests\test_build_core.py
git commit -m "refactor: add build core boundary"
```

---

### Task 3: Route The Launcher Through The Core API

**Files:**
- Modify: `Ortho4XP.py:30-36`
- Modify: `Ortho4XP.py:107-112`
- Test: `tests/test_launcher_core.py`
- Test: `tests/test_startup.py`

- [ ] **Step 1: Update launcher imports**

In `Ortho4XP.py`, replace this import block:

```python
import O4_Imagery_Utils as IMG
import O4_Vector_Map as VMAP
import O4_Mesh_Utils as MESH
import O4_Mask_Utils as MASK
import O4_Tile_Utils as TILE
import O4_GUI_Utils as GUI
import O4_Config_Utils as CFG  # CFG imported last because it can modify other modules variables
```

with:

```python
import O4_Imagery_Utils as IMG
import O4_Build_Core as CORE
import O4_GUI_Utils as GUI
import O4_Config_Utils as CFG  # CFG imported last because it can modify other modules variables
```

- [ ] **Step 2: Replace direct CLI build calls**

In `Ortho4XP.py`, replace this block:

```python
        try:
            VMAP.build_poly_file(tile)
            MESH.build_mesh(tile)
            MASK.build_masks(tile)
            TILE.build_tile(tile)
            print("Bon vol!")
        except Exception as e:
            print(e)
            print("Crash!")
```

with:

```python
        try:
            result = CORE.build_tile_all(tile)
            if result.ok:
                print("Bon vol!")
            else:
                if result.message:
                    print(result.message)
                print("Crash!")
        except Exception as e:
            print(e)
            print("Crash!")
```

- [ ] **Step 3: Run launcher and startup tests**

Run:

```powershell
uv run python -m unittest tests.test_launcher_core tests.test_startup -q
```

Expected result: output includes `Ran 7 tests` and ends with `OK`.

- [ ] **Step 4: Run focused core and launcher tests together**

Run:

```powershell
uv run python -m unittest tests.test_build_core tests.test_launcher_core tests.test_startup tests.test_tile_texture_conversion -q
```

Expected result: output includes `Ran 20 tests` and ends with `OK`.

The exact elapsed time may vary. The important observed facts are that all four modules run and the result is `OK`.

- [ ] **Step 5: Commit the launcher routing**

Run:

```powershell
git add Ortho4XP.py tests\test_launcher_core.py
git commit -m "refactor: route launcher builds through core"
```

---

### Task 4: Mark Work Item 019 Done And Verify Quality

**Files:**
- Modify: `TODO.md:490`
- Validate: `Ortho4XP.py`
- Validate: `src/O4_Build_Core.py`
- Validate: `src/O4_Tile_Utils.py`
- Validate: `tests/test_build_core.py`
- Validate: `tests/test_launcher_core.py`

- [ ] **Step 1: Update work item 019 in `TODO.md`**

In `TODO.md`, under `### TODO-019: Separate GUI, CLI, and Core Build Logic`, insert `Status: Done` after the title and add the completion paragraph shown below.

The resulting section should start like this:

```markdown
### TODO-019: Separate GUI, CLI, and Core Build Logic

Status: Done

GitHub Issue: #14

Begin separating presentation, command-line parsing, and build orchestration.

Completed by adding a tested `O4_Build_Core.build_tile_all()` orchestration
boundary for the current all-in-one tile sequence, preserving
`O4_Tile_Utils.build_all()` as a compatibility wrapper, and routing the
launcher's command-line all-in-one path through the same structured core API.
The GUI all-in-one button continues to target the compatibility wrapper, so GUI
and CLI all-in-one behavior now share the core build boundary.

Acceptance criteria:
```

Do not mark any later work item done.

- [ ] **Step 2: Run formatting checks for changed Python files**

Run:

```powershell
uv run ruff format --check Ortho4XP.py src\O4_Build_Core.py src\O4_Tile_Utils.py tests\test_build_core.py tests\test_launcher_core.py
```

Expected result:

```text
5 files already formatted
```

If Ruff reports formatting changes are needed, run:

```powershell
uv run ruff format Ortho4XP.py src\O4_Build_Core.py src\O4_Tile_Utils.py tests\test_build_core.py tests\test_launcher_core.py
```

Then rerun the `--check` command and proceed only after it passes.

- [ ] **Step 3: Run Ruff lint on the changed Python surface**

Run:

```powershell
uv run ruff check Ortho4XP.py src\O4_Build_Core.py src\O4_Tile_Utils.py tests\test_build_core.py tests\test_launcher_core.py
```

Expected result:

```text
All checks passed!
```

- [ ] **Step 4: Run ty on changed Python files**

Run:

```powershell
uv run ty check Ortho4XP.py src\O4_Build_Core.py src\O4_Tile_Utils.py tests\test_build_core.py tests\test_launcher_core.py
```

Expected result:

```text
All checks passed!
```

If ty reports warnings inherited from the legacy Tk or dynamic config surface, inspect them. Fix issues introduced by this change before proceeding.

- [ ] **Step 5: Run focused regression tests**

Run:

```powershell
uv run python -m unittest tests.test_build_core tests.test_launcher_core tests.test_startup tests.test_tile_texture_conversion -q
```

Expected result: output includes `Ran 20 tests` and ends with `OK`.

- [ ] **Step 6: Run the full unittest suite**

Run:

```powershell
uv run python -m unittest discover -s tests
```

Expected result:

```text
OK
```

The exact test count and elapsed time may vary. Record the observed test count in the final evidence.

- [ ] **Step 7: Run the repository quality check**

Run:

```powershell
uv run python .codex/skills/quality-check/scripts/quality_check.py
```

Expected result:

```text
Quality check passed
```

If this script prints a different success line, record the exact success line. If it finds unrelated defects, follow the repository directive: fix in-scope defects immediately, and make every remaining defect trackable before completion.

- [ ] **Step 8: Commit completion tracking**

Run:

```powershell
git add TODO.md
git commit -m "docs: mark build core task done"
```

- [ ] **Step 9: Add GitHub issue evidence and close issue #14**

Run:

```powershell
gh issue comment 14 --repo tvproductions/Ortho4XP --body "Implemented work item 019: separated the first all-in-one build orchestration boundary into O4_Build_Core.build_tile_all(), preserved O4_Tile_Utils.build_all() as a compatibility wrapper for GUI callers, and routed the launcher CLI path through the same core API. Evidence: focused build-core, launcher, startup, and Step 3 texture integration tests passed; full unittest discovery passed; Ruff format/check passed on changed files; ty passed on changed Python files; repository quality check passed."
gh issue close 14 --repo tvproductions/Ortho4XP --comment "Closing after implementation and verification of the build core boundary."
```

If the `gh issue comment` command is unavailable in the local approval rules, request approval for that command. The `gh issue close` prefix is already commonly used in this repository but still verify the command result.

- [ ] **Step 10: Final git status check**

Run:

```powershell
git status --short --branch
git log --oneline -3
```

Expected result:

- Working tree is clean.
- The last commits include:
  - `docs: mark build core task done`
  - `refactor: route launcher builds through core`
  - `refactor: add build core boundary`

---

## Plan Self-Review

- Spec coverage: Task 1 and Task 2 cover the callable core API, current all-in-one sequence, structured result, interruption behavior, incomplete-imagery retry, and legacy wrapper compatibility. Task 3 covers launcher routing through the core boundary. Task 4 covers tracking, issue evidence, and verification.
- Deferred-work scan: The plan uses no deferred implementation markers. The only queue references are concrete file and issue tracking names.
- Type consistency: The plan uses one result type, `BuildResult(ok: bool, step: str, message: str = "")`, consistently in tests, implementation, wrapper behavior, and launcher behavior.
