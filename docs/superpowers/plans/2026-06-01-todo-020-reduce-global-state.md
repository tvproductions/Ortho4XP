# TODO-020 Reduce Global Mutable State — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a `BuildContext` property facade over UI process-state globals and thread it as an explicit parameter through top-level build step functions.

**Architecture:** `BuildContext` lives in `src/O4_Build_Context.py`. Its properties delegate reads/writes to `O4_UI_Utils` module attributes, so the GUI stop button and existing sub-delegate readers stay consistent without sync calls. Build step functions accept `ctx` with a `None` default that constructs a `BuildContext` internally, allowing incremental caller migration. `build_tile_all` constructs the context and passes it explicitly. GUI handlers and `build_tile_list` follow.

**Tech Stack:** Python 3.13+, stdlib `unittest` only, no external dependencies.

---

### Task 1: Create BuildContext Class and Tests

**Files:**
- Create: `src/O4_Build_Context.py`
- Create: `tests/test_build_context.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_build_context.py`:

```python
import unittest
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Build_Context as BC
import O4_UI_Utils as UI


class BuildContextPropertyTests(unittest.TestCase):
    def test_red_flag_reads_ui_module(self):
        with mock.patch.object(UI, "red_flag", False):
            ctx = BC.BuildContext()
            self.assertFalse(ctx.red_flag)

    def test_red_flag_writes_through_to_ui(self):
        with mock.patch.object(UI, "red_flag", False):
            ctx = BC.BuildContext()
            ctx.red_flag = True
            self.assertTrue(UI.red_flag)

    def test_red_flag_reflects_external_ui_write(self):
        with mock.patch.object(UI, "red_flag", False):
            ctx = BC.BuildContext()
            UI.red_flag = True
            self.assertTrue(ctx.red_flag)

    def test_is_working_reads_ui_module(self):
        with mock.patch.object(UI, "is_working", False):
            ctx = BC.BuildContext()
            self.assertFalse(ctx.is_working)

    def test_is_working_writes_through_to_ui(self):
        with mock.patch.object(UI, "is_working", False):
            ctx = BC.BuildContext()
            ctx.is_working = True
            self.assertTrue(UI.is_working)

    def test_verbosity_reads_ui_module(self):
        with mock.patch.object(UI, "verbosity", 2):
            ctx = BC.BuildContext()
            self.assertEqual(ctx.verbosity, 2)

    def test_verbosity_writes_through_to_ui(self):
        with mock.patch.object(UI, "verbosity", 1):
            ctx = BC.BuildContext()
            ctx.verbosity = 3
            self.assertEqual(UI.verbosity, 3)

    def test_cleaning_level_reads_ui_module(self):
        with mock.patch.object(UI, "cleaning_level", 1):
            ctx = BC.BuildContext()
            self.assertEqual(ctx.cleaning_level, 1)

    def test_cleaning_level_writes_through_to_ui(self):
        with mock.patch.object(UI, "cleaning_level", 1):
            ctx = BC.BuildContext()
            ctx.cleaning_level = 2
            self.assertEqual(UI.cleaning_level, 2)

    def test_gui_reads_ui_module(self):
        with mock.patch.object(UI, "gui", None):
            ctx = BC.BuildContext()
            self.assertIsNone(ctx.gui)

    def test_gui_writes_through_to_ui(self):
        sentinel = object()
        with mock.patch.object(UI, "gui", None):
            ctx = BC.BuildContext()
            ctx.gui = sentinel
            self.assertIs(UI.gui, sentinel)


class BuildContextVprintTests(unittest.TestCase):
    def test_vprint_delegates_to_ui_vprint(self):
        ctx = BC.BuildContext()
        with mock.patch.object(UI, "vprint") as vprint:
            ctx.vprint(1, "hello", "world")
        vprint.assert_called_once_with(1, "hello", "world")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m unittest tests.test_build_context -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'O4_Build_Context'`

- [ ] **Step 3: Create BuildContext implementation**

Create `src/O4_Build_Context.py`:

