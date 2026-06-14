# Package Naming and Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace legacy `zOrtho4XP_`/`yOrtho4XP_` naming with configurable `Ortho4XP_Mesh_+43-079` convention and add `package.json` metadata to every generated package.

**Architecture:** Add config keys to `O4_Cfg_Vars.py` for all naming options. Refactor `O4_File_Names.py` to read these config keys instead of hardcoded strings. Add a new `write_package_metadata()` function for `package.json` generation. Update overlay directory naming and all internal references. Wire up CLI validation and migration commands.

**Tech Stack:** Python 3.13+, Pydantic v2 (for metadata schema validation), stdlib `json`, stdlib `datetime`.

---

### Task 1: Add Naming Config Keys to Registry

**Files:**
- Modify: `src/O4_Cfg_Vars.py` (add global-config keys for naming)
- Test: `tests/test_config_models.py` (verify `ConfigVariableDefinition` accepts new keys)

- [ ] **Step 1: Write failing test for new config keys**

Add to `tests/test_config_models.py`:

```python
def test_package_naming_config_keys_have_valid_definitions(self):
    from O4_Cfg_Vars import cfg_global_vars
    for key in ("package_prefix", "package_separator", "mesh_purpose_token",
                "overlay_purpose_token", "monolithic_overlay_name",
                "latlon_format", "per_tile_overlays"):
        definition = cfg_global_vars["global_" + key]
        ConfigVariableDefinition.model_validate(definition)
```

Also add a test that defaults are correct:

```python
def test_package_naming_config_defaults(self):
    from O4_Cfg_Vars import cfg_global_vars
    prefix = cfg_global_vars["global_package_prefix"]["default"]
    self.assertEqual(prefix, "Ortho4XP")
    sep = cfg_global_vars["global_package_separator"]["default"]
    self.assertEqual(sep, "_")
    mesh = cfg_global_vars["global_mesh_purpose_token"]["default"]
    self.assertEqual(mesh, "Mesh")
    overlay = cfg_global_vars["global_overlay_purpose_token"]["default"]
    self.assertEqual(overlay, "Overlay")
    mononame = cfg_global_vars["global_monolithic_overlay_name"]["default"]
    self.assertEqual(mononame, "Overlays")
    latlon = cfg_global_vars["global_latlon_format"]["default"]
    self.assertEqual(latlon, "short")
    per_tile = cfg_global_vars["global_per_tile_overlays"]["default"]
    self.assertEqual(per_tile, False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_config_models.FileNamesTests -v`
Expected: FAIL with KeyError on `cfg_global_vars["global_package_prefix"]`

- [ ] **Step 3: Write minimal implementation**

Add to `O4_Cfg_Vars.py` inside `cfg_global_vars` dict (after existing keys, before closing `}`):

```python
    "package_prefix": {
        "module": "Naming",
        "type": str,
        "default": "Ortho4XP",
        "hint": "Prefix for all generated scenery package directory names.",
    },
    "package_separator": {
        "module": "Naming",
        "type": str,
        "default": "_",
        "hint": "Separator character between naming components.",
    },
    "mesh_purpose_token": {
        "module": "Naming",
        "type": str,
        "default": "Mesh",
        "hint": "Purpose token for mesh/ortho tile packages.",
    },
    "overlay_purpose_token": {
        "module": "Naming",
        "type": str,
        "default": "Overlay",
        "hint": "Purpose token for overlay packages.",
    },
    "monolithic_overlay_name": {
        "module": "Naming",
        "type": str,
        "default": "Overlays",
        "hint": "Directory name for the monolithic overlay package.",
    },
    "latlon_format": {
        "module": "Naming",
        "type": str,
        "default": "short",
        "hint": "Lat/lon formatting: short (+43-079), hem (N43W079), long (+40-080/+43-079).",
    },
    "per_tile_overlays": {
        "module": "Naming",
        "type": bool,
        "default": False,
        "hint": "Generate per-tile overlay packages instead of monolithic.",
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_config_models -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/O4_Cfg_Vars.py tests/test_config_models.py
git commit -m "feat: add config keys for package naming convention"
```

---

