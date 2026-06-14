from __future__ import annotations

import os


def validate_package_command(package_dir: str) -> int:
    from O4_Package_Validator import validate_package

    result = validate_package(package_dir)
    if result["valid"]:
        print(f"Package validated: {package_dir}")
        return 0
    for err in result["errors"]:
        print(f"ERROR: {err}")
    return 1


def upgrade_package_command(
    package_dir: str, *, dry_run: bool, update_scenery: bool
) -> int:
    from O4_Package_Upgrader import upgrade_package

    result = upgrade_package(package_dir, dry_run=dry_run)
    if not result["upgraded"]:
        print(f"Not a legacy zOrtho4XP_ package: {package_dir}")
        return 0

    print(f"Would rename: {result['old_name']} -> {result['new_name']}")
    if not dry_run:
        _print_package_upgrade_result(result)
    if update_scenery and not dry_run:
        _update_scenery_for_package_upgrade(result)
    return 0


def _print_package_upgrade_result(result: dict) -> None:
    print(f"Renamed: {result['old_name']} -> {result['new_name']}")
    if result["metadata_written"]:
        print("package.json written")


def _update_scenery_for_package_upgrade(result: dict) -> None:
    from O4_Config_Utils import CFG
    from O4_Scenery_Manager import SceneryManager

    cs_dir = getattr(CFG, "custom_scenery_dir", "")
    if not cs_dir:
        print("Warning: custom_scenery_dir not set; cannot update scenery_packs.ini")
        return

    xp_root = os.path.dirname(os.path.normpath(cs_dir))
    ini_path = os.path.join(xp_root, "Output", "preferences", "scenery_packs.ini")
    mgr = SceneryManager(custom_scenery_dir=cs_dir, ini_path=ini_path)
    old_ini_path = os.path.join("Custom Scenery", result["old_name"])
    mgr._ini.remove_entry(old_ini_path)
    mgr._ini.write()
    mgr.add_tile(
        lat=result["lat"],
        lon=result["lon"],
        build_dir=os.path.dirname(result["new_dir"]),
    )
    print("scenery_packs.ini updated.")