```python
from typing import Any

import O4_UI_Utils as UI


class BuildContext:
    """Typed facade over UI process-state globals.

    Build steps receive this instead of reading UI.* directly.
    Properties delegate to the UI module for bidirectional consistency.
    """

    @property
    def red_flag(self) -> bool:
        return UI.red_flag

    @red_flag.setter
    def red_flag(self, value: bool) -> None:
        UI.red_flag = value

    @property
    def is_working(self) -> bool:
        return UI.is_working

    @is_working.setter
    def is_working(self, value: bool) -> None:
        UI.is_working = value

    @property
    def verbosity(self) -> int:
        return UI.verbosity

    @verbosity.setter
    def verbosity(self, value: int) -> None:
        UI.verbosity = value

    @property
    def cleaning_level(self) -> int:
        return UI.cleaning_level

    @cleaning_level.setter
    def cleaning_level(self, value: int) -> None:
        UI.cleaning_level = value

    @property
    def gui(self) -> Any | None:
        return UI.gui

    @gui.setter
    def gui(self, value: Any | None) -> None:
        UI.gui = value

    def vprint(self, min_verbosity: int, *args: Any) -> None:
        UI.vprint(min_verbosity, *args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest tests.test_build_context -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Run ruff and ty**

Run: `uv run ruff check src/O4_Build_Context.py tests/test_build_context.py && uv run ty check src/O4_Build_Context.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add src/O4_Build_Context.py tests/test_build_context.py
git commit -m "feat: add BuildContext property facade over UI process-state globals"
```

---

### Task 2: Add ctx Parameter to Build Step Functions and Migrate Internal Reads

**Files:**
- Modify: `src/O4_Vector_Map.py:21-157` (build_poly_file)
- Modify: `src/O4_Mesh_Utils.py:508-763` (build_mesh)
- Modify: `src/O4_Mask_Utils.py:70-239` (build_masks)
- Modify: `src/O4_Tile_Utils.py:176-332` (build_tile)

Each function gains `ctx=None` with a fallback that constructs `BuildContext()`. All direct reads of `UI.red_flag`, `UI.is_working`, and `UI.cleaning_level` within the function body become `ctx.*` reads. Sub-delegate functions called by these build steps are NOT changed — they continue reading `UI.*` directly.

- [ ] **Step 1: Migrate build_poly_file in O4_Vector_Map.py**

Add import at top of file (after existing imports):

```python
import O4_Build_Context as BC
```

Change signature and migrate reads within `build_poly_file` (lines 21-157):

```python
def build_poly_file(tile, ctx=None):
    if ctx is None:
        ctx = BC.BuildContext()
    if ctx.is_working:
        return 0
    ctx.is_working = True
    ctx.red_flag = False
```

Replace all `UI.is_working` and `UI.red_flag` reads within lines 21-157 with `ctx.is_working` and `ctx.red_flag`. The specific lines are:

| Line | Before | After |
|------|--------|-------|
| 22 | `if UI.is_working:` | `if ctx.is_working:` |
| 24 | `UI.is_working = 1  # ty:ignore[invalid-assignment]` | `ctx.is_working = True` |
| 25 | `UI.red_flag = 0  # ty:ignore[invalid-assignment]` | `ctx.red_flag = False` |
| 48 | `if UI.red_flag:` | `if ctx.red_flag:` |
| 56 | `if UI.red_flag:` | `if ctx.red_flag:` |
| 65 | `if UI.red_flag:` | `if ctx.red_flag:` |
| 73 | `if UI.red_flag:` | `if ctx.red_flag:` |
| 81 | `if UI.red_flag:` | `if ctx.red_flag:` |
| 119 | `if UI.red_flag:` | `if ctx.red_flag:` |
| 138 | `if UI.red_flag:` | `if ctx.red_flag:` |

Line 87 is a comment — skip it.

Do NOT change `UI.vprint`, `UI.logprint`, `UI.lvprint`, `UI.exit_message_and_bottom_line`, or any other function calls. Only the five properties in `BuildContext` are migrated.

- [ ] **Step 2: Migrate build_mesh in O4_Mesh_Utils.py**

Add import at top of file (after existing imports):

```python
import O4_Build_Context as BC
```

Change signature and migrate reads within `build_mesh` (lines 508-763):

```python
def build_mesh(tile, ctx=None):
    if ctx is None:
        ctx = BC.BuildContext()
    if ctx.is_working:
        return 0
    ctx.is_working = True
    ctx.red_flag = False
```

