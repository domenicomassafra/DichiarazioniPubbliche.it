"""Release fence against a single PostgreSQL snapshot of published challenges.

An append-only challenge history may grow indefinitely. Only requests for the
versions in the current release are read; one SQL statement gives them one
MVCC snapshot, including their complete integrity chains.
"""
from __future__ import annotations

import json
from typing import Callable

from .public_statement_authority_common import _CHALLENGE_CLEAR_STATES


def _valid_target(target: object) -> bool:
    return (type(target) is tuple and len(target) == 2
            and all(isinstance(value, str) and value for value in target))


def public_release_clear(
    store: object, published: object, *,
    validate_chain: Callable[[dict, list[dict]], bool],
    may_serve_cleared: Callable[[tuple[str, str], str], bool] | None = None,
) -> bool | None:
    """True only when all matching challenge chains clear the exact release."""
    if (not isinstance(published, frozenset)
            or any(not _valid_target(target) for target in published)):
        return None
    try:
        # No keyset traversal: a newly inserted earlier target cannot be missed
        # between queries. Unrelated historical challenges are never scanned.
        raw = store.run(
            """
            WITH release_targets AS (
                SELECT statement_id, version_id
                FROM jsonb_to_recordset(:'published'::jsonb)
                    AS target(statement_id text, version_id text)
            )
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
                JOIN release_targets t USING (statement_id, version_id)
                ORDER BY r.created_at, r.request_id
            ) request_row;
            """,
            published=json.dumps([
                {"statement_id": statement, "version_id": version}
                for statement, version in sorted(published)
            ], separators=(",", ":")),
        )
        requests = json.loads(raw)
        if not isinstance(requests, list):
            return None
        for request in requests:
            if not isinstance(request, dict):
                return None
            events = request.get("events")
            if not isinstance(events, list) or not validate_chain(request, events):
                return None
            if not events or events[-1].get("status") not in _CHALLENGE_CLEAR_STATES:
                return False
            target = (request.get("statement_id"), request.get("version_id"))
            if (may_serve_cleared is not None
                    and may_serve_cleared(target, request.get("created_at")) is not True):
                return False
        return True
    except Exception:
        return None
