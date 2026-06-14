import json
import os

REQUIRED_FIELDS = [
    "name",
    "version",
    "author",
    "description",
    "type",
    "compatibility",
    "generation",
]

REQUIRED_GENERATION_FIELDS = ["tool", "tool_version", "timestamp"]
VALID_TYPES = {"mesh", "overlay", "library"}


def validate_package(package_dir):
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