Replace all `UI.is_working`, `UI.red_flag`, and `UI.cleaning_level` reads within lines 508-763:

| Line | Before | After |
|------|--------|-------|
| 509 | `if UI.is_working:` | `if ctx.is_working:` |
| 511 | `UI.is_working = True` | `ctx.is_working = True` |
| 512 | `UI.red_flag = False` | `ctx.red_flag = False` |
| 598 | `UI.cleaning_level` | `ctx.cleaning_level` |
| 703 | `if UI.red_flag:` | `if ctx.red_flag:` |
| 709 | `if UI.red_flag:` | `if ctx.red_flag:` |
| 715 | `if UI.cleaning_level:` | `if ctx.cleaning_level:` |
| 728 | `if UI.cleaning_level > 2:` | `if ctx.cleaning_level > 2:` |

Do NOT change lines 353, 373, 425 — those are in `extract_mesh_to_obj`, a sub-delegate.

- [ ] **Step 3: Migrate build_masks in O4_Mask_Utils.py**

Add import at top of file (after existing imports):

```python
import O4_Build_Context as BC
```

Change signature and migrate reads within `build_masks` (lines 70-239). Note: `ctx` goes AFTER `for_imagery` to preserve the existing GUI call `args=[tile, for_imagery]` between tasks:

```python
def build_masks(tile, for_imagery=False, ctx=None):
    if ctx is None:
        ctx = BC.BuildContext()
    if ctx.is_working:
        return 0
    ctx.is_working = True
```

Replace all `UI.is_working` and `UI.red_flag` reads within lines 70-239:

| Line | Before | After |
|------|--------|-------|
| 72 | `if UI.is_working:` | `if ctx.is_working:` |
| 74 | `UI.is_working = True` | `ctx.is_working = True` |
| 81 | `UI.red_flag = False` | `ctx.red_flag = False` |

Do NOT change lines 484, 605 — those are in sub-delegate functions (`record_water_tris`, `blur_mask`).

- [ ] **Step 4: Migrate build_tile in O4_Tile_Utils.py**

Add import at top of file (after existing imports):

```python
import O4_Build_Context as BC
```

Change signature and migrate reads within `build_tile` (lines 176-332):

```python
def build_tile(tile, ctx=None):
    if ctx is None:
        ctx = BC.BuildContext()
    if ctx.is_working:
        return 0
    ctx.is_working = True
    ctx.red_flag = False
```

Replace all `UI.is_working`, `UI.red_flag`, and `UI.cleaning_level` reads within lines 176-332:

| Line | Before | After |
|------|--------|-------|
| 177 | `if UI.is_working:` | `if ctx.is_working:` |
| 179 | `UI.is_working = 1  # ty:ignore[invalid-assignment]` | `ctx.is_working = True` |
| 180 | `UI.red_flag = False` | `ctx.red_flag = False` |
| 219 | `if UI.cleaning_level > 1 and not tile.grouped:` | `if ctx.cleaning_level > 1 and not tile.grouped:` |
| 286 | `if UI.red_flag:` | `if ctx.red_flag:` |
| 300 | `if UI.red_flag:` | `if ctx.red_flag:` |
| 303 | `if UI.cleaning_level > 1:` | `if ctx.cleaning_level > 1:` |
| 316 | `if UI.cleaning_level > 2:` | `if ctx.cleaning_level > 2:` |
| 325 | `if UI.cleaning_level > 1 and not tile.grouped:` | `if ctx.cleaning_level > 1 and not tile.grouped:` |

Do NOT change lines 79, 103, 116, 127, 130, 143 — those are in `download_textures`, a sub-delegate.

- [ ] **Step 5: Run full test suite**

Run: `uv run python -m unittest discover -s tests -v`
Expected: All tests PASS (no callers pass ctx yet; defaults construct internally)

- [ ] **Step 6: Run ruff and ty on changed files**

Run: `uv run ruff check src/O4_Vector_Map.py src/O4_Mesh_Utils.py src/O4_Mask_Utils.py src/O4_Tile_Utils.py && uv run ty check src/O4_Vector_Map.py src/O4_Mesh_Utils.py src/O4_Mask_Utils.py src/O4_Tile_Utils.py`
Expected: No new errors

- [ ] **Step 7: Commit**

