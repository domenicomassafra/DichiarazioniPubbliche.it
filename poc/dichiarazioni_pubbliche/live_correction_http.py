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
from http import HTTPStatus
from urllib.parse import unquote, urlsplit

from .challenge_persistence import ChallengeHoldDisposition
from .challenge_hold_inventory import challenged_findings
from .policy.challenge_workflow import ChallengeKind, ChallengeRole, ChallengeState
from .public_account import SESSION_COOKIE
from .public_api import PublicApiError, PublicApiRequestHandler, load_index

MAX_CORRECTION_BYTES = 8192
_FINDING_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_REQUEST_ID = re.compile(r"^challenge-request:[0-9a-f]{64}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class LiveCorrectionRequestHandler(PublicApiRequestHandler):
    correction_ledger = None
    correction_enqueue = None
    correction_purge = None
    correction_lock = None
    correction_reserve = None

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
            return True
        except Exception:
            return False

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
        if not isinstance(payload, dict) or set(payload) != {"finding_id", "reason"}:
            return self._correction_response(400, {"error": "INVALID_REQUEST"})
        finding, reason = payload["finding_id"], payload["reason"]
        if (not isinstance(finding, str) or not _FINDING_ID.fullmatch(finding)
                or not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 4000
                or _CONTROL.search(reason)):
            return self._correction_response(400, {"error": "INVALID_REQUEST"})
        reason = reason.strip()
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
):
    """Pin the existing HTTP/static server before opting into correction intake."""
    if any(item is None for item in (account_service, correction_ledger, correction_enqueue, correction_purge, correction_reserve)):
        raise ValueError("CORRECTION_AUTH_LEDGER_QUEUE_PURGE_QUOTA_REQUIRED")
    from .public_api import build_server

    server = build_server(
        projection_path, account_service=account_service,
        account_private_secret_path=account_private_secret_path,
        host=host, port=port, static_dir=static_dir,
    )
    base = server.RequestHandlerClass
    attrs = {
        name: getattr(base, name)
        for name in ("projection_path", "static_dir", "account_service", "account_private_secret_path")
    }
    attrs.update({
        "correction_ledger": correction_ledger,
        "correction_enqueue": correction_enqueue,
        "correction_purge": correction_purge,
        "correction_reserve": correction_reserve,
        "correction_lock": threading.RLock(),
    })
    server.RequestHandlerClass = type(
        "BoundLiveCorrectionRequestHandler", (LiveCorrectionRequestHandler,), attrs
    )
    return server
