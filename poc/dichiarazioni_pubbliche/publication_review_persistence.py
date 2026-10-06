from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Mapping, Protocol

from dichiarazioni_pubbliche.publication_review_control import (
    PublicationReviewEvent,
    review_event_integrity_valid,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


PUBLICATION_REVIEW_IDENTITY_AUTHORITY_CONTRACT_VERSION = (
    "publication-review-identity-authority-v1"
)


class ReviewerIdentityAuthority(Protocol):
    """Trusted identity authority supplied outside the review-event database.

    The persistence database is not an identity authority. A caller must resolve an opaque
    authority receipt through an independently controlled source. This intentionally leaves
    the concrete operator/admin identity system to the later auth surface.
    """

    def resolve(self, receipt_id: str) -> "ReviewerIdentityAttestation | None": ...


@dataclass(frozen=True)
class ReviewerIdentityAttestation:
    contract_version: str
    receipt_id: str
    actor_ref: str
    credential_fingerprint: str
    review_event_integrity_sha256: str
    record_id: str
    record_version: str
    policy_version: str
    authority_version: str
    issued_at: str
    binding_sha256: str


@dataclass(frozen=True)
class DurableReviewReplay:
    events: tuple[PublicationReviewEvent, ...]
    blockers: tuple[str, ...]

    @property
    def authority_verified(self) -> bool:
        return bool(self.events) and not self.blockers


def _required(value: object, code: str, *, limit: int = 512) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit:
        raise ValueError(code)
    return text


def _sha256(value: object, code: str) -> str:
    text = _required(value, code, limit=64).lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(code)
    return text


def _attestation_material(
    *,
    receipt_id: str,
    actor_ref: str,
    credential_fingerprint: str,
    review_event_integrity_sha256: str,
    record_id: str,
    record_version: str,
    policy_version: str,
    authority_version: str,
    issued_at: str,
) -> dict[str, str]:
    return {
        "contract_version": PUBLICATION_REVIEW_IDENTITY_AUTHORITY_CONTRACT_VERSION,
        "receipt_id": _required(receipt_id, "REVIEW_IDENTITY_RECEIPT_ID_REQUIRED"),
        "actor_ref": _required(actor_ref, "REVIEW_IDENTITY_ACTOR_REQUIRED"),
        "credential_fingerprint": _sha256(
            credential_fingerprint, "REVIEW_IDENTITY_CREDENTIAL_FINGERPRINT_INVALID"
        ),
        "review_event_integrity_sha256": _sha256(
            review_event_integrity_sha256,
            "REVIEW_IDENTITY_EVENT_INTEGRITY_INVALID",
        ),
        "record_id": _required(record_id, "REVIEW_IDENTITY_RECORD_ID_REQUIRED"),
        "record_version": _required(
            record_version, "REVIEW_IDENTITY_RECORD_VERSION_REQUIRED"
        ),
        "policy_version": _required(
            policy_version, "REVIEW_IDENTITY_POLICY_VERSION_REQUIRED"
        ),
        "authority_version": _required(
            authority_version, "REVIEW_IDENTITY_AUTHORITY_VERSION_REQUIRED"
        ),
        "issued_at": _required(issued_at, "REVIEW_IDENTITY_ISSUED_AT_REQUIRED"),
    }


def _binding(material: Mapping[str, str]) -> str:
    encoded = json.dumps(
        dict(material),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_identity_attestation(
    event: PublicationReviewEvent,
    *,
    receipt_id: str,
    authority_version: str,
    issued_at: str,
) -> ReviewerIdentityAttestation:
    material = _attestation_material(
        receipt_id=receipt_id,
        actor_ref=event.actor_ref,
        credential_fingerprint=event.credential_fingerprint,
        review_event_integrity_sha256=event.integrity_sha256,
        record_id=event.record_id,
        record_version=event.record_version,
        policy_version=event.policy_version,
        authority_version=authority_version,
        issued_at=issued_at,
    )
    return ReviewerIdentityAttestation(**material | {"binding_sha256": _binding(material)})


def identity_attestation_blockers(
    event: PublicationReviewEvent,
    attestation: ReviewerIdentityAttestation | None,
) -> tuple[str, ...]:
    if attestation is None:
        return ("REVIEW_IDENTITY_AUTHORITY_RECEIPT_UNKNOWN",)
    if (
        attestation.contract_version
        != PUBLICATION_REVIEW_IDENTITY_AUTHORITY_CONTRACT_VERSION
    ):
        return ("REVIEW_IDENTITY_AUTHORITY_VERSION_MISMATCH",)
    try:
        material = _attestation_material(
            receipt_id=attestation.receipt_id,
            actor_ref=attestation.actor_ref,
            credential_fingerprint=attestation.credential_fingerprint,
            review_event_integrity_sha256=attestation.review_event_integrity_sha256,
            record_id=attestation.record_id,
            record_version=attestation.record_version,
            policy_version=attestation.policy_version,
            authority_version=attestation.authority_version,
            issued_at=attestation.issued_at,
        )
        binding = _sha256(
            attestation.binding_sha256,
            "REVIEW_IDENTITY_AUTHORITY_BINDING_INVALID",
        )
    except ValueError:
        return ("REVIEW_IDENTITY_AUTHORITY_ATTESTATION_INVALID",)
    blockers: list[str] = []
    if binding != _binding(material):
        blockers.append("REVIEW_IDENTITY_AUTHORITY_ATTESTATION_TAMPERED")
    expected = (
        ("actor_ref", event.actor_ref),
        ("credential_fingerprint", event.credential_fingerprint),
        ("review_event_integrity_sha256", event.integrity_sha256),
        ("record_id", event.record_id),
        ("record_version", event.record_version),
        ("policy_version", event.policy_version),
    )
    for field, value in expected:
        if material[field] != value:
            blockers.append("REVIEW_IDENTITY_AUTHORITY_EVENT_MISMATCH")
            break
    return tuple(dict.fromkeys(blockers))


def _event_from_json(raw: object) -> PublicationReviewEvent:
    if not isinstance(raw, dict):
        raise ValueError("PUBLICATION_REVIEW_DURABLE_EVENT_INVALID")
    values = dict(raw)
    reason_codes = values.get("reason_codes") or ()
    if not isinstance(reason_codes, (list, tuple)):
        raise ValueError("PUBLICATION_REVIEW_DURABLE_REASON_CODES_INVALID")
    # `build_review_event()` currently materializes this annotated tuple field as a list
    # because the hash payload is JSON-shaped. Preserve that exact replay representation.
    values["reason_codes"] = [str(value) for value in reason_codes]
    return PublicationReviewEvent(**values)


class PublicationReviewPersistenceStore(PsqlRuntime):
    def append_attested_event(
        self,
        event: PublicationReviewEvent,
        *,
        authority_receipt_id: str,
        authority: ReviewerIdentityAuthority | None,
    ) -> str:
        if not review_event_integrity_valid(event):
            raise ValueError("PUBLICATION_REVIEW_DURABLE_EVENT_TAMPERED")
        receipt_id = _required(
            authority_receipt_id, "REVIEW_IDENTITY_RECEIPT_ID_REQUIRED"
        )
        if authority is None:
            raise ValueError("REVIEW_IDENTITY_AUTHORITY_UNAVAILABLE")
        attestation = authority.resolve(receipt_id)
        blockers = identity_attestation_blockers(event, attestation)
        if blockers:
            raise ValueError(blockers[0])
        assert attestation is not None
        event_json = json.dumps(
            asdict(event),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.run(
            """
            INSERT INTO publication_review_event_durable (
                event_id, record_id, record_version, sequence,
                previous_event_id, previous_integrity_sha256,
                actor_ref, credential_fingerprint, policy_version, reviewed_at_text,
                event_json, integrity_sha256,
                identity_authority_receipt_id, identity_authority_binding_sha256
            ) VALUES (
                :'event_id', :'record_id', :'record_version', :'sequence'::integer,
                NULLIF(:'previous_event_id',''), NULLIF(:'previous_integrity_sha256',''),
                :'actor_ref', :'credential_fingerprint', :'policy_version', :'reviewed_at_text',
                :'event_json'::jsonb, :'integrity_sha256',
                :'authority_receipt_id', :'authority_binding_sha256'
            );
            """,
            event_id=event.event_id,
            record_id=event.record_id,
            record_version=event.record_version,
            sequence=event.sequence,
            previous_event_id=event.previous_event_id or "",
            previous_integrity_sha256=event.previous_integrity_sha256 or "",
            actor_ref=event.actor_ref,
            credential_fingerprint=event.credential_fingerprint,
            policy_version=event.policy_version,
            reviewed_at_text=event.reviewed_at,
            event_json=event_json,
            integrity_sha256=event.integrity_sha256,
            authority_receipt_id=receipt_id,
            authority_binding_sha256=attestation.binding_sha256,
        )
        return event.event_id

    def replay_attested_chain(
        self,
        record_id: str,
        *,
        authority: ReviewerIdentityAuthority | None,
    ) -> DurableReviewReplay:
        clean_record_id = _required(record_id, "PUBLICATION_REVIEW_RECORD_ID_REQUIRED")
        if authority is None:
            return DurableReviewReplay((), ("REVIEW_IDENTITY_AUTHORITY_UNAVAILABLE",))
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'event_json', event_json,
                'event_id', event_id,
                'record_id', record_id,
                'record_version', record_version,
                'sequence', sequence,
                'actor_ref', actor_ref,
                'credential_fingerprint', credential_fingerprint,
                'policy_version', policy_version,
                'integrity_sha256', integrity_sha256,
                'authority_receipt_id', identity_authority_receipt_id,
                'authority_binding_sha256', identity_authority_binding_sha256
            ) ORDER BY sequence)::text, '[]')
            FROM publication_review_event_durable
            WHERE record_id = :'record_id';
            """,
            record_id=clean_record_id,
        )
        rows = json.loads(raw or "[]")
        events: list[PublicationReviewEvent] = []
        blockers: list[str] = []
        for row in rows:
            try:
                event = _event_from_json(row.get("event_json"))
            except (TypeError, ValueError):
                blockers.append("PUBLICATION_REVIEW_DURABLE_EVENT_INVALID")
                continue
            if not review_event_integrity_valid(event):
                blockers.append("PUBLICATION_REVIEW_DURABLE_EVENT_TAMPERED")
                continue
            mirrored = {
                "event_id": event.event_id,
                "record_id": event.record_id,
                "record_version": event.record_version,
                "sequence": event.sequence,
                "actor_ref": event.actor_ref,
                "credential_fingerprint": event.credential_fingerprint,
                "policy_version": event.policy_version,
                "integrity_sha256": event.integrity_sha256,
            }
            if any(row.get(key) != value for key, value in mirrored.items()):
                blockers.append("PUBLICATION_REVIEW_DURABLE_ROW_MISMATCH")
                continue
            receipt_id = str(row.get("authority_receipt_id") or "")
            attestation = authority.resolve(receipt_id) if receipt_id else None
            authority_blockers = identity_attestation_blockers(event, attestation)
            if authority_blockers:
                blockers.extend(authority_blockers)
                continue
            assert attestation is not None
            if row.get("authority_binding_sha256") != attestation.binding_sha256:
                blockers.append("REVIEW_IDENTITY_AUTHORITY_BINDING_MISMATCH")
                continue
            events.append(event)
        if blockers:
            return DurableReviewReplay((), tuple(dict.fromkeys(blockers)))
        return DurableReviewReplay(tuple(events), ())


__all__ = [
    "PUBLICATION_REVIEW_IDENTITY_AUTHORITY_CONTRACT_VERSION",
    "DurableReviewReplay",
    "PublicationReviewPersistenceStore",
    "ReviewerIdentityAttestation",
    "ReviewerIdentityAuthority",
    "build_identity_attestation",
    "identity_attestation_blockers",
]