```bash
git add src/O4_Vector_Map.py src/O4_Mesh_Utils.py src/O4_Mask_Utils.py src/O4_Tile_Utils.py
git commit -m "refactor: add ctx parameter to build step functions, migrate process-state reads"
```

---

### Task 3: Thread ctx Through Build Core and Update Tests

**Files:**
- Modify: `src/O4_Build_Core.py:1-83`
- Modify: `tests/test_build_core.py`
- Modify: `tests/test_build_core_interrupts.py`
- Modify: `tests/test_build_context.py` (add pipeline integration test)

- [ ] **Step 1: Update test mock signatures in test_build_core.py**

The mock `side_effect` functions must accept `(tile, ctx)` since `build_tile_all` will now pass both.

Change `_record_step` — `ctx` must be keyword to match `build_step(tile, ctx=ctx)`:

```python
def _record_step(calls, name):
    def _inner(_tile, ctx=None):
        calls.append(name)
        return 1

    return _inner
```

- [ ] **Step 2: Update test mock signatures in test_build_core_interrupts.py**

Change `_step` — `ctx` must be keyword to match `build_step(tile, ctx=ctx)`:

```python
def _step(calls, name, interrupt_step):
    def _inner(_tile, ctx=None):
        calls.append(name)
        if name == interrupt_step:
            CORE.UI.red_flag = True
        return 1

    return _inner
```

Change the local `build_tile` function in `test_build_tile_all_stops_after_interrupted_retry`:

```python
        def build_tile(_tile, ctx=None):
            calls.append("tile")
            if len(calls) == 2:
                CORE.UI.red_flag = True
            return 1
```

- [ ] **Step 3: Update O4_Build_Core.py to construct and pass ctx**

Add import:

```python
import O4_Build_Context as BC
```

Rewrite `build_tile_all` to construct `ctx` and pass it through:

```python
def build_tile_all(tile) -> BuildResult:
    """Run the current all-in-one tile sequence and return its structured result."""
    ctx = BC.BuildContext()
    interrupted = _run_build_steps(tile, ctx)
    if interrupted:
        return interrupted

    interrupted = _retry_incomplete_textures_if_needed(tile, ctx)
    if interrupted:
        return interrupted

    ctx.is_working = False
    _report_remaining_incomplete_textures()
    return BuildResult(ok=True, step="all")


def _run_build_steps(tile, ctx) -> BuildResult | None:
    for step, build_step in _build_steps():
        build_step(tile, ctx=ctx)
        if ctx.red_flag:
            return _interrupted(step)
    return None


def _build_steps():
    return (
        ("vector", VMAP.build_poly_file),
        ("mesh", MESH.build_mesh),
        ("masks", MASK.build_masks),
        ("tile", TILE.build_tile),
    )


def _interrupted(step: str) -> BuildResult:
    UI.exit_message_and_bottom_line("")
    return BuildResult(False, step, "interrupted")


def _retry_incomplete_textures_if_needed(tile, ctx) -> BuildResult | None:
    tile_coords = FNAMES.short_latlon(tile.lat, tile.lon)
    if tile_coords not in IMG.incomplete_imgs:
        return None
    _retry_incomplete_textures(tile, ctx, tile_coords)
    if ctx.red_flag:
        return _interrupted("retry")
    return None


def _retry_incomplete_textures(tile, ctx, tile_coords: str) -> None:
    UI.lvprint(
        1,
        f"Attempting to rebuild textures with white squares: "
        f"{IMG.incomplete_texture_file_names(tile_coords)}",
    )
    TILE.delete_incomplete_imgs(tile)
    TILE.build_tile(tile, ctx)


def _report_remaining_incomplete_textures() -> None:
    if IMG.incomplete_imgs:
        UI.lvprint(
            0,
            f"\nERROR: Parts of the following images could not be obtained "
            f"and have been filled with white: "
            f"{IMG.incomplete_texture_file_names_by_tile()}",
        )
```

- [ ] **Step 4: Run existing build core tests**

Run: `uv run python -m unittest tests.test_build_core tests.test_build_core_interrupts tests.test_build_core_wrapper -v`
Expected: All tests PASS

- [ ] **Step 5: Add pipeline integration test to test_build_context.py**

Append to `tests/test_build_context.py`:

