"""Minimal GitHub REST client for one managed upstream-watch tracking issue."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol, cast

from .models import ForkState, WatchExit, canonical_json_bytes, validate_repository

API_ORIGIN = "https://api.github.com"
API_VERSION = "2022-11-28"
TRACKING_TITLE = "[Upstream Watch] ORTHO4XP_V3 review status"
TRACKING_LABEL = "upstream-watch"
_FINGERPRINT_RE = re.compile(r"<!-- upstream-watch:fingerprint ([0-9a-f]{64}) -->")


class GitHubApiError(RuntimeError):
    """Raised when GitHub cannot provide or accept a trustworthy response."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> HttpResponse: ...


class UrllibTransport:
    """Network transport restricted to GitHub's HTTPS API origin."""

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> HttpResponse:
        _require_api_url(url)
        request = urllib.request.Request(  # noqa: S310 - URL origin validated above.
            url=url, data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                return HttpResponse(
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            return HttpResponse(
                status=exc.code,
                headers=dict(exc.headers.items()) if exc.headers else {},
                body=exc.read(),
            )
        except urllib.error.URLError as exc:
            raise GitHubApiError("GitHub API request failed") from exc


@dataclass(frozen=True, slots=True)
class IssueSnapshot:
    number: int
    title: str
    body: str
    state: str
    labels: tuple[str, ...]
    is_pull_request: bool = False

    @classmethod
    def from_dict(cls, value: object) -> IssueSnapshot:
        if not isinstance(value, dict):
            raise GitHubApiError("GitHub returned a non-object issue")
        number = value.get("number")
        title = value.get("title")
        body = value.get("body")
        state = value.get("state")
        raw_labels = value.get("labels")
        if (
            isinstance(number, bool)
            or not isinstance(number, int)
            or number <= 0
            or not isinstance(title, str)
            or not isinstance(body, str)
            or state not in {"open", "closed"}
            or not isinstance(raw_labels, list)
        ):
            raise GitHubApiError("GitHub returned a malformed issue")
        labels: list[str] = []
        for raw_label in raw_labels:
            if not isinstance(raw_label, dict):
                raise GitHubApiError("GitHub returned a malformed issue label")
            raw_label_map = cast(dict[str, object], raw_label)
            name = raw_label_map.get("name")
            if not isinstance(name, str):
                raise GitHubApiError("GitHub returned a malformed issue label")
            labels.append(name)
        return cls(
            number=number,
            title=title,
            body=body,
            state=cast(str, state),
            labels=tuple(labels),
            is_pull_request="pull_request" in value,
        )


@dataclass(frozen=True, slots=True)
class WatchObservation:
    status: WatchExit
    author_repository: str
    author_branch: str
    baseline_sha: str
    author_head: str
    passive_repository: str
    passive_branch: str
    passive_head: str
    passive_state: ForkState

    def to_dict(self) -> dict[str, object]:
        return {
            "status": int(self.status),
            "author": {
                "repository": self.author_repository,
                "branch": self.author_branch,
                "baseline_sha": self.baseline_sha,
                "head_sha": self.author_head,
            },
            "passive_fork": {
                "repository": self.passive_repository,
                "branch": self.passive_branch,
                "head_sha": self.passive_head,
                "state": self.passive_state.value,
            },
        }


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    action: str
    issue_number: int | None
    fingerprint: str


class GitHubClient:
    """Small authenticated client with redacted state and strict pagination."""

    def __init__(self, token: str, *, transport: HttpTransport | None = None) -> None:
        if not token or any(ord(character) < 33 for character in token):
            raise GitHubApiError("GitHub token is missing or malformed")
        self._token = token
        self.transport = transport or UrllibTransport()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(token='***')"

    def ensure_label(self, repository: str) -> None:
        repository = validate_repository(repository, "repository")
        encoded = urllib.parse.quote(TRACKING_LABEL, safe="")
        response = self._send(
            "GET", f"/repos/{repository}/labels/{encoded}", expected={200, 404}
        )
        if response.status == 200:
            self._decode_json(response)
            return
        self._request_json(
            "POST",
            f"/repos/{repository}/labels",
            {"name": TRACKING_LABEL, "color": "1d76db"},
            expected={201},
        )

    def list_issues(self, repository: str, *, label: str) -> tuple[IssueSnapshot, ...]:
        repository = validate_repository(repository, "repository")
        query = urllib.parse.urlencode(
            {"state": "all", "labels": label, "per_page": 100}
        )
        url: str | None = f"{API_ORIGIN}/repos/{repository}/issues?{query}"
        issues: list[IssueSnapshot] = []
        while url is not None:
            response = self._send("GET", url, expected={200})
            payload = self._decode_json(response)
            if not isinstance(payload, list):
                raise GitHubApiError("GitHub returned a non-array issue list")
            issues.extend(IssueSnapshot.from_dict(item) for item in payload)
            url = _next_link(response.headers)
        return tuple(issues)

    def create_issue(self, repository: str, title: str, body: str) -> IssueSnapshot:
        payload = self._request_json(
            "POST",
            f"/repos/{repository}/issues",
            {"title": title, "body": body, "labels": [TRACKING_LABEL]},
            expected={201},
        )
        return IssueSnapshot.from_dict(payload)

    def update_issue(
        self,
        repository: str,
        number: int,
        *,
        body: str,
        state: str,
    ) -> IssueSnapshot:
        payload = self._request_json(
            "PATCH",
            f"/repos/{repository}/issues/{number}",
            {"body": body, "state": state},
            expected={200},
        )
        return IssueSnapshot.from_dict(payload)

    def add_comment(self, repository: str, number: int, body: str) -> None:
        self._request_json(
            "POST",
            f"/repos/{repository}/issues/{number}/comments",
            {"body": body},
            expected={201},
        )

    def _request_json(
        self,
        method: str,
        path_or_url: str,
        payload: object | None = None,
        *,
        expected: set[int],
    ) -> object:
        body = None if payload is None else canonical_json_bytes(payload)
        return self._decode_json(
            self._send(method, path_or_url, body=body, expected=expected)
        )

    def _send(
        self,
        method: str,
        path_or_url: str,
        *,
        body: bytes | None = None,
        expected: set[int],
    ) -> HttpResponse:
        url = (
            path_or_url
            if path_or_url.startswith("https://")
            else f"{API_ORIGIN}{path_or_url}"
        )
        _require_api_url(url)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "Ortho4XP-upstream-watch",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        response = self.transport.request(method, url, headers, body)
        if response.status not in expected:
            if (
                response.status in {403, 429}
                and _header(response.headers, "X-RateLimit-Remaining") == "0"
            ):
                raise GitHubApiError("GitHub API rate limit was exhausted")
            message = _safe_error_message(response.body)
            raise GitHubApiError(
                f"GitHub API returned status {response.status}: {message}"
            )
        return response

    @staticmethod
    def _decode_json(response: HttpResponse) -> object:
        try:
            return json.loads(response.body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise GitHubApiError("GitHub returned malformed JSON") from exc


def _require_api_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "api.github.com"
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise GitHubApiError("GitHub API URL must stay on https://api.github.com/")


def _header(headers: dict[str, str], name: str) -> str | None:
    expected = name.casefold()
    return next(
        (value for key, value in headers.items() if key.casefold() == expected), None
    )


def _safe_error_message(body: bytes) -> str:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return "unreadable response"
    if isinstance(payload, dict) and isinstance(payload.get("message"), str):
        return cast(str, payload["message"])[:512]
    return "request failed"


def _next_link(headers: dict[str, str]) -> str | None:
    header = _header(headers, "Link")
    if not header:
        return None
    for part in header.split(","):
        section = part.strip()
        if 'rel="next"' not in section:
            continue
        if not section.startswith("<") or ">" not in section:
            raise GitHubApiError("GitHub pagination link was malformed")
        url = section[1 : section.index(">")]
        _require_api_url(url)
        return url
    return None


def observation_fingerprint(observation: WatchObservation) -> str:
    return hashlib.sha256(canonical_json_bytes(observation.to_dict())).hexdigest()


def render_observation_body(observation: WatchObservation) -> str:
    fingerprint = observation_fingerprint(observation)
    status_name = observation.status.name.replace("_", " ").title()
    if observation.passive_state in {ForkState.BEHIND, ForkState.SYNCHRONIZED}:
        passive_note = (
            "Informational only; normal passive-fork lag does not block engineering "
            "review or accepted-baseline advancement."
        )
    else:
        passive_note = (
            "Configuration anomaly; unexpected passive-fork commits or divergence "
            "require investigation."
        )
    return "\n".join(
        [
            "# ORTHO4XP_V3 upstream watch",
            "",
            f"Status: **{status_name}** (`{int(observation.status)}`)",
            "",
            "## Authoritative engineering source",
            "",
            f"- Repository: `{observation.author_repository}`",
            f"- Branch: `{observation.author_branch}`",
            f"- Accepted baseline: `{observation.baseline_sha}`",
            f"- Observed head: `{observation.author_head}`",
            "",
            "## Passive synchronization fork",
            "",
            f"- Repository: `{observation.passive_repository}`",
            f"- Branch: `{observation.passive_branch}`",
            f"- Observed head: `{observation.passive_head}`",
            f"- Relationship: `{observation.passive_state.value}`",
            f"- {passive_note}",
            "",
            "This issue is managed by `.github/workflows/upstream-watch.yml`.",
            f"<!-- upstream-watch:fingerprint {fingerprint} -->",
            "",
        ]
    )


def reconcile_tracking_issue(
    client: GitHubClient,
    *,
    repository: str,
    observation: WatchObservation,
) -> ReconcileResult:
    """Create, update, reopen, close, or leave one exact managed issue."""

    repository = validate_repository(repository, "repository")
    client.ensure_label(repository)
    candidates = [
        issue
        for issue in client.list_issues(repository, label=TRACKING_LABEL)
        if not issue.is_pull_request
        and issue.title == TRACKING_TITLE
        and TRACKING_LABEL in issue.labels
    ]
    if len(candidates) > 1:
        raise GitHubApiError("Multiple upstream-watch tracking issues exist")
    fingerprint = observation_fingerprint(observation)
    desired_body = render_observation_body(observation)
    desired_state = "closed" if observation.status is WatchExit.CURRENT else "open"
    if not candidates:
        if desired_state == "closed":
            return ReconcileResult(
                action="unchanged", issue_number=None, fingerprint=fingerprint
            )
        created = client.create_issue(repository, TRACKING_TITLE, desired_body)
        return ReconcileResult(
            action="created",
            issue_number=created.number,
            fingerprint=fingerprint,
        )

    issue = candidates[0]
    existing_match = _FINGERPRINT_RE.search(issue.body)
    existing_fingerprint = existing_match.group(1) if existing_match else None
    state_changed = issue.state != desired_state
    fingerprint_changed = existing_fingerprint != fingerprint
    if not state_changed and not fingerprint_changed:
        return ReconcileResult(
            action="unchanged", issue_number=issue.number, fingerprint=fingerprint
        )
    if fingerprint_changed:
        client.add_comment(
            repository,
            issue.number,
            "\n".join(
                [
                    "Upstream-watch observation changed.",
                    "",
                    f"- Previous fingerprint: `{existing_fingerprint or 'missing'}`",
                    f"- Current fingerprint: `{fingerprint}`",
                ]
            ),
        )
    client.update_issue(
        repository,
        issue.number,
        body=desired_body,
        state=desired_state,
    )
    if issue.state == "closed" and desired_state == "open":
        action = "reopened"
    elif issue.state == "open" and desired_state == "closed":
        action = "closed"
    else:
        action = "updated"
    return ReconcileResult(
        action=action, issue_number=issue.number, fingerprint=fingerprint
    )
