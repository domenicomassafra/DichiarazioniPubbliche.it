"""Read-only changedetection.io snapshot adapter for DP-515 authorized polls.

changedetection.io owns fetching its configured URL. This adapter only reads its
loopback API after DP-515 has admitted the attempt, then commits the resulting
WatchObservation through the existing source-watch store. It never schedules,
creates watches, rechecks URLs, enqueues children or publishes content.
"""

from __future__ import annotations

import hashlib
import json
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping
from urllib import error, request
from urllib.parse import urlsplit
from uuid import UUID

from .incremental_source_watch import (
    WatchDecision, WatchObservation, WatchPlan, WatchPolicy, policy_fingerprint,
)
from .source_watch_store_v1 import LocalSourceWatchStore


_MAX_METADATA = 128 * 1024
_MAX_SNAPSHOT = 2 * 1024 * 1024
_MAX_SKEW_SECONDS = 600
_SERVICE_VERSION = "0.60.9"


@dataclass(frozen=True)
class ChangedetectionBinding:
    """An operator-approved no-feed URL bound to a specific upstream watch."""

    source_id: str
    locator_id: str
    canonical_url: str
    watch_uuid: str
    api_base: str = "http://127.0.0.1:5000"
    max_check_age_seconds: int = 600


@dataclass(frozen=True)
class ChangedetectionSnapshot:
    watch: Mapping[str, object]
    history: Mapping[str, object]
    content: bytes


@dataclass(frozen=True)
class ChangedetectionReceipt:
    """Private metadata; never includes page text, provider credentials or headers."""

    source_id: str
    canonical_url: str
    watch_uuid: str
    attempt_id: str
    observed_at: datetime
    upstream_release_reference: str
    provider_checked_at: datetime | None
    provider_history_key: str | None
    content_sha256: str | None
    disposition: str
    reason: str
    receipt_sha256: str
    measured_cost_micro_eur: int | None = None  # Unknown until metered externally.


class ChangedetectionError(ValueError):
    """Invalid configuration, source binding or unverified upstream metadata."""


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_loopback(api_base: str) -> None:
    api = urlsplit(api_base)
    try:
        port = api.port
    except ValueError as exc:
        raise ChangedetectionError("API_MUST_BE_LOOPBACK") from exc
    if (api.scheme != "http" or api.hostname not in ("127.0.0.1", "::1")
            or api.username or api.password or api.path not in ("", "/")
            or api.query or api.fragment or port is None):
        raise ChangedetectionError("API_MUST_BE_LOOPBACK")


def _validate(binding: ChangedetectionBinding, policy: WatchPolicy) -> str:
    if (policy.source_family != "WEB_NO_FEED"
            or binding.source_id != policy.source_id
            or binding.locator_id != policy.locator_id):
        raise ChangedetectionError("NO_FEED_PROFILE_NOT_AUTHORIZED")
    target = urlsplit(binding.canonical_url)
    if (target.scheme != "https" or not target.hostname or target.username
            or target.password or target.fragment):
        raise ChangedetectionError("CANONICAL_URL_INVALID")
    try:
        watch_id = str(UUID(binding.watch_uuid))
    except (ValueError, AttributeError) as exc:
        raise ChangedetectionError("WATCH_UUID_INVALID") from exc
    if watch_id != binding.watch_uuid:
        raise ChangedetectionError("WATCH_UUID_NOT_CANONICAL")
    _validate_loopback(binding.api_base)
    if (type(binding.max_check_age_seconds) is not int
            or not 1 <= binding.max_check_age_seconds <= 86400):
        raise ChangedetectionError("CHECK_AGE_INVALID")
    return watch_id


