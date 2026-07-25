from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from scripts.upstream_watch_core.models import (
    StateValidationError,
    WatchExit,
    canonical_json_bytes,
    load_state,
)
from tests._path import ROOT_DIR  # noqa: F401

BASE_SHA = "4ca0a8d404b078ad899979bafde84769a0fb235b"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class WatchStateTests(unittest.TestCase):
    def _state(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "author": {
                "repository": "Ypsos/ORTHO4XP_V3",
                "branch": "ORTHO4XP_V3",
            },
            "passive_fork": {
                "repository": "tvproductions/ORTHO4XP_V3",
                "branch": "ORTHO4XP_V3",
            },
            "baseline": {
                "reviewed_sha": BASE_SHA,
                "audit_id": "bootstrap-existing-baseline",
                "audit_date": "2026-06-16",
                "manifest_sha256": EMPTY_SHA256,
                "path_count": 0,
            },
        }

    def _load(self, payload: dict[str, object]):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "state.json")
            path.write_text(json.dumps(payload), encoding="utf-8")
            return load_state(path)

    def test_load_state_accepts_valid_schema(self) -> None:
        state = self._load(self._state())
        self.assertEqual(state.baseline.reviewed_sha, BASE_SHA)
        self.assertEqual(WatchExit.REVIEW_REQUIRED, 2)

    def test_canonical_json_is_order_independent(self) -> None:
        self.assertEqual(canonical_json_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}')

    def test_load_state_rejects_short_sha(self) -> None:
        payload = self._state()
        baseline = cast(dict[str, Any], payload["baseline"])
        baseline["reviewed_sha"] = "abc123"
        with self.assertRaisesRegex(StateValidationError, "lowercase 40-character SHA"):
            self._load(payload)

    def test_load_state_rejects_repository_url_or_credentials(self) -> None:
        for value in (
            "https://github.com/Ypsos/ORTHO4XP_V3",
            "token@github.com/Ypsos/ORTHO4XP_V3",
        ):
            with self.subTest(value=value):
                payload = self._state()
                author = cast(dict[str, Any], payload["author"])
                author["repository"] = value
                with self.assertRaisesRegex(StateValidationError, "owner/name"):
                    self._load(payload)

    def test_load_state_rejects_unknown_schema_version(self) -> None:
        payload = self._state()
        payload["schema_version"] = 2
        with self.assertRaisesRegex(StateValidationError, "schema_version"):
            self._load(payload)

    def test_load_state_rejects_unknown_fields(self) -> None:
        payload = self._state()
        payload["unexpected"] = True
        with self.assertRaisesRegex(StateValidationError, "unknown fields"):
            self._load(payload)

    def test_load_state_rejects_boolean_path_count(self) -> None:
        payload = self._state()
        baseline = cast(dict[str, Any], payload["baseline"])
        baseline["path_count"] = True
        with self.assertRaisesRegex(StateValidationError, "path_count"):
            self._load(payload)
