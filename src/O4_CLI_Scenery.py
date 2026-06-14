from __future__ import annotations

import argparse

from O4_CLI_Scenery_Commands import (
    add_scenery_entry,
    list_scenery_entries,
    remove_scenery_entry,
    reorder_scenery_entries,
    validate_scenery_entries,
)
from O4_CLI_Scenery_Runtime import scenery_manager


def dispatch_scenery(argv: list[str]) -> None:
    """Dispatch scenery subcommands."""
    parser = _scenery_parser()
    args = parser.parse_args(argv)
    mgr = scenery_manager()
    if mgr is None:
        return

    args.handler(args, parser, mgr)


def _scenery_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scenery")
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Add a tile or overlay to scenery")
    add_p.add_argument("target", help="Latitude (integer) or 'overlay'")
    add_p.add_argument("lon", nargs="?", type=int, help="Longitude (integer)")
    add_p.set_defaults(handler=add_scenery_entry)

    rm_p = sub.add_parser("remove", help="Remove a tile or overlay from scenery")
    rm_p.add_argument("target", help="Latitude (integer) or 'overlay'")
    rm_p.add_argument("lon", nargs="?", type=int, help="Longitude (integer)")
    rm_p.set_defaults(handler=remove_scenery_entry)

    list_p = sub.add_parser("list", help="List Ortho4XP entries in scenery_packs.ini")
    list_p.set_defaults(handler=list_scenery_entries)

    reorder_p = sub.add_parser(
        "reorder", help="Reorder Ortho4XP entries in scenery_packs.ini"
    )
    reorder_p.set_defaults(handler=reorder_scenery_entries)

    validate_p = sub.add_parser("validate", help="Validate scenery_packs.ini ordering")
    validate_p.set_defaults(handler=validate_scenery_entries)
    return parser
