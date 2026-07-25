"""Executable wrapper for the sister-project upstream watch."""

from __future__ import annotations

import sys
from pathlib import Path


def _main() -> int:
    if __package__ in {None, ""}:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.upstream_watch_core.cli import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_main())
