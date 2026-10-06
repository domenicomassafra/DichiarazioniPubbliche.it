from __future__ import annotations

from dataclasses import asdict
from typing import Any

from dichiarazioni_pubbliche.coverage_needs import (
    coverage_need_params,
    materialize_coverage_need_specs,
)
from dichiarazioni_pubbliche.finding_runtime import finding_draft_from_verification
from dichiarazioni_pubbliche.reanalysis_runtime import deterministic_reanalysis_trigger
from dichiarazioni_pubbliche.relation_runtime import (
    RelationCandidateType,
    StructuredClaimRelationInput,
    classify_relation,
    deterministic_relation_candidate_id,
)
from dichiarazioni_pubbliche.source_intelligence import (
    SourceRelation,
    assess_evidence_set,
    evidence_item_from_row,
)
from dichiarazioni_pubbliche.verification_runtime import (
    VerificationEvidence,
    VerificationRequest,
    deterministic_verification_run_id,
    verification_input_fingerprint,
    verify,
)
from dichiarazioni_pubbliche.worker_errors import BlockedJob


class VerificationRelationReanalysisJobHandlers:
    def verify_claim(
        self,
        job: ProcessingJob,
        content: ContentRecord,
    ) -> None:
        claim_id = str(job.payload.get("claim_id") or "").strip()
        verification_kind = str(
            job.payload.get("verification_kind") or ""
        ).strip()
        verification_rule = job.payload.get("verification_rule")
        if not claim_id or not verification_kind:
            raise BlockedJob("VERIFICATION_PAYLOAD_INCOMPLETE")
        if not isinstance(verification_rule, dict):
            raise BlockedJob("VERIFICATION_RULE_INVALID")
        try:
            context = self.store.claim_context(claim_id)
        except KeyError as exc:
            raise BlockedJob("VERIFICATION_CLAIM_NOT_FOUND") from exc
        if context["content_id"] != content.content_id:
            raise BlockedJob("VERIFICATION_CONTENT_MISMATCH")
        canonical_statement_date = str(
            context.get("statement_date") or ""
        ).strip()
        payload_statement_date = str(
            job.payload.get("statement_date") or ""
        ).strip()
        if (
            canonical_statement_date
            and payload_statement_date
            and payload_statement_date != canonical_statement_date
        ):
            raise BlockedJob("VERIFICATION_STATEMENT_DATE_MISMATCH")
        statement_date = canonical_statement_date or payload_statement_date
        if not statement_date:
            raise BlockedJob("VERIFICATION_STATEMENT_DATE_MISSING")
        evidence_rows = self.store.approved_verification_evidence(claim_id)
        source_evidence = tuple(
            evidence_item_from_row(row, self.source_intelligence_contract)
            for row in evidence_rows
        )
        relations = tuple(
            SourceRelation(**row)
            for row in self.store.source_intelligence_relations()
        )
        claim_requirements: dict[str, Any] = {}
        temporal_scope = context.get("temporal_scope")
        if isinstance(temporal_scope, dict):
            claim_requirements.update(temporal_scope)
        claim_metadata = context.get("metadata")
        if isinstance(claim_metadata, dict):
            configured_requirements = claim_metadata.get("source_requirements")
            if isinstance(configured_requirements, dict):
                claim_requirements.update(configured_requirements)
        claim_requirements.update(verification_rule)
        source_assessment = assess_evidence_set(
            target_type="ATOMIC_CLAIM",
            target_id=claim_id,
            claim_type=str(context.get("claim_type") or ""),
            statement_date=statement_date,
            claim_requirements=claim_requirements,
            evidence=source_evidence,
            contract=self.source_intelligence_contract,
            relations=relations,
        )
        self.store.insert_evidence_set_assessment(
            assessment_id=source_assessment.id,
            atomic_claim_id=claim_id,
            claim_candidate_id=None,
            requirement_profile_id=source_assessment.requirement_profile_id,
            requirement_profile_version=source_assessment.requirement_profile_version,
            input_fingerprint=source_assessment.input_fingerprint,
            assessment=source_assessment.status,
            qualifying_evidence_ids=list(source_assessment.qualifying_evidence_ids),
            rejected_evidence=list(source_assessment.rejected_evidence),
            satisfied_rules=list(source_assessment.satisfied_rules),
            missing_rules=list(source_assessment.missing_rules),
            conflict_groups=list(source_assessment.conflict_groups),
            coverage_need_candidates=[
                asdict(item) for item in source_assessment.coverage_need_candidates
            ],
            rationale_codes=list(source_assessment.rationale_codes),
            assessment_version=source_assessment.assessment_version,
        )
        collection_ids = self.store.coverage_collection_ids_for_claim(claim_id)
        coverage_specs = materialize_coverage_need_specs(
            target_type="ATOMIC_CLAIM",
            target_id=claim_id,
            source_intelligence_assessment_id=source_assessment.id,
            candidates=[
                asdict(item) for item in source_assessment.coverage_need_candidates
            ],
            collection_ids=tuple(collection_ids),
        )
        for coverage_spec in coverage_specs:
            self.store.upsert_coverage_need(**coverage_need_params(coverage_spec))
        if source_assessment.status != "SUFFICIENT_FOR_RULE":
            raise BlockedJob(
                f"SOURCE_INTELLIGENCE_{source_assessment.status}:"
                f"{source_assessment.id}"
            )
        suitable_ids = set(source_assessment.qualifying_evidence_ids)
        evidence = tuple(
            VerificationEvidence(
                evidence_id=str(row["evidence_id"]),
                observation_id=str(row.get("observation_id") or "") or None,
                publication_date=str(row["publication_date"]),
                metric=(
                    str(row.get("metric") or "").strip() or None
                ),
                value_numeric=(
                    None
                    if row.get("value_numeric") is None
                    else float(row["value_numeric"])
                ),
                value_text=(
                    str(row.get("value_text") or "").strip() or None
                ),
                unit=str(row.get("unit") or "").strip() or None,
                reference_period=(
                    str(row.get("reference_period") or "").strip() or None
                ),
                suitable=str(row["evidence_id"]) in suitable_ids,
                authoritative=bool(row.get("authoritative")),
                status=str(row.get("status") or ""),
                metadata=(
                    row.get("metadata")
                    if isinstance(row.get("metadata"), dict)
                    else {}
                ),
            )
            for row in evidence_rows
        )
        request = VerificationRequest(
            claim_id=claim_id,
            statement_date=statement_date,
            kind=verification_kind,
            rule=verification_rule,
            source_intelligence_status=source_assessment.status,
            source_intelligence_assessment_id=source_assessment.id,
        )
        try:
            result = verify(request, evidence)
        except (KeyError, TypeError, ValueError) as exc:
            raise BlockedJob(
                f"VERIFICATION_RULE_REFUSED:{str(exc)[:180]}"
            ) from exc
        fingerprint = verification_input_fingerprint(request, evidence)
        run_id = deterministic_verification_run_id(request, evidence)
        self.store.insert_verification_run(
            run_id=run_id,
            claim_id=claim_id,
            source_intelligence_assessment_id=source_assessment.id,
            verification_kind=verification_kind,
            verification_version=result.verification_version,
            verification_rule=verification_rule,
            input_fingerprint=fingerprint,
            statement_cutoff=result.statement_cutoff,
            assessment=result.assessment.value,
            evidence_ids=list(result.evidence_ids),
            observation_ids=sorted(
                {
                    item.observation_id
                    for item in evidence
                    if (
                        item.observation_id is not None
                        and item.evidence_id in result.evidence_ids
                    )
                }
            ),
            blockers=list(result.blockers),
            rationale_codes=list(result.rationale_codes),
            result=result.result,
        )
        provisional = finding_draft_from_verification(
            verification_run_id=run_id,
            input_fingerprint=fingerprint,
            result=result,
        )
        previous = self.store.latest_finding_id(
            claim_id,
            exclude_finding_id=provisional.finding_id,
        )
        draft = finding_draft_from_verification(
            verification_run_id=run_id,
            input_fingerprint=fingerprint,
            result=result,
            supersedes_id=previous,
        )
        self.store.insert_finding_draft(asdict(draft))
        trigger_id = str(
            job.payload.get("reanalysis_trigger_id") or ""
        ).strip()
        if trigger_id:
            self.store.advance_reanalysis_trigger(
                trigger_id,
                status="PROCESSED",
                enqueued_job_id=job.job_id,
            )
    @staticmethod
    def _structured_relation_input(
        raw: object,
    ) -> StructuredClaimRelationInput:
        if not isinstance(raw, dict):
            raise BlockedJob("RELATION_INPUT_INVALID")
        try:
            return StructuredClaimRelationInput(
                claim_id=str(raw["claim_id"]).strip(),
                statement_date=str(raw["statement_date"]).strip(),
                proposition_key=(
                    str(raw.get("proposition_key") or "").strip() or None
                ),
                topic_key=str(raw.get("topic_key") or "").strip() or None,
                stance=str(raw.get("stance") or "").strip() or None,
                scope_start=str(raw.get("scope_start") or "").strip() or None,
                scope_end=str(raw.get("scope_end") or "").strip() or None,
                asserts_past_continuity=bool(
                    raw.get("asserts_past_continuity", False)
                ),
            )
        except KeyError as exc:
            raise BlockedJob("RELATION_INPUT_INCOMPLETE") from exc
    def classify_claim_relation_job(
        self,
        job: ProcessingJob,
        content: ContentRecord,
    ) -> None:
        prior = self._structured_relation_input(job.payload.get("prior"))
        later = self._structured_relation_input(job.payload.get("later"))
        try:
            prior_context = self.store.claim_context(prior.claim_id)
            later_context = self.store.claim_context(later.claim_id)
        except KeyError as exc:
            raise BlockedJob("RELATION_CLAIM_NOT_FOUND") from exc
        if content.content_id not in {
            prior_context["content_id"],
            later_context["content_id"],
        }:
            raise BlockedJob("RELATION_JOB_CONTENT_MISMATCH")
        try:
            result = classify_relation(prior, later)
        except ValueError as exc:
            raise BlockedJob(f"RELATION_REFUSED:{str(exc)[:180]}") from exc
        if result.relation_type == RelationCandidateType.NO_RELATION:
            return
        candidate_id = deterministic_relation_candidate_id(result)
        self.store.insert_relation_candidate(
            {
                "id": candidate_id,
                "subject_claim_id": result.subject_claim_id,
                "object_claim_id": result.object_claim_id,
                "relation_type": result.relation_type.value,
                "relation_version": result.relation_version,
                "status": "CANDIDATE",
                "confidence": result.confidence,
                "rationale_codes": list(result.rationale_codes),
                "metadata": {"source_job_id": job.job_id},
            }
        )
    def register_reanalysis(
        self,
        job: ProcessingJob,
        content: ContentRecord,
    ) -> None:
        claim_id = str(job.payload.get("claim_id") or "").strip()
        try:
            context = self.store.claim_context(claim_id)
        except KeyError as exc:
            raise BlockedJob("REANALYSIS_CLAIM_NOT_FOUND") from exc
        if context["content_id"] != content.content_id:
            raise BlockedJob("REANALYSIS_CONTENT_MISMATCH")
        try:
            trigger = deterministic_reanalysis_trigger(
                claim_id=claim_id,
                trigger_type=str(
                    job.payload.get("trigger_type") or ""
                ).strip(),
                source_type=str(
                    job.payload.get("source_type") or ""
                ).strip(),
                source_id=str(job.payload.get("source_id") or "").strip(),
                source_hash=(
                    str(job.payload.get("source_hash") or "").strip() or None
                ),
            )
        except ValueError as exc:
            raise BlockedJob(f"REANALYSIS_TRIGGER_REFUSED:{exc}") from exc
        self.store.insert_reanalysis_trigger(
            {
                "id": trigger.trigger_id,
                "claim_id": trigger.claim_id,
                "trigger_type": trigger.trigger_type,
                "source_type": trigger.source_type,
                "source_id": trigger.source_id,
                "source_hash": trigger.source_hash,
                "metadata": {"source_job_id": job.job_id},
            }
        )
        followup_id, _ = self.store.enqueue_followup(
            content_id=content.content_id,
            job_type="REANALYZE_CLAIM",
            payload={
                "claim_id": claim_id,
                "trigger_id": trigger.trigger_id,
                "estimated_cost_usd": 0.0,
            },
            variant=trigger.trigger_id,
        )
        self.store.advance_reanalysis_trigger(
            trigger.trigger_id,
            status="ENQUEUED",
            enqueued_job_id=followup_id,
        )
    def reanalyze_claim(
        self,
        job: ProcessingJob,
        content: ContentRecord,
    ) -> None:
        claim_id = str(job.payload.get("claim_id") or "").strip()
        trigger_id = str(job.payload.get("trigger_id") or "").strip()
        if not claim_id or not trigger_id:
            raise BlockedJob("REANALYSIS_PAYLOAD_INCOMPLETE")
        try:
            context = self.store.claim_context(claim_id)
        except KeyError as exc:
            raise BlockedJob("REANALYSIS_CLAIM_NOT_FOUND") from exc
        if context["content_id"] != content.content_id:
            raise BlockedJob("REANALYSIS_CONTENT_MISMATCH")
        template = self.store.latest_verification_template(claim_id)
        if template is None:
            raise BlockedJob("REANALYSIS_NO_VERIFICATION_TEMPLATE")
        verification_job_id, _ = self.store.enqueue_followup(
            content_id=content.content_id,
            job_type="VERIFY_CLAIM",
            payload={
                "claim_id": claim_id,
                "verification_kind": template["verification_kind"],
                "verification_rule": template["verification_rule"],
                "statement_date": template["statement_cutoff"],
                "reanalysis_trigger_id": trigger_id,
                "estimated_cost_usd": 0.0,
            },
            variant=trigger_id,
        )
        self.store.advance_reanalysis_trigger(
            trigger_id,
            status="ENQUEUED",
            enqueued_job_id=verification_job_id,
        )
