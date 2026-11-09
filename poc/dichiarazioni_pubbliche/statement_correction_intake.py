"""#704/#468: authenticated correction intake for a published v3 Statement.

A Statement-only public record has no required Claim/Finding, so the v2 finding
intake cannot express a challenge against it. This module opens the same
private, append-only DP-468 challenge, reports its state to the submitting
account and fences the public release while a challenged version is still part
of the current release.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

from .public_api import PublicApiError, dispatch, error_response
from .public_api import _unavailable as _unavailable_error
from .public_v3_http import (
    _current_release, pinned_release, response_for_pinned_release,
)

_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_STORE_READERS = (
    "current_hold", "open_request", "replay_request", "public_release_clear",
)


def _unavailable() -> tuple[int, dict[str, object]]:
    return 503, {"error": "PUBLIC_PROJECTION_UNAVAILABLE"}


def _release_body(body: object) -> dict | None:
    payload = json.loads(body)
    return payload if isinstance(payload, dict) else None


def _release_published_versions(body: object) -> frozenset[tuple[str, str]] | None:
    payload = _release_body(body)
    return _published_versions(payload.get("data") if payload is not None else None)


def _release_generated_at(body: object) -> object:
    payload = _release_body(body)
    meta = payload.get("meta") if payload is not None else None
    return meta.get("generated_at") if isinstance(meta, dict) else None


def _release_time(value: object) -> datetime:
    if (not isinstance(value, str) or not value.strip()
            or value.strip() != value or "T" not in value):
        raise ValueError("STATEMENT_V3_RELEASE_TIME_INVALID")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("STATEMENT_V3_RELEASE_TIME_INVALID")
    return parsed.astimezone(timezone.utc)


def _unavailable_response(method: str):
    return error_response(
        _unavailable_error(), request_id="statement-correction-fence", method=method)


def _published_versions(rows: object) -> frozenset[tuple[str, str]] | None:
    if not isinstance(rows, list):
        return None
    published: set[tuple[str, str]] = set()
    for row in rows:
        if (not isinstance(row, dict)
                or not isinstance(row.get("statement_id"), str)
                or not _ID.fullmatch(row["statement_id"])
                or not isinstance(row.get("version_id"), str)
                or not _ID.fullmatch(row["version_id"])):
            return None
        published.add((row["statement_id"], row["version_id"]))
    return frozenset(published)


class StatementCorrectionIntake:
    """Own the v3 Statement correction contract; the listener only delegates."""

    def __init__(self, projection_path: object, current_fingerprint_path: object, store: object):
        if (not projection_path or not current_fingerprint_path or store is None
                or any(not callable(getattr(store, name, None)) for name in _STORE_READERS)):
            raise ValueError("STATEMENT_CORRECTION_RELEASE_AND_LEDGER_REQUIRED")
        self.projection_path = projection_path
        self.current_fingerprint_path = current_fingerprint_path
        self.store = store

    def _read(self, method: str, path: str):
        return dispatch(
            method, path,
            statement_projection_path=self.projection_path,
            statement_current_fingerprint_path=self.current_fingerprint_path,
            accept="application/json",
        )

    def public_response(self, method: str, path: str):
        """Serve exactly the release this request fenced on.

        The fence and the body must observe one snapshot: reading the pointer
        again after the fence would let a rotation in between return a
        challenged version the fence never checked.
        """
        try:
            _, authority, release, bundle = pinned_release(
                self.projection_path, self.current_fingerprint_path)
            response = response_for_pinned_release(
                method, path, bundle=bundle, release=release)
            listing = response_for_pinned_release(
                "GET", "/api/v3/statements", bundle=bundle, release=release)
            published = _release_published_versions(listing.body)
            released_at = _release_generated_at(listing.body)
            cb = self._served_after_challenge(released_at)
            clear = None if published is None else self.store.public_release_clear(
                published, may_serve_cleared=cb)
            if (published is None or clear is not True
                    or _current_release(authority) != release):
                return _unavailable_response(method)
        except PublicApiError as exc:
            return error_response(exc, request_id="statement-correction-fence", method=method)
        except Exception:
            # An unreadable release, an unreadable ledger or a moved pointer all
            # fail closed: the public surface never guesses.
            return _unavailable_response(method)
        return response

    def _served_after_challenge(self, released_at: object):
        """A cleared version is servable only by a release newer than its challenge.

        A release that predates the challenge cannot carry the clearance that
        cleared it: serving it would republish the contested version under the
        old fingerprint.
        """
        try:
            release_time = _release_time(released_at)
        except ValueError:
            return lambda target, opened: False

        def servable(target: tuple[str, str], opened: str) -> bool:
            return isinstance(opened, str) and opened != "" and release_time > _release_time(opened)

        return servable

    def published_release_pin(self) -> str | None:
        """Fingerprint of a release proven clear, or None on any uncertainty."""
        try:
            _, authority, release, bundle = pinned_release(
                self.projection_path, self.current_fingerprint_path)
            listing = response_for_pinned_release(
                "GET", "/api/v3/statements", bundle=bundle, release=release)
        except Exception:
            return None
        if listing.status != 200:
            return None
        try:
            published = _release_published_versions(listing.body)
            released_at = _release_generated_at(listing.body)
        except Exception:
            return None
        if published is None:
            return None
        if (self.store.public_release_clear(
                published, may_serve_cleared=self._served_after_challenge(released_at)) is not True):
            return None
        try:
            return release if _current_release(authority) == release else None
        except Exception:
            return None

    def published_version_clear(self) -> bool:
        return self.published_release_pin() is not None

    def current_statement(self, statement_id: str) -> dict[str, object] | None:
        response = self._read("GET", "/api/v3/statements/" + quote(statement_id, safe=""))
        if response.status == 404:
            return None
        if response.status != 200:
            raise RuntimeError("STATEMENT_V3_RELEASE_UNAVAILABLE")
        payload = json.loads(response.body)
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or data.get("statement_id") != statement_id:
            raise RuntimeError("STATEMENT_V3_RECORD_INVALID")
        return data

    def open_hold(
        self, actor: str, statement_id: str, version_id: str, reason: str,
        *, reserve, purge,
    ) -> tuple[int, dict[str, object]]:
        """Open one durable private challenge for an exact published version."""
        try:
            current = self.current_statement(statement_id)
            if current is None or current.get("version_id") != version_id:
                return 404, {"error": "NOT_FOUND"}
            if reserve(actor) is not True:
                return 429, {"error": "CORRECTION_RATE_LIMITED"}
            reason_hash = hashlib.sha256(reason.encode("utf-8")).hexdigest()
            material = json.dumps({
                "statement_id": statement_id,
                "version_id": version_id,
                "reason_sha256": reason_hash,
            }, sort_keys=True, separators=(",", ":")).encode("utf-8")
            request_id = self.store.open_request(
                statement_id=statement_id,
                version_id=version_id,
                intake_ref="intake:public-statement-correction:" + hashlib.sha256(material).hexdigest(),
                requester_ref_sha256=hashlib.sha256(actor.encode("utf-8")).hexdigest(),
                reason_sha256=reason_hash,
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                actor_ref=actor,
            )
            hold = self.store.current_hold(statement_id, version_id)
            if hold is None:
                return _unavailable()
            if hold is not True:
                return 409, {"error": "CORRECTION_ALREADY_RESOLVED"}
            if purge("statement-v3:" + statement_id) is not True:
                return _unavailable()
            return 202, {
                "request_id": request_id,
                "state": "HOLD",
                "message": "Segnalazione registrata; la versione resta sospesa in attesa della verifica.",
            }
        except ValueError as exc:
            if str(exc) == "DP468_CHALLENGE_INTAKE_CONFLICT":
                return 409, {"error": "ALREADY_UNDER_REVIEW"}
            return _unavailable()
        except Exception:
            return _unavailable()

    def status(self, actor: str, request_id: str) -> tuple[int, dict[str, object]]:
        """Report the HOLD state of one request to its own requester only."""
        try:
            replay = self.store.replay_request(request_id)
            if not isinstance(replay, dict):
                return 404, {"error": "NOT_FOUND"}
            request = replay.get("request")
            requester_hash = request.get("requester_ref_sha256") if isinstance(request, dict) else None
            expected_hash = hashlib.sha256(actor.encode()).hexdigest()
            if (not isinstance(requester_hash, str)
                    or not hmac.compare_digest(requester_hash, expected_hash)):
                return 404, {"error": "NOT_FOUND"}
            statement_id = request.get("statement_id")
            version_id = request.get("version_id")
            if not isinstance(statement_id, str) or not isinstance(version_id, str):
                return _unavailable()
            hold = self.store.current_hold(statement_id, version_id)
            if hold is None:
                return _unavailable()
            return 200, {
                "request_id": request_id,
                "state": "HOLD" if hold else "RESOLVED",
                "review_state": str(replay.get("current_state", "UNKNOWN")),
            }
        except Exception:
            return _unavailable()
