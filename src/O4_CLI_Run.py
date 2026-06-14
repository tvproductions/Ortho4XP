from __future__ import annotations

import argparse
import os
from typing import Callable, cast

import O4_Build_Models as MODELS
import O4_CLI_Jobs as JOBS


def dispatch_scenery(argv: list[str]) -> None:
    """Dispatch scenery subcommands."""
    parser = argparse.ArgumentParser(prog="scenery")
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Add a tile or overlay to scenery")
    add_p.add_argument("target", help="Latitude (integer) or 'overlay'")
    add_p.add_argument("lon", nargs="?", type=int, help="Longitude (integer)")

    rm_p = sub.add_parser("remove", help="Remove a tile or overlay from scenery")
    rm_p.add_argument("target", help="Latitude (integer) or 'overlay'")
    rm_p.add_argument("lon", nargs="?", type=int, help="Longitude (integer)")

    sub.add_parser("list", help="List Ortho4XP entries in scenery_packs.ini")
    sub.add_parser("reorder", help="Reorder Ortho4XP entries in scenery_packs.ini")
    sub.add_parser("validate", help="Validate scenery_packs.ini ordering")

    args = parser.parse_args(argv)

    from O4_Config_Utils import CFG
    from O4_Scenery_Manager import SceneryManager

    cs_dir = getattr(CFG, "custom_scenery_dir", "")
    if not cs_dir:
        print("Error: custom_scenery_dir is not set in config.")
        return

    xplane_root = os.path.dirname(os.path.normpath(cs_dir))
    ini_path = os.path.join(xplane_root, "Output", "preferences", "scenery_packs.ini")
    mgr = SceneryManager(custom_scenery_dir=cs_dir, ini_path=ini_path)

    if args.command == "add":
        if args.target == "overlay":
            mgr.add_overlay(overlay_dir=getattr(CFG, "Overlay_dir", None))
            print("Added overlay symlink + ini entry.")
        else:
            try:
                lat = int(args.target)
                lon = int(args.lon)
            except (ValueError, TypeError):
                parser.error("Usage: scenery add <lat> <lon> or scenery add overlay")
            mgr.add_tile(lat=lat, lon=lon, build_dir=getattr(CFG, "custom_build_dir", None))
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


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.command == "scenery":
        dispatch_scenery(args.argv)
        return 0

    if args.command == "validate-package":
        from O4_Package_Validator import validate_package
        result = validate_package(args.package_dir)
        if result["valid"]:
            print(f"Package validated: {args.package_dir}")
            return 0
        for err in result["errors"]:
            print(f"ERROR: {err}")
        return 1

    if args.command == "upgrade-package":
        from O4_Package_Upgrader import upgrade_package
        result = upgrade_package(args.package_dir, dry_run=args.dry_run)
        if result["upgraded"]:
            print(f"Would rename: {result['old_name']} -> {result['new_name']}")
            if not args.dry_run:
                print(f"Renamed: {result['old_name']} -> {result['new_name']}")
                if result["metadata_written"]:
                    print("package.json written")
            if args.update_scenery and not args.dry_run:
                from O4_Config_Utils import CFG
                from O4_Scenery_Manager import SceneryManager
                cs_dir = getattr(CFG, "custom_scenery_dir", "")
                if cs_dir:
                    xp_root = os.path.dirname(os.path.normpath(cs_dir))
                    ini_path = os.path.join(xp_root, "Output", "preferences", "scenery_packs.ini")
                    mgr = SceneryManager(custom_scenery_dir=cs_dir, ini_path=ini_path)
                    old_ini_path = os.path.join("Custom Scenery", result["old_name"])
                    mgr._ini.remove_entry(old_ini_path)
                    mgr._ini.write()
                    mgr.add_tile(lat=result["lat"], lon=result["lon"], build_dir=os.path.dirname(result["new_dir"]))
                    print("scenery_packs.ini updated.")
                else:
                    print("Warning: custom_scenery_dir not set; cannot update scenery_packs.ini")
        else:
            print(f"Not a legacy zOrtho4XP_ package: {args.package_dir}")
        return 0

    try:
        provider_keys, combined_provider_keys, provider_metadata = _provider_inventory()
        plan = JOBS.load_build_plan(
            args.job_file,
            provider_keys=provider_keys,
            combined_provider_keys=combined_provider_keys,
            provider_metadata=provider_metadata,
        )
    except JOBS.JobValidationError as exc:
        _print_validation_failure(exc.errors, json_output=args.json)
        return 2

    if args.command == "validate-job" or args.dry_run:
        _print_validation_success(plan, json_output=args.json)
        return 0

    try:
        result = _run_build(plan)
    except Exception as exc:
        _log_build_exception(exc)
        print(f"Build job failed: {exc}")
        return 1
    _print_build_result(result)
    return 0 if result.ok else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="Ortho4XP.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-job")
    validate.add_argument("job_file")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(dry_run=True)

    build = subparsers.add_parser("build-job")
    build.add_argument("job_file")
    build.add_argument("--dry-run", action="store_true")
    build.add_argument("--json", action="store_true")

    p_validate = subparsers.add_parser(
        "validate-package",
        help="Validate a generated scenery package's metadata and structure",
    )
    p_validate.add_argument(
        "package_dir", type=str,
        help="Path to the generated package directory",
    )

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
    p_upgrade.add_argument(
        "--update-scenery", "-u", action="store_true",
        help="Also update scenery_packs.ini after upgrade",
    )

    sp = subparsers.add_parser("scenery", help="Manage Ortho4XP scenery packages")
    sp.add_argument("argv", nargs=argparse.REMAINDER, help="Scenery subcommand and args")

    return parser


def _provider_inventory() -> tuple[set[str], set[str], dict[str, dict]]:
    import O4_Imagery_Utils as IMG

    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()
    return (
        set(IMG.providers_dict),
        set(IMG.combined_providers_dict),
        IMG.providers_dict,
    )


def _run_build(plan: MODELS.BuildPlan) -> MODELS.BuildBatchResult:
    import Ortho4XP
    import O4_Build_Core as CORE

    if not Ortho4XP.ensure_runtime_dirs():
        return MODELS.BuildBatchResult(False, (), "runtime directory setup failed")
    build_batch = cast(
        Callable[[MODELS.BuildPlan], MODELS.BuildBatchResult],
        getattr(CORE, "build_batch"),
    )
    return build_batch(plan)


def _log_build_exception(exc: Exception) -> None:
    import O4_UI_Utils as UI

    UI.log_exception(exc)


def _print_validation_success(plan: MODELS.BuildPlan, *, json_output: bool) -> None:
    if json_output:
        print(JOBS.validation_success_json(plan))
    else:
        print(JOBS.human_validation_summary(plan))


def _print_validation_failure(
    errors: tuple[JOBS.ValidationError, ...], *, json_output: bool
) -> None:
    if json_output:
        print(JOBS.validation_failure_json(errors))
    else:
        print(JOBS.human_validation_errors(errors))


def _print_build_result(result: MODELS.BuildBatchResult) -> None:
    if result.ok:
        print(f"Build job completed: {len(result.tiles)} tile(s)")
        return
    failed = next((tile for tile in result.tiles if not tile.ok), None)
    if failed:
        print(
            f"Build job failed at {failed.lat:+03d}{failed.lon:+04d} "
            f"step={failed.step}: {failed.message}"
        )
    elif result.message:
        print(f"Build job failed: {result.message}")
    else:
        print("Build job failed")
