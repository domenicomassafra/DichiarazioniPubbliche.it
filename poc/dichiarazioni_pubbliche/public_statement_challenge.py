"""Private, append-only correction and challenge request events."""
from __future__ import annotations
import json
from typing import Mapping
from .public_statement_release_fence import challenge_opened_at, public_release_clear
from .public_statement_authority_common import (
    _CHALLENGE_STATES, _CHALLENGE_CLEAR_STATES, _CHALLENGE_TERMINAL_STATES,
    _CHALLENGE_TRANSITIONS, _SHA256, _digest, _text, _sha, _iso_datetime,
)

def _challenge_request_material(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "statement_id": row["statement_id"], "version_id": row["version_id"],
        "intake_ref": row["intake_ref"],
        "requester_ref_sha256": row["requester_ref_sha256"],
        "reason_sha256": row["reason_sha256"], "created_at": row["created_at"],
    }


def _challenge_event_material(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "request_id": row["request_id"], "event_sequence": row["event_sequence"],
        "previous_event_id": row.get("previous_event_id"),
        "previous_integrity_sha256": row.get("previous_integrity_sha256"),
        "status": row["status"], "reason_code": row["reason_code"],
        "actor_ref": row["actor_ref"], "occurred_at": row["occurred_at"],
    }


def _challenge_transition_valid(previous: str | None, current: str) -> bool:
    if previous is None:
        return current == "OPEN"
    return current in _CHALLENGE_TRANSITIONS.get(previous, frozenset())


def _valid_challenge_chain(request: Mapping[str, object], events: list[dict[str, object]]) -> bool:
    request_integrity = request.get("integrity_sha256")
    if (type(request_integrity) is not str or _SHA256.fullmatch(request_integrity) is None
            or request.get("request_id") != "public-statement-challenge-request:" + request_integrity
            or _digest(_challenge_request_material(request)) != request_integrity):
        return False
    previous_id = None
    previous_hash = None
    previous_status = None
    for sequence, event in enumerate(events, start=1):
        integrity = event.get("integrity_sha256")
        status = event.get("status")
        if (event.get("request_id") != request.get("request_id")
                or event.get("event_sequence") != sequence
                or event.get("previous_event_id") != previous_id
                or event.get("previous_integrity_sha256") != previous_hash
                or status not in _CHALLENGE_STATES
                or not _challenge_transition_valid(previous_status, str(status))
                or type(integrity) is not str or _SHA256.fullmatch(integrity) is None
                or event.get("event_id") != "public-statement-challenge-event:" + integrity
                or _digest(_challenge_event_material(event)) != integrity):
            return False
        previous_id = event["event_id"]
        previous_hash = integrity
        previous_status = str(status)
    return True


_INVENTORY_PAGE = 500
_MAX_INVENTORY_PAGES = 100_000


def _page_size(limit: object) -> int:
    if type(limit) is not int or not 1 <= limit <= _INVENTORY_PAGE:
        raise ValueError("DP468_CHALLENGE_INVENTORY_LIMIT_INVALID")
    return limit


