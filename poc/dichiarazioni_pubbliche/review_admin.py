from __future__ import annotations

import argparse
import hashlib
import json
import os
from typing import Any

from dichiarazioni_pubbliche.correction_runtime import (
    deterministic_correction_id,
    deterministic_right_of_reply_id,
    normalize_evidence_urls,
    right_of_reply_source_hash,
)
from dichiarazioni_pubbliche.queue_runtime import QueueRuntimeStore
from dichiarazioni_pubbliche.reanalysis_runtime import deterministic_reanalysis_trigger
from dichiarazioni_pubbliche.speaker_runtime import make_speaker_candidate
from dichiarazioni_pubbliche.text_provenance import make_text_provenance_candidate


def deterministic_review_event_id(
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_ref: str,
    reason: str | None,
) -> str:
    material = "\0".join(
        (
            entity_type.strip(),
            entity_id.strip(),
            action.strip(),
            actor_ref.strip(),
            (reason or "").strip(),
        )
    ).encode()
    return "review:" + hashlib.sha256(material).hexdigest()


def _parse_rule(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("verification rule must be a JSON object")
    return parsed


def approve_evidence(
    store: QueueRuntimeStore,
    *,
    claim_id: str,
    evidence_id: str,
    retrieval_version: str,
    actor_ref: str,
    reason: str | None,
) -> str:
    entity_id = f"{claim_id}|{evidence_id}|{retrieval_version}"
    event_id = deterministic_review_event_id(
        entity_type="CLAIM_EVIDENCE_CANDIDATE",
        entity_id=entity_id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=reason,
    )
    if not store.approve_claim_evidence_with_review(
        claim_id=claim_id,
        evidence_id=evidence_id,
        retrieval_version=retrieval_version,
        event_id=event_id,
        actor_ref=actor_ref,
        reason=reason,
    ):
        raise RuntimeError("CLAIM_EVIDENCE_CANDIDATE_NOT_FOUND")
    return event_id


def approve_observation(
    store: QueueRuntimeStore,
    *,
    observation_id: str,
    actor_ref: str,
    reason: str | None,
) -> str:
    event_id = deterministic_review_event_id(
        entity_type="EVIDENCE_OBSERVATION",
        entity_id=observation_id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=reason,
    )
    if not store.approve_evidence_observation_with_review(
        observation_id=observation_id,
        event_id=event_id,
        actor_ref=actor_ref,
        reason=reason,
    ):
        raise RuntimeError("EVIDENCE_OBSERVATION_NOT_FOUND")
    return event_id


def enqueue_verification(
    store: QueueRuntimeStore,
    *,
    claim_id: str,
    verification_kind: str,
    verification_rule: dict[str, Any],
    statement_date: str | None,
) -> str:
    context = store.claim_context(claim_id)
    canonical_cutoff = str(context.get("statement_date") or "").strip()
    requested_cutoff = str(statement_date or "").strip()
    if (
        canonical_cutoff
        and requested_cutoff
        and requested_cutoff != canonical_cutoff
    ):
        raise RuntimeError("VERIFICATION_STATEMENT_DATE_MISMATCH")
    cutoff = canonical_cutoff or requested_cutoff
    if not cutoff:
        raise RuntimeError("VERIFICATION_STATEMENT_DATE_MISSING")
    variant_payload = {
        "kind": verification_kind,
        "rule": verification_rule,
        "statement_date": cutoff,
    }
    variant = hashlib.sha256(
        json.dumps(
            variant_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    job_id, _ = store.enqueue_followup(
        content_id=context["content_id"],
        job_type="VERIFY_CLAIM",
        payload={
            "claim_id": claim_id,
            "verification_kind": verification_kind,
            "verification_rule": verification_rule,
            "statement_date": cutoff,
            "estimated_cost_usd": 0.0,
        },
        variant=variant,
    )
    return job_id


def enqueue_reanalysis_trigger(
    store: QueueRuntimeStore,
    *,
    claim_id: str,
    trigger_type: str,
    source_type: str,
    source_id: str,
    source_hash: str | None,
) -> str:
    context = store.claim_context(claim_id)
    trigger = deterministic_reanalysis_trigger(
        claim_id=claim_id,
        trigger_type=trigger_type,
        source_type=source_type,
        source_id=source_id,
        source_hash=source_hash,
    )
    job_id, _ = store.enqueue_followup(
        content_id=context["content_id"],
        job_type="REGISTER_REANALYSIS",
        payload={
            "claim_id": claim_id,
            "trigger_type": trigger.trigger_type,
            "source_type": trigger.source_type,
            "source_id": trigger.source_id,
            "source_hash": trigger.source_hash,
            "estimated_cost_usd": 0.0,
        },
        variant=trigger.trigger_id,
    )
    return job_id


def register_person(
    store: QueueRuntimeStore,
    *,
    person_id: str,
    canonical_name: str,
    public_role: str | None,
    country_code: str | None,
) -> str:
    if not store.register_public_person(
        person_id=person_id,
        canonical_name=canonical_name,
        public_role=public_role,
        country_code=country_code,
    ):
        raise RuntimeError("PERSON_ID_CONFLICT")
    return person_id


def register_organization(
    store: QueueRuntimeStore,
    *,
    organization_id: str,
    canonical_name: str,
    organization_type: str | None,
    country_code: str | None,
    canonical_url: str | None,
) -> str:
    if not store.register_organization(
        organization_id=organization_id,
        canonical_name=canonical_name,
        organization_type=organization_type,
        country_code=country_code,
        canonical_url=canonical_url,
    ):
        raise RuntimeError("ORGANIZATION_ID_CONFLICT")
    return organization_id


def approve_person_role_interval(
    store: QueueRuntimeStore,
    *,
    interval_id: str,
    person_id: str,
    organization_id: str,
    role: str,
    start_date: str,
    end_date: str | None,
    is_public_role: bool,
    source_ref: dict[str, Any],
    actor_ref: str,
    reason: str | None,
    supersedes_id: str | None = None,
) -> str:
    event_id = deterministic_review_event_id(
        entity_type="PERSON_ROLE_INTERVAL",
        entity_id=interval_id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=reason,
    )
    if not store.approve_person_role_interval_with_review(
        interval_id=interval_id,
        person_id=person_id,
        organization_id=organization_id,
        role=role,
        start_date=start_date,
        end_date=end_date,
        is_public_role=is_public_role,
        source_ref=source_ref,
        event_id=event_id,
        actor_ref=actor_ref,
        reason=reason,
        supersedes_id=supersedes_id,
    ):
        raise RuntimeError("PERSON_ROLE_INTERVAL_NOT_FOUND")
    return event_id


def add_speaker_candidate(
    store: QueueRuntimeStore,
    *,
    content_id: str,
    person_id: str,
    start_ms: int,
    end_ms: int,
    attribution_method: str,
    speaker_label: str | None,
    source_ref: dict[str, Any],
    confidence: float | None,
) -> str:
    candidate = make_speaker_candidate(
        content_id=content_id,
        person_id=person_id,
        start_ms=start_ms,
        end_ms=end_ms,
        attribution_method=attribution_method,
        speaker_label=speaker_label,
        source_ref=source_ref,
        confidence=confidence,
    )
    store.insert_speaker_identity_candidate(
        candidate_id=candidate.candidate_id,
        content_id=candidate.content_id,
        person_id=candidate.person_id,
        start_ms=candidate.start_ms,
        end_ms=candidate.end_ms,
        speaker_label=candidate.speaker_label,
        attribution_method=candidate.attribution_method,
        attribution_version=candidate.attribution_version,
        source_ref=candidate.source_ref,
        confidence=candidate.confidence,
    )
    return candidate.candidate_id


def add_text_provenance_candidate(
    store: QueueRuntimeStore,
    *,
    claim_id: str,
    content_id: str,
    person_id: str,
    selector_type: str,
    quote_sha256: str,
    source_sha256: str | None,
    start_char: int | None,
    end_char: int | None,
    attribution_method: str,
    source_ref: dict[str, Any],
) -> str:
    candidate = make_text_provenance_candidate(
        claim_id=claim_id,
        content_id=content_id,
        person_id=person_id,
        selector_type=selector_type,
        quote_sha256=quote_sha256,
        source_sha256=source_sha256,
        start_char=start_char,
        end_char=end_char,
        attribution_method=attribution_method,
        source_ref=source_ref,
    )
    if not store.insert_claim_text_provenance(
        candidate_id=candidate.candidate_id,
        claim_id=candidate.claim_id,
        content_id=candidate.content_id,
        person_id=candidate.person_id,
        selector_type=candidate.selector_type,
        quote_sha256=candidate.quote_sha256,
        source_sha256=candidate.source_sha256,
        start_char=candidate.start_char,
        end_char=candidate.end_char,
        attribution_method=candidate.attribution_method,
        attribution_version=candidate.attribution_version,
        source_ref=candidate.source_ref,
    ):
        raise RuntimeError("CLAIM_TEXT_PROVENANCE_REFUSED")
    return candidate.candidate_id


def approve_text_provenance_candidate(
    store: QueueRuntimeStore,
    *,
    candidate_id: str,
    actor_ref: str,
    reason: str | None,
) -> str:
    event_id = deterministic_review_event_id(
        entity_type="CLAIM_TEXT_PROVENANCE",
        entity_id=candidate_id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=reason,
    )
    if not store.approve_claim_text_provenance_with_review(
        candidate_id=candidate_id,
        event_id=event_id,
        actor_ref=actor_ref,
        reason=reason,
    ):
        raise RuntimeError("CLAIM_TEXT_PROVENANCE_APPROVAL_REFUSED")
    return event_id


def approve_speaker_candidate(
    store: QueueRuntimeStore,
    *,
    candidate_id: str,
    actor_ref: str,
    reason: str | None,
) -> str:
    event_id = deterministic_review_event_id(
        entity_type="SPEAKER_IDENTITY_CANDIDATE",
        entity_id=candidate_id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=reason,
    )
    if not store.approve_speaker_identity_with_review(
        candidate_id=candidate_id,
        event_id=event_id,
        actor_ref=actor_ref,
        reason=reason,
    ):
        raise RuntimeError("SPEAKER_IDENTITY_APPROVAL_REFUSED")
    return event_id


def publish_finding(
    store: QueueRuntimeStore,
    *,
    finding_id: str,
    actor_ref: str,
    reason: str | None,
) -> str:
    event_id = deterministic_review_event_id(
        entity_type="FINDING",
        entity_id=finding_id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=reason,
    )
    if not store.publish_finding_with_review(
        finding_id=finding_id,
        event_id=event_id,
        actor_ref=actor_ref,
        reason=reason,
    ):
        raise RuntimeError("FINDING_PUBLICATION_GUARD_REFUSED")
    return event_id


def approve_relation_candidate(
    store: QueueRuntimeStore,
    *,
    relation_id: str,
    actor_ref: str,
    reason: str | None,
    trigger_reanalysis: bool = True,
) -> str:
    """Approve a relation candidate through the explicit review ledger.

    Approval advances the candidate state and appends the review event. It
    never makes the relation public: public visibility is derived from the
    ledger plus both published endpoint findings at projection time. When a
    relation changes the public record of either claim, both endpoint claims
    are re-enqueued for reanalysis.
    """
    event_id = deterministic_review_event_id(
        entity_type="RELATION_CANDIDATE",
        entity_id=relation_id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=reason,
    )
    approved = store.approve_relation_candidate_with_review(
        relation_id=relation_id,
        event_id=event_id,
        actor_ref=actor_ref,
        reason=reason,
    )
    if not approved:
        raise RuntimeError("RELATION_APPROVAL_GUARD_REFUSED")
    if trigger_reanalysis:
        for claim_id in (
            approved["subject_claim_id"],
            approved["object_claim_id"],
        ):
            enqueue_reanalysis_trigger(
                store,
                claim_id=claim_id,
                trigger_type="RELATION_APPROVED",
                source_type="RELATION_CANDIDATE",
                source_id=relation_id,
                source_hash=None,
            )
    return event_id


def record_right_of_reply(
    store: QueueRuntimeStore,
    *,
    finding_id: str,
    submitter_name: str | None,
    submitter_role: str | None,
    body: str,
    evidence_urls: list[str],
) -> str:
    context = store.finding_context(finding_id)
    normalized_urls = list(normalize_evidence_urls(evidence_urls))
    reply_id = deterministic_right_of_reply_id(
        finding_id=finding_id,
        body=body,
        submitter_name=submitter_name,
        submitter_role=submitter_role,
        evidence_urls=normalized_urls,
    )
    store.insert_right_of_reply(
        reply_id=reply_id,
        finding_id=finding_id,
        submitter_name=submitter_name,
        submitter_role=submitter_role,
        body=body.strip(),
        evidence_urls=normalized_urls,
    )
    job_id = enqueue_reanalysis_trigger(
        store,
        claim_id=context["claim_id"],
        trigger_type="RIGHT_OF_REPLY",
        source_type="RIGHT_OF_REPLY",
        source_id=reply_id,
        source_hash=right_of_reply_source_hash(
            body=body,
            evidence_urls=normalized_urls,
        ),
    )
    if not store.attach_reply_reanalysis_job(
        reply_id=reply_id,
        job_id=job_id,
    ):
        raise RuntimeError("RIGHT_OF_REPLY_REANALYSIS_LINK_FAILED")
    return reply_id


def publish_right_of_reply(
    store: QueueRuntimeStore,
    *,
    reply_id: str,
    actor_ref: str,
    reason: str | None,
) -> str:
    event_id = deterministic_review_event_id(
        entity_type="RIGHT_OF_REPLY",
        entity_id=reply_id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=reason,
    )
    if not store.publish_right_of_reply_with_review(
        reply_id=reply_id,
        event_id=event_id,
        actor_ref=actor_ref,
        reason=reason,
    ):
        raise RuntimeError("RIGHT_OF_REPLY_PUBLICATION_REFUSED")
    return event_id


def record_correction(
    store: QueueRuntimeStore,
    *,
    finding_id: str,
    previous_finding_id: str,
    reason: str,
    changed_fields: dict[str, Any],
) -> str:
    context = store.finding_context(finding_id)
    correction_id = deterministic_correction_id(
        finding_id=finding_id,
        previous_finding_id=previous_finding_id,
        reason=reason,
        changed_fields=changed_fields,
    )
    if not store.insert_correction(
        correction_id=correction_id,
        finding_id=finding_id,
        previous_finding_id=previous_finding_id,
        reason=reason.strip(),
        changed_fields=changed_fields,
    ):
        raise RuntimeError("CORRECTION_CHAIN_REFUSED")
    enqueue_reanalysis_trigger(
        store,
        claim_id=context["claim_id"],
        trigger_type="CORRECTION",
        source_type="CORRECTION",
        source_id=correction_id,
        source_hash=hashlib.sha256(
            json.dumps(
                {
                    "reason": reason.strip(),
                    "changed_fields": changed_fields,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    )
    return correction_id


def publish_correction(
    store: QueueRuntimeStore,
    *,
    correction_id: str,
    actor_ref: str,
    reason: str | None,
) -> str:
    event_id = deterministic_review_event_id(
        entity_type="CORRECTION",
        entity_id=correction_id,
        action="APPROVED",
        actor_ref=actor_ref,
        reason=reason,
    )
    if not store.publish_correction_with_review(
        correction_id=correction_id,
        event_id=event_id,
        actor_ref=actor_ref,
        reason=reason,
    ):
        raise RuntimeError("CORRECTION_PUBLICATION_REFUSED")
    return event_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Explicit Dichiarazioni Pubbliche evidence/verification review operations."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"),
    )
    parser.add_argument("--actor", default="local-operator")
    sub = parser.add_subparsers(dest="command", required=True)

    evidence = sub.add_parser("approve-evidence")
    evidence.add_argument("--claim-id", required=True)
    evidence.add_argument("--evidence-id", required=True)
    evidence.add_argument("--retrieval-version", required=True)
    evidence.add_argument("--reason")

    observation = sub.add_parser("approve-observation")
    observation.add_argument("--observation-id", required=True)
    observation.add_argument("--reason")

    verify_parser = sub.add_parser("enqueue-verification")
    verify_parser.add_argument("--claim-id", required=True)
    verify_parser.add_argument("--kind", required=True)
    verify_parser.add_argument("--rule-json", required=True)
    verify_parser.add_argument("--statement-date")

    reanalysis = sub.add_parser("trigger-reanalysis")
    reanalysis.add_argument("--claim-id", required=True)
    reanalysis.add_argument("--trigger-type", required=True)
    reanalysis.add_argument("--source-type", required=True)
    reanalysis.add_argument("--source-id", required=True)
    reanalysis.add_argument("--source-hash")

    person = sub.add_parser("register-person")
    person.add_argument("--person-id", required=True)
    person.add_argument("--name", required=True)
    person.add_argument("--role")
    person.add_argument("--country-code")

    organization = sub.add_parser("register-organization")
    organization.add_argument("--organization-id", required=True)
    organization.add_argument("--name", required=True)
    organization.add_argument("--organization-type")
    organization.add_argument("--country-code")
    organization.add_argument("--canonical-url")

    role_interval = sub.add_parser("approve-role-interval")
    role_interval.add_argument("--interval-id", required=True)
    role_interval.add_argument("--person-id", required=True)
    role_interval.add_argument("--organization-id", required=True)
    role_interval.add_argument("--role", required=True)
    role_interval.add_argument("--start-date", required=True)
    role_interval.add_argument("--end-date")
    role_interval.add_argument("--source-ref-json", required=True)
    role_interval.add_argument("--supersedes-id")
    role_interval.add_argument("--reason")

    speaker = sub.add_parser("add-speaker-candidate")
    speaker.add_argument("--content-id", required=True)
    speaker.add_argument("--person-id", required=True)
    speaker.add_argument("--start-ms", type=int, required=True)
    speaker.add_argument("--end-ms", type=int, required=True)
    speaker.add_argument("--method", required=True)
    speaker.add_argument("--speaker-label")
    speaker.add_argument("--source-ref-json", default="{}")
    speaker.add_argument("--confidence", type=float)

    speaker_approve = sub.add_parser("approve-speaker")
    speaker_approve.add_argument("--candidate-id", required=True)
    speaker_approve.add_argument("--reason")

    text_provenance = sub.add_parser("add-text-provenance")
    text_provenance.add_argument("--claim-id", required=True)
    text_provenance.add_argument("--content-id", required=True)
    text_provenance.add_argument("--person-id", required=True)
    text_provenance.add_argument("--selector-type", required=True)
    text_provenance.add_argument("--quote-sha256", required=True)
    text_provenance.add_argument("--source-sha256")
    text_provenance.add_argument("--start-char", type=int)
    text_provenance.add_argument("--end-char", type=int)
    text_provenance.add_argument("--method", required=True)
    text_provenance.add_argument("--source-ref-json", default="{}")

    text_provenance_approve = sub.add_parser("approve-text-provenance")
    text_provenance_approve.add_argument("--candidate-id", required=True)
    text_provenance_approve.add_argument("--reason")

    finding_publish = sub.add_parser("publish-finding")
    finding_publish.add_argument("--finding-id", required=True)
    finding_publish.add_argument("--reason")

    reply = sub.add_parser("record-reply")
    reply.add_argument("--finding-id", required=True)
    reply.add_argument("--submitter-name")
    reply.add_argument("--submitter-role")
    reply.add_argument("--body", required=True)
    reply.add_argument("--evidence-url", action="append", default=[])

    reply_publish = sub.add_parser("publish-reply")
    reply_publish.add_argument("--reply-id", required=True)
    reply_publish.add_argument("--reason")

    correction = sub.add_parser("record-correction")
    correction.add_argument("--finding-id", required=True)
    correction.add_argument("--previous-finding-id", required=True)
    correction.add_argument("--reason", required=True)
    correction.add_argument("--changed-fields-json", required=True)

    correction_publish = sub.add_parser("publish-correction")
    correction_publish.add_argument("--correction-id", required=True)
    correction_publish.add_argument("--reason")

    args = parser.parse_args()
    store = QueueRuntimeStore(args.database_url)
    if args.command == "approve-evidence":
        result = approve_evidence(
            store,
            claim_id=args.claim_id,
            evidence_id=args.evidence_id,
            retrieval_version=args.retrieval_version,
            actor_ref=args.actor,
            reason=args.reason,
        )
    elif args.command == "approve-observation":
        result = approve_observation(
            store,
            observation_id=args.observation_id,
            actor_ref=args.actor,
            reason=args.reason,
        )
    elif args.command == "enqueue-verification":
        result = enqueue_verification(
            store,
            claim_id=args.claim_id,
            verification_kind=args.kind,
            verification_rule=_parse_rule(args.rule_json),
            statement_date=args.statement_date,
        )
    elif args.command == "trigger-reanalysis":
        result = enqueue_reanalysis_trigger(
            store,
            claim_id=args.claim_id,
            trigger_type=args.trigger_type,
            source_type=args.source_type,
            source_id=args.source_id,
            source_hash=args.source_hash,
        )
    elif args.command == "register-person":
        result = register_person(
            store,
            person_id=args.person_id,
            canonical_name=args.name,
            public_role=args.role,
            country_code=args.country_code,
        )
    elif args.command == "register-organization":
        result = register_organization(
            store,
            organization_id=args.organization_id,
            canonical_name=args.name,
            organization_type=args.organization_type,
            country_code=args.country_code,
            canonical_url=args.canonical_url,
        )
    elif args.command == "approve-role-interval":
        source_ref = json.loads(args.source_ref_json)
        if not isinstance(source_ref, dict):
            raise ValueError("source-ref-json must be a JSON object")
        result = approve_person_role_interval(
            store,
            interval_id=args.interval_id,
            person_id=args.person_id,
            organization_id=args.organization_id,
            role=args.role,
            start_date=args.start_date,
            end_date=args.end_date,
            is_public_role=True,
            source_ref=source_ref,
            actor_ref=args.actor,
            reason=args.reason,
            supersedes_id=args.supersedes_id,
        )
    elif args.command == "add-speaker-candidate":
        source_ref = json.loads(args.source_ref_json)
        if not isinstance(source_ref, dict):
            raise ValueError("source-ref-json must be a JSON object")
        result = add_speaker_candidate(
            store,
            content_id=args.content_id,
            person_id=args.person_id,
            start_ms=args.start_ms,
            end_ms=args.end_ms,
            attribution_method=args.method,
            speaker_label=args.speaker_label,
            source_ref=source_ref,
            confidence=args.confidence,
        )
    elif args.command == "approve-speaker":
        result = approve_speaker_candidate(
            store,
            candidate_id=args.candidate_id,
            actor_ref=args.actor,
            reason=args.reason,
        )
    elif args.command == "add-text-provenance":
        source_ref = json.loads(args.source_ref_json)
        if not isinstance(source_ref, dict):
            raise ValueError("source-ref-json must be a JSON object")
        result = add_text_provenance_candidate(
            store,
            claim_id=args.claim_id,
            content_id=args.content_id,
            person_id=args.person_id,
            selector_type=args.selector_type,
            quote_sha256=args.quote_sha256,
            source_sha256=args.source_sha256,
            start_char=args.start_char,
            end_char=args.end_char,
            attribution_method=args.method,
            source_ref=source_ref,
        )
    elif args.command == "approve-text-provenance":
        result = approve_text_provenance_candidate(
            store,
            candidate_id=args.candidate_id,
            actor_ref=args.actor,
            reason=args.reason,
        )
    elif args.command == "publish-finding":
        result = publish_finding(
            store,
            finding_id=args.finding_id,
            actor_ref=args.actor,
            reason=args.reason,
        )
    elif args.command == "record-reply":
        result = record_right_of_reply(
            store,
            finding_id=args.finding_id,
            submitter_name=args.submitter_name,
            submitter_role=args.submitter_role,
            body=args.body,
            evidence_urls=args.evidence_url,
        )
    elif args.command == "publish-reply":
        result = publish_right_of_reply(
            store,
            reply_id=args.reply_id,
            actor_ref=args.actor,
            reason=args.reason,
        )
    elif args.command == "record-correction":
        result = record_correction(
            store,
            finding_id=args.finding_id,
            previous_finding_id=args.previous_finding_id,
            reason=args.reason,
            changed_fields=_parse_rule(args.changed_fields_json),
        )
    else:
        result = publish_correction(
            store,
            correction_id=args.correction_id,
            actor_ref=args.actor,
            reason=args.reason,
        )
    print(json.dumps({"command": args.command, "id": result}, indent=2))


if __name__ == "__main__":
    main()