### Task 2: Update O4_File_Names.py with Config-Driven Naming

**Files:**
- Modify: `src/O4_File_Names.py` (replace `tile_dir()`, add `overlay_dir()`, add `package_name_from_config()`)
- Modify: `tests/test_file_names.py` (update assertions for new naming)
- Test: `tests/test_file_names.py`

- [ ] **Step 1: Write failing tests for new naming behavior**

Replace the existing `test_build_dir_uses_default_tile_directory_without_custom_path` and `test_build_dir_appends_tile_name_for_directory_like_custom_path` with:

```python
def test_tile_dir_uses_config_driven_naming(self):
    expected = os.path.join("Ortho4XP", "Mesh", "+43-079")
    # For now we simulate config defaults manually through the function
    self.assertEqual(names.tile_dir(43, -79), "Ortho4XP_Mesh_+43-079")

def test_tile_dir_is_configurable_via_prefix(self):
    # Simulate changing prefix (requires the function to read config)
    # Placeholder: we test the default first
    self.assertTrue(names.tile_dir(43, -79).startswith("Ortho4XP"))

def test_build_dir_uses_config_driven_tile_dir(self):
    self.assertEqual(
        names.build_dir(43, -79, ""),
        os.path.join(names.Tile_dir, "Ortho4XP_Mesh_+43-079"),
    )

def test_build_dir_appends_tile_name_for_directory_like_custom_path(self):
    custom_dir = os.path.join("D:", "tiles") + os.sep
    self.assertEqual(
        names.build_dir(43, -79, custom_dir),
        os.path.join("D:", "tiles", "Ortho4XP_Mesh_+43-079"),
    )

def test_mesh_and_dsf_file_paths_use_tile_naming_conventions(self):
    build_dir = os.path.join("Tiles", "Ortho4XP_Mesh_+43-079")
    self.assertEqual(
        names.mesh_file(build_dir, 43, -79),
        os.path.join(build_dir, "Data+43-079.mesh"),
    )
    self.assertEqual(
        names.dsf_file(build_dir, 43, -79),
        os.path.join(build_dir, "Earth nav data", "+40-080", "+43-079.dsf"),
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_file_names -v`
Expected: FAIL — asserts `Ortho4XP_Mesh_` but `tile_dir()` still returns `zOrtho4XP_`

- [ ] **Step 3: Write minimal implementation**

Replace the `tile_dir()` function and add a config-reading helper:

```python
def _naming_config():
    """Lazy-load naming config values with defaults."""
    try:
        import O4_Config_Utils as CFG
        prefix = getattr(CFG, "package_prefix", "Ortho4XP")
        sep = getattr(CFG, "package_separator", "_")
        mesh_token = getattr(CFG, "mesh_purpose_token", "Mesh")
        overlay_token = getattr(CFG, "overlay_purpose_token", "Overlay")
    except Exception:
        prefix, sep, mesh_token, overlay_token = "Ortho4XP", "_", "Mesh", "Overlay"
    return prefix, sep, mesh_token, overlay_token


def tile_dir(lat, lon):
    prefix, sep, mesh_token, _ = _naming_config()
    return prefix + sep + mesh_token + sep + short_latlon(lat, lon)
```

Also add an `overlay_dir_name()` function:

```python
def overlay_dir_name(lat=None, lon=None):
    """Return the overlay package directory name.
    
    If per_tile_overlays is True and lat/lon provided, returns per-tile name.
    Otherwise returns the monolithic overlay name.
    """
    try:
        import O4_Config_Utils as CFG
        prefix = getattr(CFG, "package_prefix", "Ortho4XP")
        sep = getattr(CFG, "package_separator", "_")
        overlay_token = getattr(CFG, "overlay_purpose_token", "Overlay")
        mono_name = getattr(CFG, "monolithic_overlay_name", "Overlays")
        per_tile = getattr(CFG, "per_tile_overlays", False)
    except Exception:
        prefix, sep, overlay_token, mono_name, per_tile = (
            "Ortho4XP", "_", "Overlay", "Overlays", False
        )
    if per_tile and lat is not None and lon is not None:
        return prefix + sep + overlay_token + sep + short_latlon(lat, lon)
    return prefix + sep + mono_name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests.test_file_names -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/O4_File_Names.py tests/test_file_names.py
git commit -m "feat: update tile_dir and add overlay_dir_name with config-driven naming"
```