```python
class BuildContextPipelineTests(unittest.TestCase):
    def test_build_tile_all_constructs_and_passes_context(self):
        import O4_Build_Core as CORE
        from types import SimpleNamespace

        tile = SimpleNamespace(lat=12, lon=-123, build_dir="build")
        received_ctx = []

        def capture_ctx(_tile, ctx=None):
            received_ctx.append(ctx)
            return 1

        with (
            mock.patch.object(UI, "red_flag", False),
            mock.patch.object(UI, "is_working", False),
            mock.patch("O4_Build_Core.IMG.incomplete_imgs", {}),
            mock.patch.object(CORE.VMAP, "build_poly_file", side_effect=capture_ctx),
            mock.patch.object(CORE.MESH, "build_mesh", side_effect=capture_ctx),
            mock.patch.object(CORE.MASK, "build_masks", side_effect=capture_ctx),
            mock.patch.object(CORE.TILE, "build_tile", side_effect=capture_ctx),
            mock.patch.object(CORE.UI, "lvprint"),
            mock.patch.object(CORE.UI, "exit_message_and_bottom_line"),
        ):
            CORE.build_tile_all(tile)

        self.assertEqual(len(received_ctx), 4)
        for ctx in received_ctx:
            self.assertIsInstance(ctx, BC.BuildContext)
```

- [ ] **Step 6: Run all tests**

Run: `uv run python -m unittest discover -s tests -v`
Expected: All tests PASS

- [ ] **Step 7: Run ruff and ty**

Run: `uv run ruff check src/O4_Build_Core.py tests/test_build_context.py tests/test_build_core.py tests/test_build_core_interrupts.py && uv run ty check src/O4_Build_Core.py`
Expected: No new errors

- [ ] **Step 8: Commit**

```bash
git add src/O4_Build_Core.py tests/test_build_context.py tests/test_build_core.py tests/test_build_core_interrupts.py
git commit -m "refactor: thread BuildContext through build_tile_all pipeline"
```

---

### Task 4: Update GUI Handlers and build_tile_list to Pass ctx

**Files:**
- Modify: `src/O4_GUI_Utils.py:529-614`
- Modify: `src/O4_Tile_Utils.py:341-422` (build_tile_list)

- [ ] **Step 1: Update GUI button handlers in O4_GUI_Utils.py**

Add import at top of file (after existing imports):

```python
import O4_Build_Context as BC
```

Update each handler to construct `BuildContext` and pass it to the thread target.

`build_poly_file` (line 529):

```python
    def build_poly_file(self):
        try:
            tile = self.tile_from_interface()
            if tile:
                tile.make_dirs()  # ty:ignore[unresolved-attribute]
            else:
                return
        except Exception as e:
            UI.vprint(1, "Process aborted.\n")
            UI.log_exception(e)
            return 0
        ctx = BC.BuildContext()
        self.working_thread = threading.Thread(
            target=VMAP.build_poly_file, args=[tile, ctx]
        )
        self.working_thread.start()
```

`build_mesh` (line 543):

```python
    def build_mesh(self, event):
        try:
            tile = self.tile_from_interface()
            if tile:
                tile.make_dirs()  # ty:ignore[unresolved-attribute]
            else:
                return
        except Exception:
            UI.vprint(1, "Process aborted.\n")
            UI.log_exception("Exception on build_mesh")
            return 0
        ctx = BC.BuildContext()
        self.working_thread = threading.Thread(
            target=MESH.build_mesh, args=[tile, ctx]
        )
        self.working_thread.start()
```

`build_masks` (line 585):

```python
    def build_masks(self, event):
        for_imagery = "Shift" in str(event) or "shift" in str(event)
        try:
            tile = self.tile_from_interface()
            if tile:
                tile.make_dirs()  # ty:ignore[unresolved-attribute]
            else:
                return
        except Exception as e:
            UI.vprint(1, "Process aborted.\n")
            UI.log_exception(e)
            return 0
        ctx = BC.BuildContext()
        self.working_thread = threading.Thread(
            target=MASK.build_masks, args=[tile, for_imagery, ctx]
        )
        self.working_thread.start()
```

`build_tile` (line 602):

