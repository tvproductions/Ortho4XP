"""Low-level JSON helpers for tile build cache metadata."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping
from contextlib import suppress
from hashlib import sha256
from typing import Any

# These helpers deliberately use JSON-compatible values only. That keeps
# hashes stable across process runs and makes tile_meta.json inspectable.


def read_json_dict(path: str) -> dict[str, object] | None:
    try:
        with open(path, encoding="utf-8") as f:
            metadata = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return metadata if isinstance(metadata, dict) else None


def write_json_atomically(
    path: str,
    file_name: str,
    metadata: Mapping[str, object],
) -> None:
    # Write beside the destination and replace it in one filesystem operation
    # so interrupted builds do not leave a half-written cache file.
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{file_name}.",
        suffix=".tmp",
        dir=os.path.dirname(path),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=True, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, path)
    except OSError:
        with suppress(OSError):
            os.unlink(tmp_path)
        raise


def hash_payload(payload: Mapping[str, object]) -> str:
    # Compact, sorted JSON is the canonical byte stream for the SHA256 key.
    data = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(data).hexdigest()


def json_stable_value(value: Any) -> object:
    # Config values are usually primitive JSON values, but zone lists and test
    # fixtures can contain tuples or dicts that need canonicalization.
    converter = _json_stable_converter(value)
    return converter(value)


def _json_stable_converter(value: Any) -> Callable[[Any], object]:
    if _is_json_scalar(value):
        return _identity
    if isinstance(value, Mapping):
        return json_stable_dict
    if isinstance(value, tuple | list):
        return json_stable_sequence
    return _stringify


def _is_json_scalar(value: Any) -> bool:
    return isinstance(value, bool | int | float | str) or value is None


def _identity(value: Any) -> object:
    return value


def _stringify(value: Any) -> str:
    return str(value)


def json_stable_dict(value: Mapping[Any, Any]) -> dict[str, object]:
    return {
        str(key): json_stable_value(value[key])
        for key in sorted(value, key=lambda item: str(item))
    }


def json_stable_sequence(value: tuple[Any, ...] | list[Any]) -> list[object]:
    return [json_stable_value(item) for item in value]
