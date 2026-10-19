"""Bounded private DP-244 HTTP observation using the existing DP-236/515 gates.

The caller supplies an authenticated current rights reader and independently
persists any accepted receipt. This adapter never persists source bodies,
creates Captures, dispatches child work, or publishes anything. A caller must
recheck the gate and state revision before committing an observation.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from dichiarazioni_pubbliche.incremental_source_watch import (
    WatchCommittedAttempt,
    WatchObservation,
    WatchPolicy,
    WatchReadiness,
    WatchState,
    plan_watch_poll,
    reconcile_watch_observation,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard

MAX_BODY_BYTES = 512 * 1024


@dataclass(frozen=True)
class HttpResult:
    status_code: int | None
    final_url: str
    body: bytes = b""
    etag: str | None = None
    last_modified: str | None = None
    transport_error: str | None = None
    retry_after_seconds: int | None = None


@dataclass(frozen=True)
class ConditionalProbeReceipt:
    committed_attempt: WatchCommittedAttempt
    fetched_bytes: int
    # The network and external provider's metered cost cannot be inferred from
    # successful HTTP, even for a response without a body.
    measured_cost_micro_eur: int | None = None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def bounded_http_get(url: str, headers: tuple[tuple[str, str], ...]) -> HttpResult:
    """One HTTPS request, no redirects, no unbounded response or stored body."""
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("DP244_HTTPS_URL_REQUIRED")
    request = Request(url, headers=dict(headers), method="GET")
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=8) as response:
            data = response.read(MAX_BODY_BYTES + 1)
            if len(data) > MAX_BODY_BYTES:
                raise ValueError("DP244_RESPONSE_TOO_LARGE")
            return HttpResult(
                response.status, response.geturl(), data,
                response.headers.get("ETag"), response.headers.get("Last-Modified"),
            )
    except HTTPError as exc:
        # urllib presents even a valid HTTP 304 through HTTPError. Never read
        # error-page bodies or follow an unreviewed redirect destination.
        return HttpResult(exc.code, exc.geturl())
    except TimeoutError:
        return HttpResult(None, url, transport_error="TIMEOUT")
    except (URLError, OSError):
        return HttpResult(None, url, transport_error="NETWORK_ERROR")


def probe_permitted_source(
    *,
    policy: WatchPolicy,
    state: WatchState,
    planning_gate: WatchReadiness,
    current_gate: Callable[[], WatchReadiness],
    rights_guard: SourceFamilyUseGuard,
    content_id: str,
    url: str,
    attempt_id: str,
    attempted_at: datetime,
    fetch: Callable[[str, tuple[tuple[str, str], ...]], HttpResult] = bounded_http_get,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ConditionalProbeReceipt:
    """Observe one explicitly authorized URL and return a replayable receipt.

    Rights must be checked before HTTP and again after the response. A changed
    representation yields a held *review proposal*, not an immutable Capture;
    storing a Capture requires a separate STORE_BODY clearance and pipeline.
    """
    if type(rights_guard) is not SourceFamilyUseGuard or not callable(current_gate):
        raise ValueError("DP244_CURRENT_RIGHTS_GATE_REQUIRED")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("DP244_HTTPS_URL_REQUIRED")
    if policy.locator_id != url or policy.source_family != rights_guard.subject.source_family:
        raise ValueError("DP244_SOURCE_BINDING_MISMATCH")
    rights_guard.bind_capture(content_id=content_id, url=url)
    rights_guard.require("FETCH")
    plan = plan_watch_poll(policy, state, planning_gate, attempt_id=attempt_id,
                           attempted_at=attempted_at)
    if not plan.allowed:
        raise ValueError("DP244_WATCH_" + plan.reason)
    response = fetch(url, plan.conditional_headers)
    if type(response) is not HttpResult or type(response.body) is not bytes:
        raise ValueError("DP244_HTTP_RESULT_INVALID")
    if len(response.body) > MAX_BODY_BYTES:
        raise ValueError("DP244_RESPONSE_TOO_LARGE")
    rights_guard.bind_fetched(final_url=response.final_url)
    # No new rights may be inferred from an HTTP 200/304 or from a prior permit.
    rights_guard.require("FETCH")
    if response.status_code != 200 and response.body:
        raise ValueError("DP244_UNEXPECTED_BODY")
    digest = hashlib.sha256(response.body).hexdigest() if response.status_code == 200 else None
    observation = WatchObservation(
        observed_at=clock(), status_code=response.status_code,
        content_sha256=digest, etag=response.etag,
        last_modified=response.last_modified, transport_error=response.transport_error,
        retry_after_seconds=response.retry_after_seconds,
    )
    gate_after = current_gate()
    decision = reconcile_watch_observation(
        policy, state, gate_after, plan, observation,
    )
    attempt = WatchCommittedAttempt(
        policy.source_id, state, planning_gate, gate_after, plan,
        observation, decision, measured_cost_micro_eur=None,
    )
    return ConditionalProbeReceipt(attempt, len(response.body))


__all__ = ["ConditionalProbeReceipt", "HttpResult", "bounded_http_get", "probe_permitted_source"]