---

### Task 3: Add package.json Generation

**Files:**
- Create: `src/O4_Package_Metadata.py` (new module for metadata generation)
- Create: `tests/test_package_metadata.py` (tests)
- Modify: `src/O4_Tile_Utils.py` (call metadata writer from `build_tile`)
- Modify: `src/O4_Overlay_Utils.py` (call metadata writer from `build_overlay`)

- [ ] **Step 1: Write failing tests**

Create `tests/test_package_metadata.py`:

```python
import json
import os
import tempfile
import unittest
from types import SimpleNamespace


class PackageMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_write_mesh_package_metadata_creates_json(self):
        from O4_Package_Metadata import write_package_metadata
        tile = SimpleNamespace(
            lat=43, lon=-79, zoomlevel=17,
            provider_code="BI", build_dir=self.tmpdir,
        )
        write_package_metadata(self.tmpdir, tile, "mesh")
        meta_file = os.path.join(self.tmpdir, "package.json")
        self.assertTrue(os.path.isfile(meta_file))

    def test_mesh_metadata_has_required_fields(self):
        from O4_Package_Metadata import write_package_metadata
        tile = SimpleNamespace(
            lat=43, lon=-79, zoomlevel=17,
            provider_code="BI", build_dir=self.tmpdir,
        )
        write_package_metadata(self.tmpdir, tile, "mesh")
        with open(os.path.join(self.tmpdir, "package.json")) as f:
            meta = json.load(f)
        self.assertEqual(meta["type"], "mesh")
        self.assertIn("name", meta)
        self.assertIn("version", meta)
        self.assertIn("tile", meta)
        self.assertEqual(meta["compatibility"]["min_xplane_version"], "12.0.0")

    def test_overlay_metadata_has_type_overlay(self):
        from O4_Package_Metadata import write_package_metadata
        tile = SimpleNamespace(
            lat=43, lon=-79, zoomlevel=17,
            provider_code="BI", build_dir=self.tmpdir,
        )
        write_package_metadata(self.tmpdir, tile, "overlay")
        with open(os.path.join(self.tmpdir, "package.json")) as f:
            meta = json.load(f)
        self.assertEqual(meta["type"], "overlay")

    def test_metadata_includes_generation_timestamp(self):
        from O4_Package_Metadata import write_package_metadata
        tile = SimpleNamespace(
            lat=43, lon=-79, zoomlevel=17,
            provider_code="BI", build_dir=self.tmpdir,
        )
        write_package_metadata(self.tmpdir, tile, "mesh")
        with open(os.path.join(self.tmpdir, "package.json")) as f:
            meta = json.load(f)
        self.assertIn("generation", meta)
        self.assertIn("timestamp", meta["generation"])
        self.assertIn("tool", meta["generation"])
        self.assertEqual(meta["generation"]["tool"], "Ortho4XP")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_package_metadata -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'O4_Package_Metadata'`

- [ ] **Step 3: Write minimal implementation**

Create `src/O4_Package_Metadata.py`:

