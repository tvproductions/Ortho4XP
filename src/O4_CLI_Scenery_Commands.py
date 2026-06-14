from __future__ import annotations

import argparse

from O4_CLI_Scenery_Runtime import tile_args


def add_scenery_entry(args, parser: argparse.ArgumentParser, mgr) -> None:
    from O4_Config_Utils import CFG

    if args.target == "overlay":
        mgr.add_overlay(overlay_dir=getattr(CFG, "Overlay_dir", None))
        print("Added overlay symlink + ini entry.")
        return

    lat, lon = tile_args(args, parser)
    mgr.add_tile(lat=lat, lon=lon, build_dir=getattr(CFG, "custom_build_dir", None))
    print(f"Added tile {lat:+d}{lon:+d} symlink + ini entry.")


def remove_scenery_entry(args, parser: argparse.ArgumentParser, mgr) -> None:
    if args.target == "overlay":
        if mgr.remove_overlay():
            print("Removed overlay symlink + ini entry.")
        else:
            print("Overlay not found.")
        return

    lat, lon = tile_args(args, parser)
    if mgr.remove_tile(lat=lat, lon=lon):
        print(f"Removed tile {lat:+d}{lon:+d} symlink + ini entry.")
    else:
        print(f"Tile {lat:+d}{lon:+d} not found in scenery.")


def list_scenery_entries(_args, _parser: argparse.ArgumentParser, mgr) -> None:
    mgr.refresh()
    entries = mgr.ortho4xp_entries()
    if not entries:
        print("No Ortho4XP entries found in scenery_packs.ini.")
        return
    for e in entries:
        status = "DISABLED" if e.disabled else "ACTIVE"
        print(f"  [{status}] {e.path}")


def reorder_scenery_entries(_args, _parser: argparse.ArgumentParser, mgr) -> None:
    mgr.refresh()
    mgr.reorder()
    print("Ortho4XP entries reordered in scenery_packs.ini.")


def validate_scenery_entries(_args, _parser: argparse.ArgumentParser, mgr) -> None:
    mgr.refresh()
    issues = mgr.validate()
    if not issues:
        print("No issues found. Scenery stack looks good.")
        return
    for issue in issues:
        tag = "ERROR" if issue.severity == "error" else "WARNING"
        print(f"  [{tag}] {issue.message}")
