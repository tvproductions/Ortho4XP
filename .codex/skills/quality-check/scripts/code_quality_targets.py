from __future__ import annotations


def filter_changed_complexity_targets(
    changed: list[str], source_paths: list[str], required: str
) -> list[str]:
    allowed = set(source_paths)
    targets = [path for path in changed if path in allowed]
    if required not in targets:
        targets.append(required)
    return targets