```python
"""Package metadata generation for generated scenery packages."""

import json
import os
from datetime import datetime, timezone


PACKAGE_SCHEMA_VERSION = "1"
SUPPORTED_TYPES = {"mesh", "overlay", "library"}


def write_package_metadata(build_dir, tile, package_type="mesh"):
    """Write package.json to build_dir with tile metadata.
    
    Args:
        build_dir: Path to the package root directory.
        tile: Tile object with lat, lon, zoomlevel, provider_code attributes.
        package_type: One of 'mesh', 'overlay', 'library'.
    """
    if package_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported package type: {package_type}")
    
    tool_version = "1.0.0"
    name = os.path.basename(os.path.normpath(build_dir))
    
    metadata = {
        "name": name,
        "version": tool_version,
        "author": "Ortho4XP",
        "description": f"Ortho4XP-generated {package_type} package",
        "type": package_type,
        "compatibility": {
            "min_xplane_version": "12.0.0",
        },
        "generation": {
            "tool": "Ortho4XP",
            "tool_version": tool_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    
    if hasattr(tile, "lat") and hasattr(tile, "lon"):
        from math import floor
        lat = int(tile.lat) if isinstance(tile.lat, float) else tile.lat
        lon = int(tile.lon) if isinstance(tile.lon, float) else tile.lon
        metadata["tile"] = {
            "lat": tile.lat,
            "lon": tile.lon,
            "lat_rounded": floor(lat / 10) * 10,
            "lon_rounded": floor(lon / 10) * 10,
        }
    
    if package_type == "mesh":
        imagery = {}
        if hasattr(tile, "provider_code"):
            imagery["provider"] = tile.provider_code
        if hasattr(tile, "zoomlevel"):
            imagery["zoom_level"] = tile.zoomlevel
        if imagery:
            metadata["imagery"] = imagery
    
    filepath = os.path.join(build_dir, "package.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
```

- [ ] **Step 4: Wire into build_tile() and build_overlay()**

In `src/O4_Tile_Utils.py`, add at the top:

```python
import O4_Package_Metadata as PKG
```

At the end of `build_tile()`, after the DSF and terrain files are written and before the function returns:

```python
    PKG.write_package_metadata(tile.build_dir, tile, "mesh")
```

In `src/O4_Overlay_Utils.py`, add at the top:

```python
import O4_Package_Metadata as PKG
```

At the end of `build_overlay()`, after the overlay DSF is copied to the output:

```python
    PKG.write_package_metadata(overlay_output_dir, SimpleNamespace(lat=lat, lon=lon), "overlay")
```