class PublicStatementChallengeStore:
    """Private challenge ledger; unresolved or unreadable requests hold release."""

    def __init__(self, *, store: object):
        if not callable(getattr(store, "run", None)):
            raise ValueError("DP468_CHALLENGE_STORE_REQUIRED")
        self.store = store

    def _request_by_intake_ref(self, intake_ref: str) -> dict[str, object] | None:
        raw = self.store.run(
            """
            SELECT COALESCE(json_agg(row_to_json(request_row))::text, '[]')
            FROM (
                SELECT request_id, statement_id, version_id, intake_ref,
                       requester_ref_sha256, reason_sha256, created_at, integrity_sha256
                FROM public_statement_challenge_request
                WHERE intake_ref = :'intake_ref'
                ORDER BY created_at
                LIMIT 2
            ) request_row;
            """,
            intake_ref=intake_ref,
        )
        rows = json.loads(raw)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("DP468_CHALLENGE_REPLAY_INVALID")
        if len(rows) > 1:
            raise ValueError("DP468_CHALLENGE_INTAKE_AMBIGUOUS")
        return rows[0] if rows else None

    def _request_by_id(self, request_id: str) -> dict[str, object] | None:
        raw = self.store.run(
            """
            SELECT COALESCE(row_to_json(request_row)::text, '')
            FROM (
                SELECT request_id, statement_id, version_id, intake_ref,
                       requester_ref_sha256, reason_sha256, created_at, integrity_sha256
                FROM public_statement_challenge_request
                WHERE request_id = :'request_id'
            ) request_row;
            """,
            request_id=request_id,
        )
        if not raw:
            return None
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError("DP468_CHALLENGE_REPLAY_INVALID")
        return row

    def open_request(
        self, *, statement_id: str, version_id: str, intake_ref: str,
        requester_ref_sha256: str, reason_sha256: str, created_at: str,
        actor_ref: str,
    ) -> str:
        statement = _text(statement_id, "DP468_CHALLENGE_REQUEST_INVALID")
        version = _text(version_id, "DP468_CHALLENGE_REQUEST_INVALID")
        intake = _text(intake_ref, "DP468_CHALLENGE_REQUEST_INVALID")
        requester_hash = _sha(requester_ref_sha256, "DP468_CHALLENGE_REQUEST_INVALID")
        reason_hash = _sha(reason_sha256, "DP468_CHALLENGE_REQUEST_INVALID")
        timestamp = _iso_datetime(created_at, "DP468_CHALLENGE_REQUEST_INVALID")
        actor = _text(actor_ref, "DP468_CHALLENGE_REQUEST_INVALID")
        existing = self._request_by_intake_ref(intake)
        if existing is not None:
            if (existing.get("statement_id") != statement
                    or existing.get("version_id") != version
                    or existing.get("requester_ref_sha256") != requester_hash
                    or existing.get("reason_sha256") != reason_hash):
                raise ValueError("DP468_CHALLENGE_INTAKE_CONFLICT")
            request_id = str(existing.get("request_id", ""))
            events = self._events(request_id)
            if not _valid_challenge_chain(existing, events):
                raise ValueError("DP468_CHALLENGE_CHAIN_INVALID")
            if not events:
                self.append_event(
                    request_id=request_id, status="OPEN",
                    reason_code="CHALLENGE_RECEIVED", actor_ref=actor,
                    occurred_at=str(existing["created_at"]),
                )
            elif (events[0].get("status") != "OPEN"
                    or events[0].get("actor_ref") != actor):
                raise ValueError("DP468_CHALLENGE_INTAKE_CONFLICT")
            return request_id
        material = {
            "statement_id": statement, "version_id": version, "intake_ref": intake,
            "requester_ref_sha256": requester_hash, "reason_sha256": reason_hash,
            "created_at": timestamp,
        }
        integrity = _digest(material)
        request_id = "public-statement-challenge-request:" + integrity
        inserted = self.store.run(
            """
            INSERT INTO public_statement_challenge_request (
                request_id, statement_id, version_id, intake_ref,
                requester_ref_sha256, reason_sha256, created_at, integrity_sha256,
                record_visibility
            ) VALUES (
                :'request_id', :'statement_id', :'version_id', :'intake_ref',
                :'requester_hash', :'reason_hash', :'created_at', :'integrity', 'PRIVATE'
            ) RETURNING request_id;
            """,
            request_id=request_id, statement_id=statement, version_id=version,
            intake_ref=intake, requester_hash=requester_hash, reason_hash=reason_hash,
            created_at=timestamp, integrity=integrity,
        )
        if inserted.strip() != request_id:
            raise ValueError("DP468_CHALLENGE_REQUEST_NOT_PERSISTED")
        self.append_event(
            request_id=request_id, status="OPEN", reason_code="CHALLENGE_RECEIVED",
            actor_ref=actor, occurred_at=timestamp,
        )
        return request_id

    def replay_request(self, request_id: str) -> dict[str, object] | None:
        request = self._request_by_id(_text(request_id, "DP468_CHALLENGE_REPLAY_INVALID"))
        if request is None:
            return None
        events = self._events(request_id)
        if not _valid_challenge_chain(request, events) or not events:
            raise ValueError("DP468_CHALLENGE_CHAIN_INVALID")
        return {
            "request": request,
            "events": events,
            "current_state": events[-1]["status"],
        }

    def challenged_statements(
        self, *, after: tuple[str, str] | None = None, limit: int = _INVENTORY_PAGE,
    ) -> list[tuple[str, str]]:
        """One bounded page of distinct challenged targets, ordered and resumable.

        The ledger is append-only and keeps every historical target, so the
        inventory is paginated: a long life must never turn all public reads
        into a permanent outage through a single capped query.
        """
        size = _page_size(limit)
        if after is not None and (
            not isinstance(after, (tuple, list)) or len(after) != 2
            or not all(isinstance(value, str) and value for value in after)
        ):
            raise ValueError("DP468_CHALLENGE_INVENTORY_CURSOR_INVALID")
        statement, version = after if after is not None else ("", "")
        raw = self.store.run(
            """
            SELECT COALESCE(json_agg(row_to_json(target_row))::text, '[]')
            FROM (
                SELECT DISTINCT statement_id, version_id
                FROM public_statement_challenge_request
                WHERE (statement_id, version_id) > (:'after_statement', :'after_version')
                ORDER BY statement_id, version_id
                LIMIT :'limit'::integer
            ) target_row;
            """,
            after_statement=statement, after_version=version, limit=size,
        )
        rows = json.loads(raw)
        if not isinstance(rows, list) or len(rows) > size:
            raise ValueError("DP468_CHALLENGE_INVENTORY_INVALID")
        result: list[tuple[str, str]] = []
        for row in rows:
            if (not isinstance(row, dict)
                    or not isinstance(row.get("statement_id"), str)
                    or not isinstance(row.get("version_id"), str)
                    or not row["statement_id"] or not row["version_id"]):
                raise ValueError("DP468_CHALLENGE_INVENTORY_INVALID")
            result.append((row["statement_id"], row["version_id"]))
        return result

    def _events(self, request_id: str) -> list[dict[str, object]]:
        raw = self.store.run(
            """
            SELECT COALESCE(json_agg(row_to_json(event_row))::text, '[]')
            FROM (
                SELECT event_id, request_id, event_sequence, previous_event_id,
                       previous_integrity_sha256, status, reason_code, actor_ref,
                       occurred_at, integrity_sha256
                FROM public_statement_challenge_event
                WHERE request_id = :'request_id'
                ORDER BY event_sequence
            ) event_row;
            """,
            request_id=request_id,
        )
        rows = json.loads(raw)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("DP468_CHALLENGE_REPLAY_INVALID")
        return rows

    def append_event(
        self, *, request_id: str, status: str, reason_code: str,
        actor_ref: str, occurred_at: str,
    ) -> str:
        request = _text(request_id, "DP468_CHALLENGE_EVENT_INVALID")
        if status not in _CHALLENGE_STATES:
            raise ValueError("DP468_CHALLENGE_EVENT_INVALID")
        reason = _text(reason_code, "DP468_CHALLENGE_EVENT_INVALID")
        actor = _text(actor_ref, "DP468_CHALLENGE_EVENT_INVALID")
        timestamp = _iso_datetime(occurred_at, "DP468_CHALLENGE_EVENT_INVALID")
        raw_request = self.store.run(
            """
            SELECT COALESCE(row_to_json(request_row)::text, '')
            FROM (
                SELECT request_id, statement_id, version_id, intake_ref,
                       requester_ref_sha256, reason_sha256, created_at, integrity_sha256
                FROM public_statement_challenge_request WHERE request_id = :'request_id'
            ) request_row;
            """,
            request_id=request,
        )
        if not raw_request:
            raise ValueError("DP468_CHALLENGE_REQUEST_NOT_FOUND")
        request_row = json.loads(raw_request)
        events = self._events(request)
        if not _valid_challenge_chain(request_row, events):
            raise ValueError("DP468_CHALLENGE_CHAIN_INVALID")
        previous = events[-1] if events else None
        previous_status = str(previous["status"]) if previous is not None else None
        if not _challenge_transition_valid(previous_status, status):
            if previous is None:
                raise ValueError("DP468_CHALLENGE_MUST_OPEN_FIRST")
            if previous_status in _CHALLENGE_TERMINAL_STATES:
                raise ValueError("DP468_CHALLENGE_ALREADY_CLOSED")
            raise ValueError("DP468_CHALLENGE_TRANSITION_INVALID")
        sequence = int(previous["event_sequence"]) + 1 if previous else 1
        material = {
            "request_id": request, "event_sequence": sequence,
            "previous_event_id": previous.get("event_id") if previous else None,
            "previous_integrity_sha256": previous.get("integrity_sha256") if previous else None,
            "status": status, "reason_code": reason, "actor_ref": actor,
            "occurred_at": timestamp,
        }
        integrity = _digest(material)
        event_id = "public-statement-challenge-event:" + integrity
        inserted = self.store.run(
            """
            INSERT INTO public_statement_challenge_event (
                event_id, request_id, event_sequence, previous_event_id,
                previous_integrity_sha256, status, reason_code, actor_ref,
                occurred_at, integrity_sha256, record_visibility
            ) VALUES (
                :'event_id', :'request_id', :'sequence'::integer,
                NULLIF(:'previous_event_id', ''), NULLIF(:'previous_integrity', ''),
                :'status', :'reason_code', :'actor_ref', :'occurred_at', :'integrity',
                'PRIVATE'
            ) RETURNING event_id;
            """,
            event_id=event_id, request_id=request, sequence=sequence,
            previous_event_id=previous.get("event_id", "") if previous else "",
            previous_integrity=previous.get("integrity_sha256", "") if previous else "",
            status=status, reason_code=reason, actor_ref=actor,
            occurred_at=timestamp, integrity=integrity,
        )
        if inserted.strip() != event_id:
            raise ValueError("DP468_CHALLENGE_EVENT_NOT_PERSISTED")
        persisted = self._events(request)
        if (not _valid_challenge_chain(request_row, persisted)
                or not persisted or persisted[-1].get("event_id") != event_id):
            raise ValueError("DP468_CHALLENGE_EVENT_READBACK_FAILED")
        return event_id

    def public_release_clear(
        self, published: frozenset[tuple[str, str]],
        *, page_size: int = _INVENTORY_PAGE,
        may_serve_cleared: "Callable[[tuple[str, str]], bool] | None" = None,
    ) -> bool | None:
        """Bounded release fence; see public_statement_release_fence."""
        return public_release_clear(
            self, published, page_size=page_size, may_serve_cleared=may_serve_cleared)

    def challenged_at(self, statement_id: str, version_id: str) -> str | None:
        """Most recent challenge instant for an exact target, or None."""
        try:
            return challenge_opened_at(
                self.store,
                _text(statement_id, "DP468_CHALLENGE_REPLAY_INVALID"),
                _text(version_id, "DP468_CHALLENGE_REPLAY_INVALID"),
            )
        except Exception:
            return None

    def current_hold(self, statement_id: str, version_id: str) -> bool | None:
        try:
            raw = self.store.run(
                """
                SELECT COALESCE(json_agg(row_to_json(request_row))::text, '[]')
                FROM (
                    SELECT r.request_id, r.statement_id, r.version_id, r.intake_ref,
                           r.requester_ref_sha256, r.reason_sha256, r.created_at,
                           r.integrity_sha256,
                           COALESCE((
                               SELECT json_agg(row_to_json(event_row))
                               FROM (
                                   SELECT event_id, request_id, event_sequence,
                                          previous_event_id, previous_integrity_sha256,
                                          status, reason_code, actor_ref, occurred_at,
                                          integrity_sha256
                                   FROM public_statement_challenge_event e
                                   WHERE e.request_id = r.request_id
                                   ORDER BY event_sequence
                               ) event_row
                           ), '[]'::json) AS events
                    FROM public_statement_challenge_request r
                    WHERE r.statement_id = :'statement_id' AND r.version_id = :'version_id'
                    ORDER BY r.created_at
                ) request_row;
                """,
                statement_id=statement_id, version_id=version_id,
            )
            requests = json.loads(raw)
            if not isinstance(requests, list):
                return None
            for request in requests:
                if not isinstance(request, dict) or not isinstance(request.get("events"), list):
                    return None
                events = request["events"]
                if not _valid_challenge_chain(request, events):
                    return None
                if not events or events[-1].get("status") not in _CHALLENGE_CLEAR_STATES:
                    return True
            return False
        except Exception:
            return None
