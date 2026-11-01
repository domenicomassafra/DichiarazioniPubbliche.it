"""Append-only PostgreSQL authority events for public Statement v3."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from typing import Callable, Mapping
from .autonomous_publication import AutonomousProofPacket
from .public_statement_authority_common import (
    AuthorityReviewPacket, _AUTHORITY_KINDS, _MODEL_REVIEW_KINDS,
    _authority_review_evidence, _digest, _text, _iso_datetime,
    _canonical, _review_evidence, _model_review_event_id,
    _validate_release_dispositions, validate_statement_binding,
)
from .public_statement_authority_policy import (
    _valid_authority_chain, _validate_approved_payload,
)

class PublicStatementAuthorityStore:
    """Append-only authority event store over the existing Postgres runtime."""

    def __init__(self, *, store: object):
        if not callable(getattr(store, "run", None)):
            raise ValueError("DP468_AUTHORITY_STORE_REQUIRED")
        self.store = store

    def events(self, statement_id: str, version_id: str) -> list[dict[str, object]]:
        raw = self.store.run(
            """
            SELECT COALESCE(json_agg(row_to_json(event_row))::text, '[]')
            FROM (
                SELECT event_id, statement_id, version_id, authority_kind,
                       event_sequence, previous_event_id, previous_integrity_sha256,
                       decision_id, review_event_id, status, binding, payload,
                       review_evidence, reviewer_ref, reviewed_at, expires_at,
                       integrity_sha256
                FROM public_statement_authority_event
                WHERE statement_id = :'statement_id' AND version_id = :'version_id'
                ORDER BY authority_kind, event_sequence
            ) event_row;
            """,
            statement_id=statement_id, version_id=version_id,
        )
        try:
            rows = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("DP468_AUTHORITY_REPLAY_INVALID") from exc
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("DP468_AUTHORITY_REPLAY_INVALID")
        return rows

    def append_event(
        self, *, binding: Mapping[str, object], authority_kind: str, status: str,
        payload: Mapping[str, object], reviewer_ref: str, reviewed_at: str,
        review_event_id: str | None = None,
        review_evidence: Mapping[str, object] | None = None,
        review_packet: AutonomousProofPacket | None = None,
        authority_review_packet: AuthorityReviewPacket | None = None,
        expires_at: str | None = None,
        verify_authority_review: Callable[[Mapping[str, object]], bool] | None = None,
    ) -> str:
        parsed_binding = validate_statement_binding(binding)
        if authority_kind not in _AUTHORITY_KINDS or status not in {
            "APPROVED", "HELD", "REJECTED", "REVOKED",
        }:
            raise ValueError("DP468_AUTHORITY_EVENT_INVALID")
        parsed_payload = dict(payload)
        parsed_reviewer = _text(reviewer_ref, "DP468_AUTHORITY_EVENT_INVALID")
        parsed_reviewed_at = _iso_datetime(reviewed_at, "DP468_AUTHORITY_EVENT_INVALID")
        parsed_expiry = (
            _iso_datetime(expires_at, "DP468_AUTHORITY_EVENT_INVALID")
            if expires_at is not None else None
        )
        if status == "APPROVED":
            current_time = datetime.now(timezone.utc)
            reviewed_moment = datetime.fromisoformat(parsed_reviewed_at)
            expiry_moment = datetime.fromisoformat(parsed_expiry) if parsed_expiry else None
            if (reviewed_moment > current_time + timedelta(minutes=5)
                    or reviewed_moment < current_time - timedelta(days=31)
                    or expiry_moment is None or expiry_moment <= reviewed_moment
                    or expiry_moment > reviewed_moment + timedelta(days=31)):
                raise ValueError("DP468_AUTHORITY_REVIEW_WINDOW_INVALID")
            _validate_approved_payload(
                authority_kind, parsed_payload, parsed_expiry, now=current_time,
            )
            if authority_kind in _MODEL_REVIEW_KINDS:
                if authority_review_packet is None:
                    raise ValueError("DP468_AUTHORITY_REVIEW_PACKET_REQUIRED")
                evidence = _authority_review_evidence(
                    authority_review_packet, parsed_binding, authority_kind, parsed_payload,
                )
                review_evidence = evidence
                review_event_id = _model_review_event_id(authority_kind, evidence)
            elif authority_kind == "PUBLICATION":
                if review_packet is None or not isinstance(review_evidence, Mapping):
                    raise ValueError("DP468_THREE_RELEASE_DISPOSITIONS_REQUIRED")
                evidence = _review_evidence(review_packet, parsed_binding)
                _validate_release_dispositions(review_evidence, evidence)
                if type(review_event_id) is not str or not review_event_id.strip():
                    raise ValueError("DP468_EXTERNAL_AUTHORITY_REVIEW_REQUIRED")
            elif (type(review_event_id) is not str or not review_event_id.strip()
                    or not isinstance(review_evidence, Mapping)
                    or not isinstance(review_evidence.get("evidence_refs"), list)
                    or not review_evidence["evidence_refs"]):
                raise ValueError("DP468_EXTERNAL_AUTHORITY_REVIEW_REQUIRED")
        else:
            if type(parsed_payload.get("reason_code")) is not str or not parsed_payload["reason_code"].strip():
                raise ValueError("DP468_AUTHORITY_HOLD_REASON_REQUIRED")
            review_evidence = dict(review_evidence or {})
            review_event_id = review_event_id or (
                "public-statement-review-hold:" + _digest({
                    "kind": authority_kind, "status": status, "binding": parsed_binding,
                    "reviewer_ref": parsed_reviewer, "payload": parsed_payload,
                    "reviewed_at": parsed_reviewed_at,
                })
            )
        parsed_review_event_id = _text(review_event_id, "DP468_AUTHORITY_EVENT_INVALID")
        parsed_review_evidence = dict(review_evidence or {})

        existing = self.events(str(parsed_binding["statement_id"]), str(parsed_binding["version_id"]))
        if not _valid_authority_chain(existing):
            raise ValueError("DP468_AUTHORITY_CHAIN_INVALID")
        same_kind = [row for row in existing if row.get("authority_kind") == authority_kind]
        previous = max(same_kind, key=lambda row: int(row["event_sequence"])) if same_kind else None
        sequence = int(previous["event_sequence"]) + 1 if previous else 1
        decision_id = "public-statement-decision:" + _digest({
            "statement_id": parsed_binding["statement_id"],
            "version_id": parsed_binding["version_id"], "authority_kind": authority_kind,
            "status": status, "binding": parsed_binding, "payload": parsed_payload,
            "review_event_id": parsed_review_event_id,
        })
        material = {
            "statement_id": parsed_binding["statement_id"],
            "version_id": parsed_binding["version_id"],
            "authority_kind": authority_kind,
            "event_sequence": sequence,
            "previous_event_id": previous.get("event_id") if previous else None,
            "previous_integrity_sha256": previous.get("integrity_sha256") if previous else None,
            "decision_id": decision_id,
            "review_event_id": parsed_review_event_id,
            "status": status,
            "binding": parsed_binding,
            "payload": parsed_payload,
            "review_evidence": parsed_review_evidence,
            "reviewer_ref": parsed_reviewer,
            "reviewed_at": parsed_reviewed_at,
            "expires_at": parsed_expiry,
        }
        integrity = _digest(material)
        event_id = "public-statement-authority:" + integrity
        if status == "APPROVED" and authority_kind not in _MODEL_REVIEW_KINDS:
            review_row = {
                **material, "event_id": event_id, "integrity_sha256": integrity,
            }
            if (not callable(verify_authority_review)
                    or verify_authority_review(review_row) is not True):
                raise ValueError("DP468_EXTERNAL_AUTHORITY_REVIEW_INVALID")
        inserted = self.store.run(
            """
            INSERT INTO public_statement_authority_event (
                event_id, statement_id, version_id, authority_kind, event_sequence,
                previous_event_id, previous_integrity_sha256, decision_id,
                review_event_id, status, binding, payload, review_evidence,
                reviewer_ref, reviewed_at, expires_at, integrity_sha256, record_visibility
            ) VALUES (
                :'event_id', :'statement_id', :'version_id', :'authority_kind',
                :'event_sequence'::integer, NULLIF(:'previous_event_id', ''),
                NULLIF(:'previous_integrity_sha256', ''), :'decision_id',
                :'review_event_id', :'status', :'binding'::jsonb, :'payload'::jsonb,
                :'review_evidence'::jsonb, :'reviewer_ref', :'reviewed_at',
                NULLIF(:'expires_at', ''), :'integrity_sha256', 'PRIVATE'
            ) RETURNING event_id;
            """,
            event_id=event_id, statement_id=parsed_binding["statement_id"],
            version_id=parsed_binding["version_id"], authority_kind=authority_kind,
            event_sequence=sequence,
            previous_event_id=previous.get("event_id", "") if previous else "",
            previous_integrity_sha256=previous.get("integrity_sha256", "") if previous else "",
            decision_id=decision_id, review_event_id=parsed_review_event_id,
            status=status, binding=_canonical(parsed_binding), payload=_canonical(parsed_payload),
            review_evidence=_canonical(parsed_review_evidence), reviewer_ref=parsed_reviewer,
            reviewed_at=parsed_reviewed_at, expires_at=parsed_expiry or "",
            integrity_sha256=integrity,
        )
        if inserted.strip() != event_id:
            raise ValueError("DP468_AUTHORITY_EVENT_NOT_PERSISTED")
        persisted = self.events(
            str(parsed_binding["statement_id"]), str(parsed_binding["version_id"]),
        )
        same_kind_persisted = [
            row for row in persisted if row.get("authority_kind") == authority_kind
        ]
        if (not _valid_authority_chain(persisted) or not same_kind_persisted
                or same_kind_persisted[-1].get("event_id") != event_id):
            raise ValueError("DP468_AUTHORITY_EVENT_READBACK_FAILED")
        return event_id

    def current_attestations(
        self, *, binding: Mapping[str, object], review_packet: AutonomousProofPacket,
        authority_review_packets: Mapping[str, AuthorityReviewPacket],
        verify_authority_review: Callable[[Mapping[str, object]], bool] | None,
        now: datetime | None = None,
    ) -> dict[str, dict[str, object]] | None:
        try:
            parsed_binding = validate_statement_binding(binding)
            evidence = _review_evidence(review_packet, parsed_binding)
            if (not isinstance(authority_review_packets, Mapping)
                    or set(authority_review_packets) != set(_MODEL_REVIEW_KINDS)):
                return None
            rows = self.events(
                str(parsed_binding["statement_id"]), str(parsed_binding["version_id"]),
            )
            if not rows or not _valid_authority_chain(rows):
                return None
            latest: dict[str, dict[str, object]] = {}
            for row in rows:
                latest[str(row["authority_kind"])] = row
            if set(latest) != set(_AUTHORITY_KINDS):
                return None
            current_time = now or datetime.now(timezone.utc)
            if current_time.tzinfo is None or current_time.utcoffset() is None:
                return None
            current_time = current_time.astimezone(timezone.utc)
            result: dict[str, dict[str, object]] = {}
            decision_ids: set[str] = set()
            review_ids: set[str] = set()
            for kind in _AUTHORITY_KINDS:
                row = latest[kind]
                if (row.get("status") != "APPROVED" or row.get("binding") != parsed_binding
                        or type(row.get("decision_id")) is not str
                        or type(row.get("review_event_id")) is not str
                        or type(row.get("payload")) is not dict):
                    return None
                reviewed_at = datetime.fromisoformat(str(row["reviewed_at"]).replace("Z", "+00:00"))
                if (reviewed_at.tzinfo is None
                        or reviewed_at > current_time + timedelta(minutes=5)
                        or reviewed_at < current_time - timedelta(days=31)):
                    return None
                expiry = row.get("expires_at")
                if not isinstance(expiry, str) or not expiry.strip():
                    return None
                parsed_expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                if parsed_expiry.tzinfo is None or parsed_expiry <= current_time:
                    return None
                payload = row["payload"]
                _validate_approved_payload(kind, payload, expiry, now=current_time)
                if kind in _MODEL_REVIEW_KINDS:
                    authority_evidence = _authority_review_evidence(
                        authority_review_packets[kind], parsed_binding, kind, payload,
                    )
                    if (row.get("review_evidence") != authority_evidence
                            or row.get("review_event_id") != _model_review_event_id(
                                kind, authority_evidence,
                            )):
                        return None
                else:
                    if kind == "PUBLICATION":
                        _validate_release_dispositions(row.get("review_evidence"), evidence)
                    if (not callable(verify_authority_review)
                            or verify_authority_review(row) is not True):
                        return None
                decision_id = str(row["decision_id"])
                review_id = str(row["review_event_id"])
                if decision_id in decision_ids or review_id in review_ids:
                    return None
                decision_ids.add(decision_id)
                review_ids.add(review_id)
                result[kind.lower()] = {
                    **parsed_binding, **payload,
                    "status": "APPROVED", "decision_id": decision_id,
                    "review_event_id": review_id, "expires_at": expiry,
                }
            return result
        except Exception:
            return None
