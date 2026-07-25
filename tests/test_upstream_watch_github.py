"""Idempotent managed-issue reconciliation contracts."""

from __future__ import annotations

import json
import unittest
from typing import cast

from scripts.upstream_watch_core.github_api import (
    GitHubApiError,
    GitHubClient,
    HttpResponse,
    WatchObservation,
    observation_fingerprint,
    reconcile_tracking_issue,
    render_observation_body,
)
from scripts.upstream_watch_core.models import (
    WatchExit,
)
from tests._path import ROOT_DIR  # noqa: F401
from tests._upstream_watch_helpers import (
    FakeTransport,
    json_response,
)
from tests._upstream_watch_helpers import (
    issue as issue_payload,
)
from tests._upstream_watch_helpers import (
    observation as make_observation,
)


class GitHubIssueTests(unittest.TestCase):
    def test_creates_label_and_single_tracking_issue(self) -> None:
        # Creation establishes the exact identity consumed by later runs.
        observation = make_observation()
        transport = FakeTransport(
            [
                json_response(404, {"message": "Not Found"}),
                json_response(201, {"name": "upstream-watch"}),
                json_response(200, []),
                json_response(201, issue_payload(observation)),
            ]
        )
        client = GitHubClient("secret-token", transport=transport)
        result = reconcile_tracking_issue(
            client,
            repository="tvproductions/Ortho4XP",
            observation=observation,
        )
        self.assertEqual(result.action, "created")
        self.assertEqual(result.issue_number, 100)
        self.assertNotIn("secret-token", repr(transport.requests))
        self.assertEqual(
            [request["method"] for request in transport.requests],
            ["GET", "POST", "GET", "POST"],
        )

    def test_unchanged_fingerprint_makes_no_issue_mutation(self) -> None:
        # Stable observations remain read-only reconciliations.
        observation = make_observation()
        transport = FakeTransport(
            [
                json_response(200, {"name": "upstream-watch"}),
                json_response(200, [issue_payload(observation)]),
            ]
        )
        result = reconcile_tracking_issue(
            GitHubClient("token", transport=transport),
            repository="tvproductions/Ortho4XP",
            observation=observation,
        )
        self.assertEqual(result.action, "unchanged")
        self.assertEqual(len(transport.requests), 2)

    def test_changed_fingerprint_updates_and_comments_once(self) -> None:
        # Pending state is persisted before its history entry is emitted.
        previous = make_observation(author_head="c" * 40)
        current = make_observation()
        transport = FakeTransport(
            [
                json_response(200, {"name": "upstream-watch"}),
                json_response(200, [issue_payload(previous)]),
                json_response(200, issue_payload(current)),
                json_response(200, []),
                json_response(201, {"id": 1}),
                json_response(200, issue_payload(current)),
            ]
        )
        result = reconcile_tracking_issue(
            GitHubClient("token", transport=transport),
            repository="tvproductions/Ortho4XP",
            observation=current,
        )
        self.assertEqual(result.action, "updated")
        self.assertEqual(
            [request["method"] for request in transport.requests],
            ["GET", "GET", "PATCH", "GET", "POST", "PATCH"],
        )

    def test_retry_completes_comment_state_without_duplicate_comment(self) -> None:
        # Retries recognize the transition marker before finalizing state.
        previous = make_observation(author_head="c" * 40)
        current = make_observation()
        current_fingerprint = observation_fingerprint(current)
        previous_fingerprint = observation_fingerprint(previous)
        pending_body = render_observation_body(current).replace(
            f"commented-fingerprint {current_fingerprint}",
            f"commented-fingerprint {previous_fingerprint}",
        )
        transition = (
            f"changed\n<!-- upstream-watch:transition {current_fingerprint} -->"
        )
        transport = FakeTransport(
            [
                json_response(200, {"name": "upstream-watch"}),
                json_response(200, [issue_payload(current, {"body": pending_body})]),
                json_response(200, [{"body": transition}]),
                json_response(200, issue_payload(current)),
            ]
        )
        result = reconcile_tracking_issue(
            GitHubClient("token", transport=transport),
            repository="tvproductions/Ortho4XP",
            observation=current,
        )
        self.assertEqual(result.action, "updated")
        self.assertEqual(
            [request["method"] for request in transport.requests],
            ["GET", "GET", "GET", "PATCH"],
        )

    def test_retry_posts_missing_transition_with_original_previous_fingerprint(
        self,
    ) -> None:
        previous = make_observation(author_head="c" * 40)
        current = make_observation()
        current_fingerprint = observation_fingerprint(current)
        previous_fingerprint = observation_fingerprint(previous)
        pending_body = render_observation_body(current).replace(
            f"commented-fingerprint {current_fingerprint}",
            f"commented-fingerprint {previous_fingerprint}",
        )
        transport = FakeTransport(
            [
                json_response(200, {"name": "upstream-watch"}),
                json_response(200, [issue_payload(current, {"body": pending_body})]),
                json_response(200, []),
                json_response(201, {"id": 1}),
                json_response(200, issue_payload(current)),
            ]
        )
        reconcile_tracking_issue(
            GitHubClient("token", transport=transport),
            repository="tvproductions/Ortho4XP",
            observation=current,
        )
        comment = cast(str, transport.requests[-2]["body"])
        self.assertIn(previous_fingerprint, comment)
        self.assertIn(current_fingerprint, comment)

    def test_failed_issue_update_never_posts_transition_comment(self) -> None:
        # Failed persistence cannot leave an orphaned history comment.
        previous = make_observation(author_head="c" * 40)
        current = make_observation()
        transport = FakeTransport(
            [
                json_response(200, {"name": "upstream-watch"}),
                json_response(200, [issue_payload(previous)]),
                json_response(500, {"message": "update failed"}),
            ]
        )
        with self.assertRaises(GitHubApiError):
            reconcile_tracking_issue(
                GitHubClient("token", transport=transport),
                repository="tvproductions/Ortho4XP",
                observation=current,
            )
        self.assertEqual(
            [request["method"] for request in transport.requests],
            ["GET", "GET", "PATCH"],
        )

    def _assert_state_transition(
        self, transition: tuple[WatchObservation, str, str, str]
    ) -> None:
        # Open and closed transitions share the two-phase comment protocol.
        observation, initial_state, action, final_state = transition
        previous_body = render_observation_body(make_observation(author_head="c" * 40))
        transport = FakeTransport(
            [
                json_response(200, {"name": "upstream-watch"}),
                json_response(
                    200,
                    [
                        issue_payload(
                            observation,
                            {"state": initial_state, "body": previous_body},
                        )
                    ],
                ),
                json_response(200, issue_payload(observation, {"state": final_state})),
                json_response(200, []),
                json_response(201, {"id": 1}),
                json_response(200, issue_payload(observation, {"state": final_state})),
            ]
        )
        result = reconcile_tracking_issue(
            GitHubClient("token", transport=transport),
            repository="tvproductions/Ortho4XP",
            observation=observation,
        )
        self.assertEqual(result.action, action)
        patch_body = json.loads(cast(str, transport.requests[-1]["body"]))
        self.assertEqual(patch_body["state"], final_state)

    def test_reopens_closed_issue_for_review_status(self) -> None:
        self._assert_state_transition(
            (make_observation(), "closed", "reopened", "open")
        )

    def test_closes_open_issue_for_current_status(self) -> None:
        self._assert_state_transition(
            (
                make_observation(status=WatchExit.CURRENT),
                "open",
                "closed",
                "closed",
            )
        )

    def test_paginates_only_same_origin_links(self) -> None:
        # Pagination stays pinned to GitHub's authenticated API origin.
        observation = make_observation()
        next_url = (
            "https://api.github.com/repos/tvproductions/Ortho4XP/issues?"
            "state=all&labels=upstream-watch&per_page=100&page=2"
        )
        transport = FakeTransport(
            [
                json_response(
                    200,
                    [],
                    {"Link": f'<{next_url}>; rel="next"'},
                ),
                json_response(200, [issue_payload(observation)]),
            ]
        )
        issues = GitHubClient("token", transport=transport).list_issues(
            "tvproductions/Ortho4XP", label="upstream-watch"
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(len(transport.requests), 2)

    def test_reports_rate_limits_and_malformed_json_without_token(self) -> None:
        # Bounded failures must not expose the bearer token.
        cases = (
            HttpResponse(
                status=403,
                headers={"X-RateLimit-Remaining": "0"},
                body=b'{"message":"rate limit exceeded"}',
            ),
            HttpResponse(status=200, headers={}, body=b"not-json"),
        )
        for response in cases:
            with self.subTest(status=response.status):
                transport = FakeTransport([response])
                client = GitHubClient("secret-token", transport=transport)
                with self.assertRaises(GitHubApiError) as context:
                    client.ensure_label("tvproductions/Ortho4XP")
                self.assertNotIn("secret-token", str(context.exception))

    def test_fingerprint_is_canonical_and_fork_lag_is_informational(self) -> None:
        # Normal passive lag is not an engineering blocker.
        observation = make_observation()
        self.assertEqual(
            observation_fingerprint(observation),
            observation_fingerprint(make_observation()),
        )
        body = render_observation_body(observation)
        self.assertIn("informational", body.casefold())
        self.assertIn("Ypsos/ORTHO4XP_V3", body)
        self.assertIn("tvproductions/ORTHO4XP_V3", body)
