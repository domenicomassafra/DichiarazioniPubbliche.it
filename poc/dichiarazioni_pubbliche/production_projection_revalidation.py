from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.challenge_persistence import (
    ChallengeHoldDisposition,
    PrivateChallengeLedgerStore,
)
from dichiarazioni_pubbliche.finding_record_version import FindingRecordVersionStore
from dichiarazioni_pubbliche.high_risk_review_persistence import HighRiskReviewedPacketStore
from dichiarazioni_pubbliche.policy.excerpt_policy import RightsStatus
from dichiarazioni_pubbliche.privacy_decision_persistence import (
    PrivacyPublicationDecisionStore,
    privacy_decision_binding_ref,
)
from dichiarazioni_pubbliche.provenance_quarantine import (
    BoundedDependencyGraph,
    HoldEventType,
    HoldState,
    InMemoryProvenanceHoldRegistry,
    ProvenanceQuarantineError,
)
from dichiarazioni_pubbliche.provenance_quarantine_persistence import (
    ProvenanceHoldPersistenceStore,
)
from dichiarazioni_pubbliche.publication_eligibility import evaluate_publication_eligibility
from dichiarazioni_pubbliche.publication_review_persistence import PublicationReviewPersistenceStore
from dichiarazioni_pubbliche.publication_safety import (
    ProofState,
    PublicationSafetyInput,
    WordingMode,
    evaluate_publication_safety,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime
from dichiarazioni_pubbliche.reviewer_identity_authority import LocalFileReviewerIdentityAuthority


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ref(label: str, value: object) -> str:
    return f"{label}:{_digest(value)}"


def local_provenance_hold_allows_publication(
    *,
    finding_id: str,
    current_safety_binding_sha256: str,
    registry: InMemoryProvenanceHoldRegistry,
    graph: BoundedDependencyGraph,
) -> bool:
    """Apply the local DP-510 hold ledger to one current DP-308 safety binding.

    The local graph is intentionally explicit: its ``public_id`` for a Finding must be the
    canonical Finding ID used by the public dossier.  A caller that supplies the local hold
    seam must also supply a graph row whose publication binding is the exact current DP-308
    safety binding.  Active/pending holds block.  A released hold counts only when its final
    REVALIDATED event is bound to that same current safety state.  Chain tamper or incomplete
    local graph coverage fails closed.
    """

    finding = str(finding_id or "").strip()
    binding = str(current_safety_binding_sha256 or "").strip().lower()
    if not finding or len(binding) != 64 or any(ch not in "0123456789abcdef" for ch in binding):
        return False
    records = tuple(record for record in graph.records if record.public_id == finding)
    if len(records) != 1 or records[0].binding_sha256 != binding:
        return False
    try:
        events = registry.events
        hold_ids = sorted({event.hold_id for event in events})
        for hold_id in hold_ids:
            hold_events = tuple(event for event in events if event.hold_id == hold_id)
            if not hold_events:
                return False
            activation = hold_events[0]
            if activation.event_type is not HoldEventType.ACTIVATE:
                return False
            if finding not in graph.affected_public_ids(activation.scope):
                continue
            state = registry.state(hold_id)
            if state is not HoldState.RELEASED:
                return False
            latest = hold_events[-1]
            if (
                latest.event_type is not HoldEventType.REVALIDATED
                or latest.revalidation_binding_sha256 != binding
            ):
                return False
    except (ProvenanceQuarantineError, TypeError, ValueError):
        return False
    return True


class ProductionProjectionRevalidator(PsqlRuntime):
    """DP-308 production boundary over current private proof state.

    The legacy projection query remains useful as a candidate finder.  This class is the
    publication authority boundary: a candidate reaches the serializer only after current
    record-version, privacy, rights, challenge, high-risk and authority-attested review state
    are revalidated.  Missing state is a hold; no legacy status or caller boolean is promoted
    into permission.
    """

    def __init__(
        self,
        database_url: str | None,
        *,
        reviewer_authority_root: str | Path | None,
        local_hold_registry: InMemoryProvenanceHoldRegistry | None = None,
        local_hold_graph: BoundedDependencyGraph | None = None,
        provenance_hold_store: ProvenanceHoldPersistenceStore | None = None,
        psql: str = "psql",
    ) -> None:
        super().__init__(database_url, psql)
        self._authority_root = (
            None if reviewer_authority_root is None else Path(reviewer_authority_root)
        )
        if (local_hold_registry is None) != (local_hold_graph is None):
            raise ValueError("PRODUCTION_REVALIDATION_LOCAL_HOLD_INPUT_INCOMPLETE")
        self._local_hold_registry = local_hold_registry
        self._local_hold_graph = local_hold_graph
        self._provenance_hold_store = provenance_hold_store or ProvenanceHoldPersistenceStore(
            database_url, psql
        )

    def _rights_target_records(
        self,
        *,
        column: str,
        target_id: str,
    ) -> tuple[dict[str, Any], ...]:
        if column not in {"content_id", "evidence_id"}:
            raise ValueError("PUBLICATION_RIGHTS_TARGET_COLUMN_INVALID")
        raw = self.run(
            f"""
            SELECT COALESCE(json_agg(json_build_object(
                'id', current.id,
                'rights_status', current.rights_status,
                'rights_receipt_ref', current.rights_receipt_ref,
                'permitted_uses', to_json(current.permitted_uses),
                'attribution_requirements', to_json(current.attribution_requirements),
                'reviewed_at', current.reviewed_at::text,
                'expires_at', current.expires_at::text,
                'reviewer_ref', current.reviewer_ref,
                'policy_version', current.policy_version,
                'record_visibility', current.record_visibility
            ) ORDER BY current.id)::text, '[]')
            FROM private_source_rights_record current
            WHERE current.{column}=:'target_id'
              AND current.transcript_segment_id IS NULL
              AND current.canonical_segment_id IS NULL
              AND current.passage_id IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM private_source_rights_record child
                  WHERE child.supersedes_id=current.id
              );
            """,
            target_id=target_id,
        )
        rows = json.loads(raw or "[]")
        return tuple(row for row in rows if isinstance(row, dict))

    @staticmethod
    def _rights_pass(
        records: tuple[dict[str, Any], ...],
        *,
        now: datetime,
    ) -> bool:
        if len(records) != 1:
            return False
        record = records[0]
        if record.get("record_visibility") != "PRIVATE":
            return False
        if record.get("rights_status") != RightsStatus.CLEARED.value:
            return False
        if not record.get("rights_receipt_ref") or not record.get("reviewer_ref"):
            return False
        # A source may be cleared for private fetch/retention/model work, but
        # that does not grant the ability to display even its link in a public
        # Finding. Our published dossiers expose both the source and evidence
        # URLs; require a separate, explicit public-link use on *each* record.
        # Quotation/media remain subject to their independent DP-305 policies.
        uses = record.get("permitted_uses")
        if not isinstance(uses, list) or "LINK_PUBLIC" not in uses:
            return False
        reviewed = record.get("reviewed_at")
        if not isinstance(reviewed, str) or not reviewed.strip():
            return False
        try:
            reviewed_at = datetime.fromisoformat(reviewed.replace("Z", "+00:00"))
        except ValueError:
            return False
        if reviewed_at.tzinfo is None or reviewed_at > now:
            return False
        expires = record.get("expires_at")
        if expires:
            try:
                parsed = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
            except ValueError:
                return False
            if parsed.tzinfo is None or parsed <= now:
                return False
        return True

    def _current_high_risk_binding(self, finding_id: str) -> tuple[str, str | None] | None:
        raw = self.run(
            """
            SELECT COALESCE(json_agg(json_build_object(
                'record_ref', packet.record_ref,
                'human_review_actor_ref', packet.human_review_actor_ref
            ) ORDER BY packet.packet_sequence DESC)::text, '[]')
            FROM private_high_risk_review_packet packet
            WHERE packet.finding_ref=:'finding_id'
              AND NOT EXISTS (
                  SELECT 1 FROM private_high_risk_review_packet child
                  WHERE child.supersedes_packet_id=packet.packet_id
              );
            """,
            finding_id=finding_id,
        )
        rows = json.loads(raw or "[]")
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            return None
        record_ref = str(rows[0].get("record_ref") or "")
        if not record_ref:
            return None
        actor = rows[0].get("human_review_actor_ref")
        return record_ref, None if actor is None else str(actor)

    def _privacy_reviewer(self, decision_id: str) -> str | None:
        value = self.run(
            "SELECT reviewer_ref FROM privacy_publication_decision "
            "WHERE decision_id=:'decision_id';",
            decision_id=decision_id,
        )
        return value or None

    def revalidate(
        self,
        *,
        row: dict[str, Any],
        dossier: dict[str, Any],
    ) -> bool:
        finding_id = str(dossier.get("finding_id") or "")
        speaker_id = str((dossier.get("speaker") or {}).get("id") or "")
        normalized_claim = str(dossier.get("claim") or "")
        source = dossier.get("source") or {}
        source_content_id = str(source.get("content_id") or "")
        if not finding_id or not speaker_id or not normalized_claim or not source_content_id:
            return False

        try:
            current_version = FindingRecordVersionStore(
                self.database_url, self.psql
            ).current_record_version(finding_id)
        except (RuntimeError, TypeError, ValueError):
            return False

        try:
            privacy = PrivacyPublicationDecisionStore(
                self.database_url, self.psql
            ).replay_current_text_field(
                subject_ref=speaker_id,
                record_ref=finding_id,
                current_record_version=current_version,
                field_name="normalized_claim",
                current_text_value=normalized_claim,
            )
        except (RuntimeError, TypeError, ValueError, json.JSONDecodeError):
            return False
        privacy_state = ProofState.PASSED if privacy.allowed else ProofState.HOLD
        privacy_ref = privacy.decision_ref
        if privacy_ref is None:
            return False
        privacy_binding = privacy_decision_binding_ref(privacy.input_sha256)

        now = datetime.now(timezone.utc)
        try:
            source_rights = self._rights_target_records(
                column="content_id", target_id=source_content_id
            )
            evidence_rights = tuple(
                self._rights_target_records(column="evidence_id", target_id=str(item["id"]))
                for item in dossier.get("evidence") or []
            )
        except (RuntimeError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            return False
        rights_ok = self._rights_pass(source_rights, now=now) and all(
            self._rights_pass(records, now=now) for records in evidence_rights
        )
        rights_state = ProofState.PASSED if rights_ok else ProofState.HOLD

        try:
            challenge = PrivateChallengeLedgerStore(
                self.database_url, self.psql
            ).current_hold_for_finding(finding_id)
        except (RuntimeError, TypeError, ValueError, json.JSONDecodeError):
            return False
        challenge_state = (
            ProofState.PASSED
            if challenge.disposition is ChallengeHoldDisposition.CLEAR
            else ProofState.HOLD
        )

        wording = dossier.get("wording") or {}
        source_wording = wording.get("source_occurrence") or {}
        source_hash = str(source_wording.get("text_sha256") or "")
        if len(source_hash) != 64:
            return False

        source_methodology = dossier.get("source_methodology")
        evidence_suitability = (
            ProofState.PASSED
            if isinstance(source_methodology, dict)
            and source_methodology.get("assessment") == "SUFFICIENT_FOR_RULE"
            else ProofState.MISSING
        )
        publication_review_ids = tuple(
            str(value)
            for value in ((dossier.get("finding") or {}).get("publication_review_ids") or [])
        )
        evidence = dossier.get("evidence") or []
        finding = dossier.get("finding") or {}
        policy_version = str(finding.get("policy_version") or "").strip()
        if not policy_version:
            return False
        source_version_ref = _ref(
            "source-version",
            {
                "source": source,
                "source_occurrence": source_wording,
            },
        )
        provenance_version_ref = _ref(
            "provenance-version",
            {
                "speaker": dossier.get("speaker"),
                "wording": wording,
                "evidence": evidence,
            },
        )
        review_version_ref = _ref(
            "review-version",
            {
                "record_version": current_version,
                "publication_review_ids": publication_review_ids,
            },
        )
        load_bearing_refs = {
            "source_version": source_version_ref,
            "provenance_version": provenance_version_ref,
            "policy_version": policy_version,
            "review_version": review_version_ref,
            "finding_record_version": current_version,
            "source_identity": _ref("source", source),
            "speaker_span": _ref("speaker-provenance", (dossier.get("speaker") or {}).get("provenance")),
            "speech_origin": _ref("wording-source", source_wording),
            "context_integrity": _ref("source-occurrence", row.get("source_occurrence_quote_sha256")),
            "wording_integrity": _ref("wording", wording),
            "identity_integrity": _ref("speaker", dossier.get("speaker")),
            "evidence_suitability": _ref("methodology", source_methodology),
            "citation_assurance": _ref(
                "citations",
                {
                    "assertion": row.get("finding_assertion_sha256"),
                    "evidence": evidence,
                },
            ),
            "privacy": privacy_ref,
            "rights": _ref(
                "rights",
                [
                    *[record.get("id") for record in source_rights],
                    *[
                        record.get("id")
                        for records in evidence_rights
                        for record in records
                    ],
                ],
            ),
            "verification_review": _ref(
                "verification",
                {
                    "verification_run_id": (dossier.get("finding") or {}).get(
                        "verification_run_id"
                    ),
                    "evidence": evidence,
                },
            ),
            "finding_review": _ref("legacy-finding-review", publication_review_ids),
            "challenge_hold": _ref(
                "challenge",
                {
                    "record_version": challenge.record_version,
                    "request_id": challenge.request_id,
                    "event_id": challenge.event_id,
                    "disposition": challenge.disposition.value,
                },
            ),
        }
        safety = evaluate_publication_safety(
            PublicationSafetyInput(
                wording_mode=WordingMode.PARAPHRASE,
                media_quote=False,
                source_identity=ProofState.PASSED,
                exact_wording=ProofState.NOT_APPLICABLE,
                transcript_verbatim=ProofState.NOT_APPLICABLE,
                speaker_span=ProofState.PASSED,
                speech_origin=ProofState.PASSED,
                context_integrity=ProofState.PASSED,
                wording_integrity=ProofState.PASSED,
                identity_integrity=ProofState.PASSED,
                translation_review=ProofState.NOT_APPLICABLE,
                evidence_suitability=evidence_suitability,
                citation_assurance=ProofState.PASSED,
                privacy=privacy_state,
                rights=rights_state,
                verification_review=ProofState.PASSED,
                finding_review=(
                    ProofState.PASSED if publication_review_ids else ProofState.MISSING
                ),
                challenge_hold=challenge_state,
                load_bearing_refs=load_bearing_refs,
            )
        )
        if not safety.eligible:
            return False
        try:
            if not self._provenance_hold_store.allows_publication(
                public_id=finding_id,
                current_publication_binding_sha256=safety.binding_sha256,
            ):
                return False
        except (RuntimeError, TypeError, ValueError, ProvenanceQuarantineError):
            return False
        if self._local_hold_registry is not None and self._local_hold_graph is not None:
            if not local_provenance_hold_allows_publication(
                finding_id=finding_id,
                current_safety_binding_sha256=safety.binding_sha256,
                registry=self._local_hold_registry,
                graph=self._local_hold_graph,
            ):
                return False

        try:
            high_risk_binding = self._current_high_risk_binding(finding_id)
            if high_risk_binding is None:
                return False
            high_risk_record_ref, high_risk_actor_ref = high_risk_binding
            high_risk = HighRiskReviewedPacketStore(
                self.database_url, self.psql
            ).replay_current_hash_bound(
                record_ref=high_risk_record_ref,
                finding_ref=finding_id,
                current_record_version=current_version,
                current_source_text_sha256=source_hash,
                current_normalized_text=normalized_claim,
                privacy_decision_ref=privacy_ref,
                privacy_decision_binding_ref=privacy_binding,
            )
        except (RuntimeError, TypeError, ValueError, json.JSONDecodeError):
            return False
        if high_risk.blockers:
            return False

        try:
            privacy_reviewer = self._privacy_reviewer(privacy_ref)
        except RuntimeError:
            return False
        upstream_actor_refs = tuple(
            dict.fromkeys(
                value
                for value in (
                    privacy_reviewer,
                    high_risk_actor_ref,
                    *(
                        str(record.get("reviewer_ref") or "")
                        for record in source_rights
                    ),
                    *(
                        str(record.get("reviewer_ref") or "")
                        for records in evidence_rights
                        for record in records
                    ),
                )
                if value
            )
        )

        authority = None
        if self._authority_root is not None:
            try:
                authority = LocalFileReviewerIdentityAuthority(self._authority_root)
            except (OSError, TypeError, ValueError):
                return False
        result = evaluate_publication_eligibility(
            record_id=finding_id,
            record_version=current_version,
            publication_safety=safety,
            high_risk=high_risk.decision,
            high_risk_input_binding_sha256=high_risk.input_sha256,
            review_store=PublicationReviewPersistenceStore(self.database_url, self.psql),
            review_authority=authority,
            upstream_actor_refs=upstream_actor_refs,
        )
        return result.disposition == "ELIGIBLE_FOR_PROJECTION_REVALIDATION"


__all__ = [
    "ProductionProjectionRevalidator",
    "local_provenance_hold_allows_publication",
]
