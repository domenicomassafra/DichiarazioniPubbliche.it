"""Opt-in public correction intake with a synchronous publication HOLD fence.

The API can acknowledge a correction only after the durable challenge ledger
and the configured edge purge confirm the withdrawal. A failed dependency
keeps every current public projection surface unavailable.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from urllib.parse import quote, unquote, urlsplit

from .challenge_persistence import ChallengeHoldDisposition
from .challenge_hold_inventory import challenged_findings
from .policy.challenge_workflow import ChallengeKind, ChallengeRole, ChallengeState
from .public_account import SESSION_COOKIE
from .public_api import PublicApiError, PublicApiRequestHandler, dispatch, load_index

MAX_CORRECTION_BYTES = 8192
_FINDING_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_REQUEST_ID = re.compile(r"^challenge-request:[0-9a-f]{64}$")
_STATEMENT_REQUEST_ID = re.compile(r"^public-statement-challenge-request:[0-9a-f]{64}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class LiveCorrectionRequestHandler(PublicApiRequestHandler):
    correction_ledger = None
    correction_enqueue = None
    correction_purge = None
    correction_lock = None
    correction_reserve = None
    statement_challenge_store = None

    def _correction_response(self, status: int, payload: dict[str, object]) -> None:
        self.close_connection = True
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Surrogate-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(encoded)

    def _session_actor(self, *, modifying: bool) -> str | None:
        service = type(self).account_service
        if service is None or len(self.headers.get_all("Cookie", [])) != 1:
            return None
        expected_host = urlsplit(service.site_origin).netloc
        if self.headers.get_all("Host", []) != [expected_host]:
            return None
        if self.headers.get("Transfer-Encoding"):
            return None
        if modifying:
            if (self.headers.get_all("Origin", []) != [service.site_origin]
                    or self.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin"):
                raise PermissionError("CROSS_ORIGIN")
        try:
            session = service.store.get_session(self._account_cookie(SESSION_COOKIE), int(time.time()))
        except Exception:
            return None
        if session is None or len(session) != 3 or not isinstance(session[0], str):
            return None
        if modifying:
            tokens = self.headers.get_all("X-CSRF-Token", [])
            if (len(tokens) != 1 or not isinstance(session[2], str)
                    or not hmac.compare_digest(tokens[0], session[2])):
                raise PermissionError("CSRF")
        return "oidc:" + hashlib.sha256(session[0].encode()).hexdigest()

    def _public_safe(self) -> bool:
        try:
            load_index(type(self).projection_path)
            # The private inventory query also proves the ledger is online.
            # Only challenged findings need individual replay/hold checks;
            # querying every published record would spawn O(N) SQL clients.
            for finding_id in challenged_findings(type(self).correction_ledger):
                hold = type(self).correction_ledger.current_hold_for_finding(finding_id)
                if hold.disposition is not ChallengeHoldDisposition.CLEAR:
                    return False
            statement_path = type(self).statement_projection_path
            fingerprint_path = type(self).statement_current_fingerprint_path
            statement_store = type(self).statement_challenge_store
            if statement_path is not None or fingerprint_path is not None:
                if not statement_path or not fingerprint_path or statement_store is None:
                    return False
                response = dispatch(
                    "GET", "/api/v3/statements",
                    statement_projection_path=statement_path,
                    statement_current_fingerprint_path=fingerprint_path,
                    accept="application/json",
                )
                if response.status != 200:
                    return False
                payload = json.loads(response.body)
                rows = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(rows, list):
                    return False
                published_versions: set[tuple[str, str]] = set()
                for row in rows:
                    if (not isinstance(row, dict)
                            or not isinstance(row.get("statement_id"), str)
                            or not _FINDING_ID.fullmatch(row["statement_id"])
                            or not isinstance(row.get("version_id"), str)
                            or not _FINDING_ID.fullmatch(row["version_id"])):
                        return False
                    published_versions.add((row["statement_id"], row["version_id"]))
                for target in statement_store.challenged_statements():
                    if (not isinstance(target, (tuple, list)) or len(target) != 2
                            or not all(isinstance(value, str) for value in target)):
                        return False
                    statement_id, version_id = target
                    if (statement_id, version_id) in published_versions:
                        if statement_store.current_hold(statement_id, version_id) is not False:
                            return False
            return True
        except Exception:
            return False

    def _current_statement(self, statement_id: str) -> dict[str, object] | None:
        response = dispatch(
            "GET", "/api/v3/statements/" + quote(statement_id, safe=""),
            statement_projection_path=type(self).statement_projection_path,
            statement_current_fingerprint_path=type(self).statement_current_fingerprint_path,
            accept="application/json",
        )
        if response.status == 404:
            return None
        if response.status != 200:
            raise RuntimeError("STATEMENT_V3_RELEASE_UNAVAILABLE")
        payload = json.loads(response.body)
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or data.get("statement_id") != statement_id:
            raise RuntimeError("STATEMENT_V3_RECORD_INVALID")
        return data

    def _unavailable(self) -> None:
        self._correction_response(503, {"error": "PUBLIC_PROJECTION_UNAVAILABLE"})

    def _serve_public(self, method: str) -> None:
        path = urlsplit(self.path).path
        contact_routes = {"/segnalazioni", "/segnalazioni/", "/privacy", "/privacy/", "/accedi", "/accedi/"}
        if self._is_account_path() or path.startswith("/account/") or path in contact_routes:
            return super().do_GET() if method == "GET" else super().do_HEAD()
        with type(self).correction_lock:
            if not self._public_safe():
                return self._unavailable()
            return super().do_GET() if method == "GET" else super().do_HEAD()

    def _status(self, request_id: str) -> None:
        actor = self._session_actor(modifying=False)
        if actor is None:
            return self._correction_response(401, {"error": "AUTHENTICATION_REQUIRED"})
        if _STATEMENT_REQUEST_ID.fullmatch(request_id):
            statement_store = type(self).statement_challenge_store
            if statement_store is None:
                return self._unavailable()
            try:
                replay = statement_store.replay_request(request_id)
                if not isinstance(replay, dict):
                    return self._correction_response(404, {"error": "NOT_FOUND"})
                request = replay.get("request")
                requester_hash = request.get("requester_ref_sha256") if isinstance(request, dict) else None
                expected_hash = hashlib.sha256(actor.encode()).hexdigest()
                if (not isinstance(requester_hash, str)
                        or not hmac.compare_digest(requester_hash, expected_hash)):
                    return self._correction_response(404, {"error": "NOT_FOUND"})
                statement_id = request.get("statement_id")
                version_id = request.get("version_id")
                if not isinstance(statement_id, str) or not isinstance(version_id, str):
                    return self._unavailable()
                hold = statement_store.current_hold(statement_id, version_id)
                if hold is None:
                    return self._unavailable()
                return self._correction_response(200, {
                    "request_id": request_id,
                    "state": "HOLD" if hold else "RESOLVED",
                    "review_state": str(replay.get("current_state", "UNKNOWN")),
                })
            except Exception:
                return self._unavailable()
        if not _REQUEST_ID.fullmatch(request_id):
            return self._correction_response(404, {"error": "NOT_FOUND"})
        try:
            replay = type(self).correction_ledger.replay_request(request_id)
            if (replay.blockers or replay.request is None
                    or replay.request.initiated_by_actor_ref != actor):
                return self._correction_response(404, {"error": "NOT_FOUND"})
            state = replay.current_state
            if state in (ChallengeState.PUBLIC_VERSIONED, ChallengeState.REJECTED):
                disposition = "RESOLVED"
            else:
                hold = type(self).correction_ledger.current_hold_for_finding(replay.request.target_finding_id)
                disposition = "HOLD" if hold.disposition is ChallengeHoldDisposition.HOLD else "UNAVAILABLE"
            return self._correction_response(200 if disposition != "UNAVAILABLE" else 503, {
                "request_id": request_id, "state": disposition,
                "review_state": str(state),
            })
        except Exception:
            return self._unavailable()

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path.startswith("/intake/corrections/") and not urlsplit(self.path).query:
            return self._status(unquote(path.removeprefix("/intake/corrections/")))
        return self._serve_public("GET")

    def do_HEAD(self) -> None:  # noqa: N802
        return self._serve_public("HEAD")

    def do_POST(self) -> None:  # noqa: N802
        if urlsplit(self.path).path != "/intake/corrections":
            return super()._reject()
        if urlsplit(self.path).query:
            return self._correction_response(400, {"error": "INVALID_REQUEST"})
        try:
            actor = self._session_actor(modifying=True)
        except PermissionError:
            return self._correction_response(403, {"error": "REQUEST_FORBIDDEN"})
        if actor is None:
            return self._correction_response(401, {"error": "AUTHENTICATION_REQUIRED"})
        lengths = self.headers.get_all("Content-Length", [])
        normalized_length = (lengths[0].lstrip("0") or "0") if len(lengths) == 1 else ""
        if (len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal()
                or len(normalized_length) > len(str(MAX_CORRECTION_BYTES))
                or int(normalized_length) > MAX_CORRECTION_BYTES
                or self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json"):
            return self._correction_response(413, {"error": "INVALID_CONTENT_LENGTH"})
        try:
            payload = json.loads(self.rfile.read(int(normalized_length)))
        except (UnicodeError, ValueError):
            return self._correction_response(400, {"error": "INVALID_JSON"})
        if not isinstance(payload, dict) or set(payload) not in (
            {"finding_id", "reason"},
            {"statement_id", "version_id", "reason"},
        ):
            return self._correction_response(400, {"error": "INVALID_REQUEST"})
        reason = payload["reason"]
        if (not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 4000
                or _CONTROL.search(reason)):
            return self._correction_response(400, {"error": "INVALID_REQUEST"})
        reason = reason.strip()
        if set(payload) == {"statement_id", "version_id", "reason"}:
            statement_id, version_id = payload["statement_id"], payload["version_id"]
            if (not isinstance(statement_id, str) or not _FINDING_ID.fullmatch(statement_id)
                    or not isinstance(version_id, str) or not _FINDING_ID.fullmatch(version_id)):
                return self._correction_response(400, {"error": "INVALID_REQUEST"})
            with type(self).correction_lock:
                return self._submit_statement_correction(actor, statement_id, version_id, reason)
        finding = payload["finding_id"]
        if not isinstance(finding, str) or not _FINDING_ID.fullmatch(finding):
            return self._correction_response(400, {"error": "INVALID_REQUEST"})
        ledger = type(self).correction_ledger
        with type(self).correction_lock:
            try:
                index = load_index(type(self).projection_path)
                if finding not in index.findings_by_id:
                    return self._correction_response(404, {"error": "NOT_FOUND"})
                if type(self).correction_reserve(actor) is not True:
                    return self._correction_response(429, {"error": "CORRECTION_RATE_LIMITED"})
                current = ledger.current_hold_for_finding(finding)
                if current.disposition is ChallengeHoldDisposition.UNKNOWN:
                    return self._unavailable()
                source_ref = "public-correction:" + hashlib.sha256(
                    json.dumps({"finding_id": finding, "reason": reason}, sort_keys=True).encode()
                ).hexdigest()
                if current.disposition is ChallengeHoldDisposition.HOLD:
                    request_id = current.request_id
                else:
                    initiated = ledger.initiate_request(
                        kind=ChallengeKind.CORRECTION, target_finding_id=finding,
                        source_request_ref=source_ref, actor_ref=actor,
                        actor_role=ChallengeRole.PUBLIC_SUBMITTER, reason=reason,
                    )
                    request_id = initiated.request.request_id
                # A repeated request may recover from a partial queue/CDN
                # failure. Only the *same* principal and identical payload
                # can resume the durable request; unrelated challenges stay
                # confidential and cannot be advanced by this POST.
                replay = ledger.replay_request(request_id)
                request = replay.request
                if (replay.blockers or request is None or request.kind is not ChallengeKind.CORRECTION
                        or request.initiated_by_actor_ref != actor
                        or request.source_request_ref != source_ref
                        or request.target_finding_id != finding):
                    return self._correction_response(409, {"error": "ALREADY_UNDER_REVIEW"})
                hold = ledger.current_hold_for_finding(finding)
                if hold.disposition is not ChallengeHoldDisposition.HOLD:
                    return self._unavailable()
                # A bare public complaint has no superseding Finding yet.
                # DP-303 forbids advancing CORRECTION to REANALYSIS_PENDING
                # without a validated new chain. Keep PRIVATE_RECEIVED/HOLD;
                # the existing queue builds the reanalysis task first.
                if type(self).correction_enqueue(finding, request_id) is not True:
                    return self._unavailable()
                if type(self).correction_purge(finding) is not True:
                    return self._unavailable()
                return self._correction_response(202, {
                    "request_id": request_id,
                    "state": "HOLD", "message": "Rettifica ricevuta; verifica automatica in corso.",
                })
            except Exception:
                return self._unavailable()

    def _submit_statement_correction(
        self, actor: str, statement_id: str, version_id: str, reason: str,
    ) -> None:
        statement_store = type(self).statement_challenge_store
        if (statement_store is None or not type(self).statement_projection_path
                or not type(self).statement_current_fingerprint_path):
            return self._unavailable()
        try:
            current = self._current_statement(statement_id)
            if current is None or current.get("version_id") != version_id:
                return self._correction_response(404, {"error": "NOT_FOUND"})
            if type(self).correction_reserve(actor) is not True:
                return self._correction_response(429, {"error": "CORRECTION_RATE_LIMITED"})
            reason_hash = hashlib.sha256(reason.encode("utf-8")).hexdigest()
            intake_material = json.dumps({
                "statement_id": statement_id,
                "version_id": version_id,
                "reason_sha256": reason_hash,
            }, sort_keys=True, separators=(",", ":")).encode("utf-8")
            intake_ref = "intake:public-statement-correction:" + hashlib.sha256(
                intake_material
            ).hexdigest()
            request_id = statement_store.open_request(
                statement_id=statement_id,
                version_id=version_id,
                intake_ref=intake_ref,
                requester_ref_sha256=hashlib.sha256(actor.encode("utf-8")).hexdigest(),
                reason_sha256=reason_hash,
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                actor_ref=actor,
            )
            hold = statement_store.current_hold(statement_id, version_id)
            if hold is None:
                return self._unavailable()
            if hold is not True:
                return self._correction_response(409, {"error": "CORRECTION_ALREADY_RESOLVED"})
            if type(self).correction_purge("statement-v3:" + statement_id) is not True:
                return self._unavailable()
            return self._correction_response(202, {
                "request_id": request_id,
                "state": "HOLD",
                "message": "Segnalazione registrata; la versione resta sospesa in attesa della verifica.",
            })
        except ValueError as exc:
            if str(exc) == "DP468_CHALLENGE_INTAKE_CONFLICT":
                return self._correction_response(409, {"error": "ALREADY_UNDER_REVIEW"})
            return self._unavailable()
        except Exception:
            return self._unavailable()


def build_live_correction_server(
    projection_path: str,
    *,
    account_service: object,
    correction_ledger: object,
    correction_enqueue: object,
    correction_purge: object,
    correction_reserve: object,
    host: str = "127.0.0.1",
    port: int = 0,
    static_dir: str | None = None,
    account_private_secret_path: str | None = None,
    statement_projection_path: str | None = None,
    statement_current_fingerprint_path: str | None = None,
    statement_challenge_store: object | None = None,
):
    """Pin the existing HTTP/static server before opting into correction intake."""
    if any(item is None for item in (account_service, correction_ledger, correction_enqueue, correction_purge, correction_reserve)):
        raise ValueError("CORRECTION_AUTH_LEDGER_QUEUE_PURGE_QUOTA_REQUIRED")
    v3_configured = (
        statement_projection_path is not None
        or statement_current_fingerprint_path is not None
    )
    if v3_configured and (
        not statement_projection_path or not statement_current_fingerprint_path
        or statement_challenge_store is None
        or not callable(getattr(statement_challenge_store, "challenged_statements", None))
        or not callable(getattr(statement_challenge_store, "current_hold", None))
        or not callable(getattr(statement_challenge_store, "open_request", None))
        or not callable(getattr(statement_challenge_store, "replay_request", None))
    ):
        raise ValueError("STATEMENT_CORRECTION_RELEASE_AND_LEDGER_REQUIRED")
    if statement_challenge_store is not None and not v3_configured:
        raise ValueError("STATEMENT_CORRECTION_V3_RELEASE_REQUIRED")
    from .public_api import build_server

    server = build_server(
        projection_path, account_service=account_service,
        account_private_secret_path=account_private_secret_path,
        host=host, port=port, static_dir=static_dir,
        statement_projection_path=statement_projection_path,
        statement_current_fingerprint_path=statement_current_fingerprint_path,
    )
    base = server.RequestHandlerClass
    attrs = {
        name: getattr(base, name)
        for name in (
            "projection_path", "static_dir", "account_service", "account_private_secret_path",
            "statement_projection_path", "statement_current_fingerprint_path",
        )
    }
    attrs.update({
        "correction_ledger": correction_ledger,
        "correction_enqueue": correction_enqueue,
        "correction_purge": correction_purge,
        "correction_reserve": correction_reserve,
        "statement_challenge_store": statement_challenge_store,
        "correction_lock": threading.RLock(),
    })
    server.RequestHandlerClass = type(
        "BoundLiveCorrectionRequestHandler", (LiveCorrectionRequestHandler,), attrs
    )
    return server
