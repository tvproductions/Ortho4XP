import json
import os
import re
from datetime import datetime, timezone


LEGACY_Z_PATTERN = re.compile(r"^zOrtho4XP_([+-]\d+)([+-]\d+)$")


def upgrade_package(package_dir, dry_run=True):
    basename = os.path.basename(os.path.normpath(package_dir))
    match = LEGACY_Z_PATTERN.match(basename)

    if not match:
        return {"upgraded": False}

    lat = int(match.group(1))
    lon = int(match.group(2))

    prefix = "Ortho4XP"
    sep = "_"
    strlat = f"{lat:+}".zfill(3)
    strlon = f"{lon:+}".zfill(4)
    new_name = f"{prefix}{sep}Mesh{sep}{strlat}{strlon}"
    parent = os.path.dirname(os.path.normpath(package_dir))
    new_dir = os.path.join(parent, new_name)

    result = {
        "upgraded": True,
        "old_name": basename,
        "new_name": new_name,
        "new_dir": new_dir,
        "lat": lat,
        "lon": lon,
        "metadata_written": False,
    }

    if dry_run:
        return result

    os.rename(package_dir, new_dir)
    result["new_dir"] = new_dir

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
