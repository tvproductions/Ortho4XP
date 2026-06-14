from __future__ import annotations

import argparse
import os


def scenery_manager():
    from O4_Config_Utils import CFG
    from O4_Scenery_Manager import SceneryManager

    cs_dir = getattr(CFG, "custom_scenery_dir", "")
    if not cs_dir:
        print("Error: custom_scenery_dir is not set in config.")
        return None

    xplane_root = os.path.dirname(os.path.normpath(cs_dir))
    ini_path = os.path.join(xplane_root, "Output", "preferences", "scenery_packs.ini")
    return SceneryManager(custom_scenery_dir=cs_dir, ini_path=ini_path)


def tile_args(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> tuple[int, int]:
    try:
        return int(args.target), int(args.lon)
    except (ValueError, TypeError):
        parser.error(
            f"Usage: scenery {args.command} <lat> <lon> "
            f"or scenery {args.command} overlay"
        )
    raise AssertionError("parser.error exits")
