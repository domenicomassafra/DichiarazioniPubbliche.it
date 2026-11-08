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

from .public_api import dispatch

_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_STORE_READERS = ("challenged_statements", "current_hold", "open_request", "replay_request")


def _unavailable() -> tuple[int, dict[str, object]]:
    return 503, {"error": "PUBLIC_PROJECTION_UNAVAILABLE"}


class StatementCorrectionIntake:
    """Own the v3 Statement correction contract; the listener only delegates."""

    def __init__(self, projection_path: object, current_fingerprint_path: object, store: object):
        if (not projection_path or not current_fingerprint_path or store is None
                or any(not callable(getattr(store, name, None)) for name in _STORE_READERS)):
            raise ValueError("STATEMENT_CORRECTION_RELEASE_AND_LEDGER_REQUIRED")
        self.projection_path = projection_path
        self.current_fingerprint_path = current_fingerprint_path
        self.store = store

    def _read(self, path: str):
        return dispatch(
            "GET", path,
            statement_projection_path=self.projection_path,
            statement_current_fingerprint_path=self.current_fingerprint_path,
            accept="application/json",
        )

    def public_reads_allowed(self) -> bool:
        """False while a challenged version is still part of the current release."""
        response = self._read("/api/v3/statements")
        if response.status != 200:
            return False
        payload = json.loads(response.body)
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return False
        published: set[tuple[str, str]] = set()
        for row in rows:
            if (not isinstance(row, dict)
                    or not isinstance(row.get("statement_id"), str)
                    or not _ID.fullmatch(row["statement_id"])
                    or not isinstance(row.get("version_id"), str)
                    or not _ID.fullmatch(row["version_id"])):
                return False
            published.add((row["statement_id"], row["version_id"]))
        for target in self.store.challenged_statements():
            if (not isinstance(target, (tuple, list)) or len(target) != 2
                    or not all(isinstance(value, str) for value in target)):
                return False
            statement_id, version_id = target
            if (statement_id, version_id) in published:
                if self.store.current_hold(statement_id, version_id) is not False:
                    return False
        return True

    def current_statement(self, statement_id: str) -> dict[str, object] | None:
        response = self._read("/api/v3/statements/" + quote(statement_id, safe=""))
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
