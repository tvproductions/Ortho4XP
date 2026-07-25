from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from scripts.upstream_watch_core.github_api import (
    HttpRequest,
    HttpResponse,
    WatchObservation,
    render_observation_body,
)
from scripts.upstream_watch_core.models import ForkState, WatchExit

BASE_SHA = "4ca0a8d404b078ad899979bafde84769a0fb235b"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def state_payload(reviewed_sha: str = BASE_SHA) -> dict[str, object]:
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
            "reviewed_sha": reviewed_sha,
            "audit_id": "bootstrap-existing-baseline",
            "audit_date": "2026-06-16",
            "manifest_sha256": EMPTY_SHA256,
            "path_count": 0,
        },
    }


def run_test_git(repo: Path, *args: str) -> str:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_DATE": "2026-07-19T12:00:00Z",
            "GIT_COMMITTER_DATE": "2026-07-19T12:00:00Z",
        }
    )
    result = subprocess.run(  # noqa: S603 - local test Git only.
        ["git", *args],  # noqa: S607 - PATH-resolved test dependency.
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    return result.stdout.strip()


def write_test_file(repo: Path, relative: str, content: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class FakeTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.requests: list[dict[str, object]] = []

    def request(self, request: HttpRequest) -> HttpResponse:
        safe_headers = dict(request.headers)
        if "Authorization" in safe_headers:
            safe_headers["Authorization"] = "Bearer ***"
        self.requests.append(
            {
                "method": request.method,
                "url": request.url,
                "headers": safe_headers,
                "body": request.body.decode("utf-8") if request.body else None,
            }
        )
        if not self.responses:
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")
        return self.responses.pop(0)


def json_response(
    status: int,
    payload: object,
    headers: dict[str, str] | None = None,
) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers=headers or {},
        body=json.dumps(payload).encode("utf-8"),
    )


def observation(
    *,
    status: WatchExit = WatchExit.REVIEW_REQUIRED,
    fork_state: ForkState = ForkState.BEHIND,
    author_head: str = "b" * 40,
) -> WatchObservation:
    return WatchObservation(
        status=status,
        author_repository="Ypsos/ORTHO4XP_V3",
        author_branch="ORTHO4XP_V3",
        baseline_sha="a" * 40,
        author_head=author_head,
        passive_repository="tvproductions/ORTHO4XP_V3",
        passive_branch="ORTHO4XP_V3",
        passive_head="a" * 40,
        passive_state=fork_state,
    )


def issue(
    current: WatchObservation,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "number": 100,
        "title": "[Upstream Watch] ORTHO4XP_V3 review status",
        "body": render_observation_body(current),
        "state": "open",
        "labels": [{"name": "upstream-watch"}],
    }
    value.update(overrides or {})
    return value