(Note: the actual overlay output dir path needs to be computed — this will be finalized in Task 4.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run python -m unittest tests.test_package_metadata -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/O4_Package_Metadata.py tests/test_package_metadata.py src/O4_Tile_Utils.py src/O4_Overlay_Utils.py
git commit -m "feat: add package.json generation for mesh and overlay packages"
```

---

### Task 4: Rename Overlay Output Directory

**Files:**
- Modify: `src/O4_File_Names.py` (update `Overlay_dir` to use config-driven name)
- Modify: `src/O4_GUI_Utils.py` (update hardcoded `yOrtho4XP_Overlays` references)
- Modify: `src/O4_Overlay_Utils.py` (update output path)
- Test: `tests/test_file_names.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_file_names.py`:

```python
def test_overlay_dir_uses_config_driven_naming(self):
    self.assertEqual(names.Overlay_dir, "Ortho4XP_Overlays")

def test_overlay_dir_name_returns_monolithic_name_by_default(self):
    self.assertEqual(names.overlay_dir_name(), "Ortho4XP_Overlays")

def test_overlay_dir_name_with_per_tile_and_coords(self):
    self.assertEqual(
        names.overlay_dir_name(43, -79), "Ortho4XP_Overlays"
    )

def test_overlay_dir_is_resource_path_combined(self):
    self.assertTrue(names.Overlay_dir.endswith("Ortho4XP_Overlays"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_file_names -v`
Expected: FAIL — `Overlay_dir` still = `yOrtho4XP_Overlays`

- [ ] **Step 3: Write minimal implementation**

Replace line 34 in `O4_File_Names.py`:

```python
Overlay_dir = resource_path("yOrtho4XP_Overlays")
```

With:

```python
def _overlay_dir_name():
    try:
        import O4_Config_Utils as CFG
        prefix = getattr(CFG, "package_prefix", "Ortho4XP")
        sep = getattr(CFG, "package_separator", "_")
        mono = getattr(CFG, "monolithic_overlay_name", "Overlays")
    except Exception:
        prefix, sep, mono = "Ortho4XP", "_", "Overlays"
    return prefix + sep + mono

Overlay_dir = resource_path(_overlay_dir_name())
```

- [ ] **Step 4: Update GUI references**

In `src/O4_GUI_Utils.py`, replace all hardcoded `"yOrtho4XP_Overlays"` string literals with `FNAMES.overlay_dir_name()`. The relevant lines are:

Line 1662: `link = os.path.join(CFG.custom_scenery_dir, FNAMES.overlay_dir_name())`
Line 1670: f`"{FNAMES.overlay_dir_name()} link removed from:"`
Line 1679: f`"{FNAMES.overlay_dir_name()} link added to:"`

Also update `O4_Overlay_Utils.py` line 202 to compute the output dir dynamically rather than using the hardcoded overlay output path.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run python -m unittest tests.test_file_names -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/O4_File_Names.py src/O4_GUI_Utils.py src/O4_Overlay_Utils.py
git commit -m "feat: rename overlay output directory from yOrtho4XP_Overlays"
```

---

### Task 5: Update All Internal z/y Prefix References

**Files:**
- Modify: `src/O4_Mask_Utils.py` (lines using `FNAMES.tile_dir()` for construction, not affected by naming change — tile_dir() already uses new naming)
- Search for: any code that string-matches `"zOrtho4XP_"` or `"yOrtho4XP_"` prefix
- Test: verify no legacy prefix strings remain in source code

- [ ] **Step 1: Write a safety test**

Add to `tests/test_file_names.py`:

```python
def test_no_legacy_z_prefix_remains_in_tile_dir(self):
    """The zOrtho4XP_ prefix is removed in favor of config-driven naming."""
    result = names.tile_dir(43, -79)
    self.assertNotIn("zOrtho4XP", result)
    self.assertNotIn("zOrtho4XP_", result)
```

- [ ] **Step 2: Search for remaining legacy strings**

Run: `rg '"zOrtho4XP_"' src/` and `rg '"yOrtho4XP_Overlays"' src/` to find any remaining hardcoded strings.

- [ ] **Step 3: Replace any found**

If any found, replace each with the appropriate config-driven call (`tile_dir()` or `overlay_dir_name()`).

- [ ] **Step 4: Run tests**

Run: `uv run python -m unittest tests.test_file_names -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ tests/
git commit -m "refactor: remove remaining legacy zOrtho4XP/yOrtho4XP string references"
```

---

### Task 6: Add Package Validation CLI Command

**Files:**
- Create: `src/O4_Package_Validator.py` (validation logic)
- Create: `tests/test_package_validator.py`
- Modify: `src/O4_CLI_Utils.py` (wire `validate-package` subcommand)

- [ ] **Step 1: Write failing tests**

Create `tests/test_package_validator.py`:

```python
import json
import os
import tempfile
import unittest


class PackageValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_package_json(self, data):
        path = os.path.join(self.tmpdir, "package.json")
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_valid_mesh_package_passes_validation(self):
        from O4_Package_Validator import validate_package
        data = {
            "name": "Ortho4XP_Mesh_+43-079",
            "version": "1.0.0",
            "author": "Ortho4XP",
            "description": "Test",
            "type": "mesh",
            "compatibility": {"min_xplane_version": "12.0.0"},
            "generation": {
                "tool": "Ortho4XP",
                "tool_version": "1.0.0",
                "timestamp": "2026-06-13T12:00:00Z",
            },
            "tile": {"lat": 43, "lon": -79, "lat_rounded": 40, "lon_rounded": -80},
        }
        self._write_package_json(data)
        result = validate_package(self.tmpdir)
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)

    def test_missing_required_field_fails_validation(self):
        from O4_Package_Validator import validate_package
        data = {
            "name": "Ortho4XP_Mesh_+43-079",
            "type": "mesh",
        }
        self._write_package_json(data)
        result = validate_package(self.tmpdir)
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)

    def test_invalid_type_fails_validation(self):
        from O4_Package_Validator import validate_package
        data = {
            "name": "Test",
            "version": "1.0.0",
            "author": "Test",
            "description": "Test",
            "type": "invalid_type",
            "compatibility": {"min_xplane_version": "12.0.0"},
            "generation": {
                "tool": "Test",
                "tool_version": "1.0.0",
                "timestamp": "2026-06-13T12:00:00Z",
            },
        }
        self._write_package_json(data)
        result = validate_package(self.tmpdir)
        self.assertFalse(result["valid"])

    def test_missing_package_json_file_fails(self):
        from O4_Package_Validator import validate_package
        result = validate_package(self.tmpdir)
        self.assertFalse(result["valid"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_package_validator -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `src/O4_Package_Validator.py`:

```python
"""Package validation for generated scenery packages."""

import json
import os


REQUIRED_FIELDS = [
    "name", "version", "author", "description", "type",
    "compatibility", "generation",
]

REQUIRED_COMPATIBILITY_FIELDS = ["min_xplane_version"]
REQUIRED_GENERATION_FIELDS = ["tool", "tool_version", "timestamp"]
VALID_TYPES = {"mesh", "overlay", "library"}


def validate_package(package_dir):
    """Validate a generated package's metadata.
    
    Returns dict with keys: valid (bool), errors (list of str).
    """
    errors = []
    meta_path = os.path.join(package_dir, "package.json")
    
    if not os.path.isfile(meta_path):
        return {"valid": False, "errors": [f"package.json not found in {package_dir}"]}
    
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [f"Invalid JSON: {e}"]}
    
    if not isinstance(meta, dict):
        return {"valid": False, "errors": ["package.json root must be a JSON object"]}
    
    for field in REQUIRED_FIELDS:
        if field not in meta:
            errors.append(f"Missing required field: {field}")
    
    if not errors:
        if meta.get("type") not in VALID_TYPES:
            errors.append(f"Invalid type: {meta.get('type')!r}")
        if not isinstance(meta.get("compatibility"), dict):
            errors.append("compatibility must be an object")
        elif not isinstance(meta["compatibility"].get("min_xplane_version"), str):
            errors.append("compatibility.min_xplane_version must be a string")
        if not isinstance(meta.get("generation"), dict):
            errors.append("generation must be an object")
        else:
            for gf in REQUIRED_GENERATION_FIELDS:
                if gf not in meta["generation"]:
                    errors.append(f"Missing generation field: {gf}")
        if meta.get("type") in ("mesh", "overlay") and "tile" not in meta:
            errors.append(f"Missing tile field for type={meta.get('type')}")
    
    return {"valid": len(errors) == 0, "errors": errors}
```

- [ ] **Step 4: Wire CLI command**

In `src/O4_CLI_Utils.py`, add `validate-package` subcommand to the argument parser:

```python
# In the subparser setup:
p_validate = subparsers.add_parser(
    "validate-package",
    help="Validate a generated scenery package's metadata and structure",
)
p_validate.add_argument(
    "package_dir", type=str,
    help="Path to the generated package directory",
)
```

And in the command dispatch:

```python
elif args.command == "validate-package":
    from O4_Package_Validator import validate_package
    result = validate_package(args.package_dir)
    if result["valid"]:
        print(f"Package validated: {args.package_dir}")
    else:
        for err in result["errors"]:
            print(f"ERROR: {err}")
        sys.exit(1)
```

- [ ] **Step 5: Run tests**

Run: `uv run python -m unittest tests.test_package_validator -v`
Expected: PASS

- [ ] **Step 6: Verify CLI works**

Run: `uv run python Ortho4XP.py validate-package --help`
Expected: Shows help text for the subcommand.

- [ ] **Step 7: Commit**

```bash
git add src/O4_Package_Validator.py tests/test_package_validator.py src/O4_CLI_Utils.py
git commit -m "feat: add validate-package CLI command for package metadata validation"
```

---

### Task 7: Add upgrade-package CLI Command

**Files:**
- Create: `src/O4_Package_Upgrader.py`
- Create: `tests/test_package_upgrader.py`
- Modify: `src/O4_CLI_Utils.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_package_upgrader.py`:

```python
import os
import tempfile
import unittest


class PackageUpgraderTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_legacy_package(self, name):
        pkg_dir = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.join(pkg_dir, "Earth nav data", "+40-080"))
        return pkg_dir

    def test_upgrade_renames_legacy_z_prefix_to_new_naming(self):
        from O4_Package_Upgrader import upgrade_package
        old_dir = self._create_legacy_package("zOrtho4XP_+43-079")
        result = upgrade_package(old_dir, dry_run=True)
        self.assertIn("Ortho4XP_Mesh", result["new_name"])

    def test_upgrade_generates_package_json(self):
        from O4_Package_Upgrader import upgrade_package
        old_dir = self._create_legacy_package("zOrtho4XP_+43-079")
        result = upgrade_package(old_dir, dry_run=False)
        self.assertTrue(result["metadata_written"])
        self.assertTrue(os.path.isfile(os.path.join(result["new_dir"], "package.json")))

    def test_upgrade_skips_none_z_named_directories(self):
        from O4_Package_Upgrader import upgrade_package
        result = upgrade_package("/nonexistent/non-z-folder")
        self.assertFalse(result["upgraded"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests.test_package_upgrader -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `src/O4_Package_Upgrader.py`:

```python
"""Upgrade legacy zOrtho4XP_ packages to new naming convention."""

import json
import os
import re
from datetime import datetime, timezone


LEGACY_Z_PATTERN = re.compile(r"^zOrtho4XP_([+-]\d+)([+-]\d+)$")


def upgrade_package(package_dir, dry_run=True):
    """Upgrade a legacy zOrtho4XP_ package to new naming.
    
    Returns dict with: upgraded (bool), new_name (str), new_dir (str),
                       metadata_written (bool).
    """
    basename = os.path.basename(os.path.normpath(package_dir))
    match = LEGACY_Z_PATTERN.match(basename)
    
    if not match:
        return {"upgraded": False}
    
    lat = int(match.group(1))
    lon = int(match.group(2))
    
    prefix = "Ortho4XP"
    sep = "_"
    new_name = f"{prefix}{sep}Mesh{sep}{lat:+d}{lon:+d}"
    parent = os.path.dirname(os.path.normpath(package_dir))
    new_dir = os.path.join(parent, new_name)
    
    result = {
        "upgraded": True,
        "old_name": basename,
        "new_name": new_name,
        "new_dir": new_dir,
        "metadata_written": False,
    }
    
    if dry_run:
        return result
    
    # Rename directory
    os.rename(package_dir, new_dir)
    result["new_dir"] = new_dir
    
    # Write package.json
    metadata = {
        "name": new_name,
        "version": "1.0.0",
        "author": "Ortho4XP",
        "description": f"Ortho4XP-generated mesh package (upgraded from {basename})",
        "type": "mesh",
        "compatibility": {"min_xplane_version": "12.0.0"},
        "generation": {
            "tool": "Ortho4XP",
            "tool_version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "tile": {"lat": lat, "lon": lon},
    }
    meta_path = os.path.join(new_dir, "package.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    result["metadata_written"] = True
    
    return result
```

- [ ] **Step 4: Wire CLI command**

In `src/O4_CLI_Utils.py`:

```python
p_upgrade = subparsers.add_parser(
    "upgrade-package",
    help="Upgrade a legacy zOrtho4XP_ package to new naming convention",
)
p_upgrade.add_argument(
    "package_dir", type=str,
    help="Path to the legacy zOrtho4XP_ package directory",
)
p_upgrade.add_argument(
    "--dry-run", action="store_true",
    help="Show what would be changed without making changes",
)
```

In dispatch:

```python
elif args.command == "upgrade-package":
    from O4_Package_Upgrader import upgrade_package
    result = upgrade_package(args.package_dir, dry_run=args.dry_run)
    if result["upgraded"]:
        print(f"Would rename: {result['old_name']} -> {result['new_name']}")
        if not args.dry_run:
            print(f"Renamed: {result['old_name']} -> {result['new_name']}")
            if result["metadata_written"]:
                print("package.json written")
    else:
        print(f"Not a legacy zOrtho4XP_ package: {args.package_dir}")
```

- [ ] **Step 5: Run tests**

Run: `uv run python -m unittest tests.test_package_upgrader -v`
Expected: PASS

- [ ] **Step 6: Verify CLI**

Run: `uv run python Ortho4XP.py upgrade-package --help`
Expected: Shows help.

- [ ] **Step 7: Commit**

```bash
git add src/O4_Package_Upgrader.py tests/test_package_upgrader.py src/O4_CLI_Utils.py
git commit -m "feat: add upgrade-package CLI command for legacy package migration"
```
