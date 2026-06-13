import json
import os
from datetime import datetime, timezone


PACKAGE_SCHEMA_VERSION = "1"
SUPPORTED_TYPES = {"mesh", "overlay", "library"}
TOOL_VERSION = "1.0.0"


def write_package_metadata(build_dir, tile, package_type="mesh"):
    if package_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported package type: {package_type}")

    name = os.path.basename(os.path.normpath(build_dir))

    metadata = {
        "name": name,
        "version": TOOL_VERSION,
        "author": "Ortho4XP",
        "description": f"Ortho4XP-generated {package_type} package",
        "type": package_type,
        "compatibility": {
            "min_xplane_version": "12.0.0",
        },
        "generation": {
            "tool": "Ortho4XP",
            "tool_version": TOOL_VERSION,
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

    os.makedirs(build_dir, exist_ok=True)
    filepath = os.path.join(build_dir, "package.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