def _json_object(payload: bytes) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeError, ValueError) as exc:
        raise ChangedetectionError("PROVIDER_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise ChangedetectionError("PROVIDER_JSON_NOT_OBJECT")
    return value


def _get(opener, url: str, key: str, limit: int) -> bytes:
    req = request.Request(url, headers={"x-api-key": key, "Accept": "application/json"})
    with opener.open(req, timeout=5) as response:
        if response.status != 200:
            raise ChangedetectionError("PROVIDER_HTTP_UNEXPECTED")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ChangedetectionError("PROVIDER_RESPONSE_TOO_LARGE")
    return data


def read_changedetection_snapshot(binding: ChangedetectionBinding, *, api_key: str) -> ChangedetectionSnapshot:
    """Only authenticated GET requests; upstream watch must already exist."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise ChangedetectionError("API_TOKEN_REQUIRED")
    _validate_loopback(binding.api_base)
    # UUID validated before interpolation, preventing arbitrary API paths.
    watch_id = str(UUID(binding.watch_uuid))
    if watch_id != binding.watch_uuid:
        raise ChangedetectionError("WATCH_UUID_NOT_CANONICAL")
    base = binding.api_base.rstrip("/")
    route = f"{base}/api/v1/watch/{watch_id}"
    # This API is strictly loopback. Ignore ambient HTTP_PROXY/HTTPS_PROXY so
    # the private x-api-key can never be forwarded to a host-level proxy.
    opener = request.build_opener(request.ProxyHandler({}), _NoRedirect())
    watch = _json_object(_get(opener, route, api_key, _MAX_METADATA))
    history = _json_object(_get(opener, route + "/history", api_key, _MAX_METADATA))
    if not history:
        raise ChangedetectionError("PROVIDER_HISTORY_EMPTY")
    body = _get(opener, route + "/history/latest", api_key, _MAX_SNAPSHOT)
    if not body:
        raise ChangedetectionError("PROVIDER_SNAPSHOT_EMPTY")
    return ChangedetectionSnapshot(watch, history, body)


def snapshot_to_observation(
    binding: ChangedetectionBinding,
    snapshot: ChangedetectionSnapshot,
    *,
    attempted_at: datetime,
    observed_at: datetime,
    previous_success_at: datetime | None = None,
) -> tuple[WatchObservation, datetime, str]:
    """Accept only fresh, exact-URL snapshots; do not trust provider diff flags."""
    watch = snapshot.watch
    if (watch.get("uuid") not in (None, binding.watch_uuid)
            or watch.get("url") != binding.canonical_url
            or watch.get("link", binding.canonical_url) != binding.canonical_url):
        raise ChangedetectionError("PROVIDER_SOURCE_MISMATCH")
    if watch.get("last_error"):
        raise ChangedetectionError("PROVIDER_LAST_CHECK_FAILED")
    checked = watch.get("last_checked")
    if type(checked) not in (int, float) or checked <= 0:
        raise ChangedetectionError("PROVIDER_LAST_CHECK_UNKNOWN")
    try:
        checked_at = datetime.fromtimestamp(checked, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise ChangedetectionError("PROVIDER_LAST_CHECK_INVALID") from exc
    if (observed_at.tzinfo is None or attempted_at.tzinfo is None
            or checked_at.timestamp() < attempted_at.timestamp() - binding.max_check_age_seconds
            or checked_at.timestamp() > observed_at.timestamp() + _MAX_SKEW_SECONDS):
        raise ChangedetectionError("PROVIDER_CHECK_STALE_OR_FUTURE")
    if (previous_success_at is not None
            and checked_at.timestamp() <= previous_success_at.timestamp()):
        # Re-reading one cached upstream result cannot advance DP freshness.
        raise ChangedetectionError("PROVIDER_CHECK_NOT_NEWER_THAN_LAST_SUCCESS")
    if not snapshot.history or not all(
        isinstance(key, str) and key.isdecimal() and len(key) <= 20
        for key in snapshot.history
    ):
        raise ChangedetectionError("PROVIDER_HISTORY_INVALID")
    if not isinstance(snapshot.content, bytes) or not 0 < len(snapshot.content) <= _MAX_SNAPSHOT:
        raise ChangedetectionError("PROVIDER_SNAPSHOT_INVALID")
    history_key = next(reversed(snapshot.history))
    digest = hashlib.sha256(snapshot.content).hexdigest()
    # Source version follows the verified text digest; an upstream history
    # timestamp alone cannot cause duplicate child proposals for equal bytes.
    return (
        WatchObservation(observed_at=observed_at, status_code=200,
                         content_sha256=digest, source_version=f"sha256:{digest}"),
        checked_at,
        history_key,
    )


def poll_changedetection_watch(
    store: LocalSourceWatchStore,
    policy: WatchPolicy,
    binding: ChangedetectionBinding,
    *,
    attempt_id: str,
    attempted_at: datetime,
    observed_at: datetime,
    api_key: str = "",
    snapshot: ChangedetectionSnapshot | None = None,
) -> tuple[WatchPlan, ChangedetectionReceipt | None]:
    """DP-515 plans first and commits once; synthetic snapshot is for isolated tests.

    Real callers omit snapshot. This does not create a second queue or poll a
    source site: only the upstream loopback snapshot store is read.
    """
    _validate(binding, policy)
    plan = store.begin_poll(policy.source_id, attempt_id=attempt_id, attempted_at=attempted_at)
    if plan.policy_fingerprint != policy_fingerprint(policy):
        if plan.allowed:
            store.commit_observation(
                policy.source_id, attempt_id=attempt_id,
                observation=WatchObservation(observed_at=observed_at, status_code=503),
            )
        raise ChangedetectionError("STORED_PROFILE_MISMATCH")
    if not plan.allowed:
        return plan, None

    previous_success_at = store.read_state(policy.source_id).last_successful_observed_at
    provider_checked_at = None
    history_key = None
    observation = WatchObservation(observed_at=observed_at, status_code=503)
    try:
        incoming = snapshot if snapshot is not None else read_changedetection_snapshot(binding, api_key=api_key)
        observation, provider_checked_at, history_key = snapshot_to_observation(
            binding, incoming, attempted_at=attempted_at, observed_at=observed_at,
            previous_success_at=previous_success_at,
        )
    except error.HTTPError as exc:
        observation = WatchObservation(observed_at=observed_at,
                                       status_code=exc.code if exc.code in (429, 503) else 503)
    except (ChangedetectionError, error.URLError, socket.timeout, TimeoutError):
        # The DP-515 state machine owns backoff and circuit breaker handling.
        observation = WatchObservation(observed_at=observed_at, status_code=503)
    decision: WatchDecision = store.commit_observation(
        policy.source_id, attempt_id=attempt_id, observation=observation,
    )
    proof = json.dumps(
        [policy.source_id, binding.canonical_url, binding.watch_uuid, attempt_id,
         observed_at.isoformat(), history_key, observation.content_sha256,
         decision.disposition, decision.reason], separators=(",", ":"),
    ).encode("utf-8")
    return plan, ChangedetectionReceipt(
        source_id=policy.source_id, canonical_url=binding.canonical_url,
        watch_uuid=binding.watch_uuid, attempt_id=attempt_id, observed_at=observed_at,
        upstream_release_reference=_SERVICE_VERSION, provider_checked_at=provider_checked_at,
        provider_history_key=history_key, content_sha256=observation.content_sha256,
        disposition=decision.disposition, reason=decision.reason,
        receipt_sha256=hashlib.sha256(proof).hexdigest(),
    )