```python
    def build_tile(self):
        try:
            tile = self.tile_from_interface()
            if tile:
                tile.make_dirs()  # ty:ignore[unresolved-attribute]
            else:
                return
        except Exception as e:
            UI.vprint(1, "Process aborted.\n")
            UI.log_exception(e)
            return 0
        ctx = BC.BuildContext()
        self.working_thread = threading.Thread(
            target=TILE.build_tile, args=[tile, ctx]
        )
        self.working_thread.start()
```

- [ ] **Step 2: Update build_tile_list in O4_Tile_Utils.py**

`build_tile_list` (lines 341-422) constructs a `BuildContext` at the top and passes it to all build step calls. Migrate `UI.is_working`, `UI.red_flag`, and `UI.gui` reads within the function body.

```python
def build_tile_list(
    tile, list_lat_lon, do_osm, do_mesh, do_mask, do_dsf, do_ovl, override_cfg
):
    ctx = BC.BuildContext()
    if ctx.is_working:
        return 0
    ctx.red_flag = False
    timer = time.time()
    UI.lvprint(0, "Batch build launched for a number of", len(list_lat_lon), "tiles.")
    k = 0
    for lat, lon in list_lat_lon:
        k += 1
        UI.vprint(
            1,
            "Dealing with tile ",
            k,
            "/",
            len(list_lat_lon),
            ":",
            FNAMES.short_latlon(lat, lon),
        )
        (tile.lat, tile.lon) = (lat, lon)
        tile.build_dir = FNAMES.build_dir(tile.lat, tile.lon, tile.custom_build_dir)
        tile.dem = None
        if override_cfg:
            tile.read_from_config(use_global=True)
        else:
            tile.read_from_config()
        if do_osm or do_mesh or do_dsf:
            tile.make_dirs()
        if do_osm:
            VMAP.build_poly_file(tile, ctx)
            if ctx.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
        if do_mesh:
            MESH.build_mesh(tile, ctx)
            if ctx.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
        if do_mask:
            MASK.build_masks(tile, ctx=ctx)
            if ctx.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
        if do_dsf:
            tile_coords = FNAMES.short_latlon(lat, lon)
            build_tile(tile, ctx)
            if tile_coords in IMG.incomplete_imgs:
                UI.lvprint(
                    1,
                    f"Attempting to rebuild textures with white squares: "
                    f"{IMG.incomplete_texture_file_names(tile_coords)}",
                )
                delete_incomplete_imgs(tile)
                build_tile(tile, ctx)
            if ctx.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
        if do_ovl:
            OVL.build_overlay(lat, lon)
            if ctx.red_flag:
                UI.exit_message_and_bottom_line()
                return 0
        try:
            if ctx.gui:
                ctx.gui.earth_window.canvas.delete(  # ty:ignore[unresolved-attribute]
                    ctx.gui.earth_window.dico_tiles_todo[(lat, lon)]  # ty:ignore[unresolved-attribute]
                )
                ctx.gui.earth_window.dico_tiles_todo.pop((lat, lon), None)  # ty:ignore[unresolved-attribute]
        except (AttributeError, KeyError) as exc:
            UI.vprint(3, exc)
    UI.lvprint(0, "Batch process completed in", UI.nicer_timer(time.time() - timer))
    if IMG.incomplete_imgs:
        UI.lvprint(
            0,
            f"\nERROR: Parts of the following images could not be obtained "
            f"and have been filled with white: "
            f"{IMG.incomplete_texture_file_names_by_tile()}",
        )
    return 1
```

Note: The `UI.gui` reads at lines 405-408 become `ctx.gui`. The `UI.exit_message_and_bottom_line` calls stay as `UI.*` because that function is not a BuildContext property.

- [ ] **Step 3: Run full test suite**

Run: `uv run python -m unittest discover -s tests -v`
Expected: All tests PASS

- [ ] **Step 4: Run ruff and ty on changed files**

Run: `uv run ruff check src/O4_GUI_Utils.py src/O4_Tile_Utils.py && uv run ty check src/O4_GUI_Utils.py src/O4_Tile_Utils.py`
Expected: No new errors

- [ ] **Step 5: Run quality check**

Run: `uv run python .codex/skills/quality-check/scripts/quality_check.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/O4_GUI_Utils.py src/O4_Tile_Utils.py
git commit -m "refactor: pass BuildContext from GUI handlers and build_tile_list"
```
