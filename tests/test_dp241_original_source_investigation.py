"""DP-241 local synthetic source recovery; no real searches or approvals."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.corpus_repository import (
    ContentCaptureRecord,
    PassageRecord,
)  # noqa: E402
from dichiarazioni_pubbliche.original_source_resolver import (  # noqa: E402
    DerivationEdge,
    ExactSourceLocator,
)
from dichiarazioni_pubbliche.original_source_investigation_v1 import (  # noqa: E402
    OriginalCandidateProof,
    RecoveryMethod,
    RecoveryReceipt,
    SourceRecoveryTarget,
    assess_recovery,
    make_recovery_plan,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceUseDecision  # noqa: E402
from dichiarazioni_pubbliche.research_plan import ResearchAssignment  # noqa: E402


def sha(value: str | bytes) -> str:
    return hashlib.sha256(
        value if isinstance(value, bytes) else value.encode("utf-8")
    ).hexdigest()


SHORT = "Non ha detto sì."
LONG = "Intervento integrale: " + SHORT + " Questa è la frase successiva."


def document(
    text: str, content_id: str
) -> tuple[ContentCaptureRecord, PassageRecord, ExactSourceLocator, bytes]:
    body = text.encode("utf-8")
    capture = ContentCaptureRecord(
        id="capture:" + content_id,
        content_id=content_id,
        observed_at="2026-10-11T00:00:00+00:00",
        final_url="https://official.example/" + content_id.replace(":", "-"),
        content_sha256=sha(body),
        retrieval_method="FIXTURE",
        retrieval_version="v1",
        parser_method="TEST_NATIVE",
        parser_version="v1",
        media_type="text/plain",
        body_ref="private:body",
        rights_status="CLEARED",
        metadata={"parse_status": "SUCCEEDED"},
    )
    passage = PassageRecord(
        id="passage:" + content_id,
        content_id=content_id,
        capture_id=capture.id,
        selector_type="TEXT_POSITION",
        start_char=0,
        end_char=len(text),
        text_sha256=sha(text),
        private_text=text,
        extraction_method="TEST_NATIVE",
        extraction_version="v1",
        language="it",
    )
    locator = ExactSourceLocator(
        content_id=content_id,
        capture_id=capture.id,
        passage_id=passage.id,
        selector_type="TEXT_POSITION",
        quote_start=0,
        quote_end=len(text),
        quote_sha256=sha(text),
        capture_sha256=sha(body),
    )
    return capture, passage, locator, body


def target(text: str = SHORT, content_id: str = "content:clip") -> SourceRecoveryTarget:
    capture, passage, locator, body = document(text, content_id)
    return SourceRecoveryTarget(
        need_id="need:original",
        question="Qual è la fonte integrale originale di questa frase?",
        expected_person_id="person:anna",
        event_date="2026-08-10",
        locator=locator,
        passage=passage,
        quote_text=text,
        capture=capture,
        source_body=body,
        canonical_text=text,
    )


def permit(use: str, label: str = "1", status: str = "PERMITTED") -> SourceUseDecision:
    return SourceUseDecision(
        use,
        status,
        "SOURCE_USE_PERMITTED" if status == "PERMITTED" else "SOURCE_USE_NOT_PERMITTED",
        "NONE",
        "rights:" + label,
        sha(use + label) if status == "PERMITTED" else None,
    )


def method(
    lane: str,
    name: str,
    *,
    discovery: SourceUseDecision | None = None,
    fetched: SourceUseDecision | None = None,
    estimated: str = "0.2",
) -> RecoveryMethod:
    assignment = ResearchAssignment(
        assignment_id="assignment:" + name,
        coverage_need_id="need:original",
        lane=lane,
        question="Qual è la fonte integrale originale di questa frase?",
        adapter_ids=("adapter:" + name,),
        max_queries=1,
        max_results=3,
        max_results_per_host=1,
        cost_cap_usd=Decimal("0.5"),
        temporal_constraints={},
        authority_scope={},
        stop_conditions=("MAX_ATTEMPTS_REACHED",),
    )
    return RecoveryMethod(
        assignment=assignment,
        source_family="source-family:" + name,
        adapter_id="adapter:" + name,
        validated_query_ref="reviewed-query:" + name,
        query_validation_sha256=sha("reviewed-query-fixture:" + name),
        discover_permission=discovery or permit("DISCOVER_METADATA", name),
        fetch_permission=fetched or permit("FETCH", name),
        estimate_usd=Decimal(estimated),
    )


def two_methods() -> tuple[RecoveryMethod, ...]:
    return (method("ORIGINAL_MEDIA", "publisher"), method("ARCHIVE_HISTORY", "archive"))


def plan(
    *,
    methods: tuple[RecoveryMethod, ...] | None = None,
    source: SourceRecoveryTarget | None = None,
    max_attempts: int = 3,
    cost: str = "1",
):
    return make_recovery_plan(
        source or target(),
        methods or two_methods(),
        max_attempts=max_attempts,
        cost_cap_usd=Decimal(cost),
    )


def receipt(
    p,
    i: int,
    result: str,
    *,
    candidate: OriginalCandidateProof | None = None,
    receipt_tag: str = "observed",
    spent: str = "0.1",
) -> RecoveryReceipt:
    return RecoveryReceipt(
        attempt_id=p.methods[i].attempt_id,
        plan_id=p.plan_id,
        result=result,
        discovery_receipt_sha256=sha(receipt_tag + str(i)),
        spent_usd=Decimal(spent),
        candidate=candidate,
    )


def source_candidate(
    *,
    content: str = "content:original",
    source_text: str = LONG,
    person: str = "person:anna",
    observed_date: str = "2026-08-10",
    approved: bool = True,
) -> OriginalCandidateProof:
    cap, passage, locator, body = document(source_text, content)
    family = (
        {
            "status": "APPROVED",
            "root_content_id": "content:original",
            "family_id": "family:official",
        },
    )
    edge = DerivationEdge(
        edge_id="edge:approved",
        family_id="family:official",
        derived_content_id="content:clip",
        origin_content_id="content:original",
        relation_type="REPUBLICATION",
        status="APPROVED" if approved else "CANDIDATE",
    )
    return OriginalCandidateProof(
        locator=locator,
        passage=passage,
        quote_text=source_text,
        capture=cap,
        source_body=body,
        canonical_text=source_text,
        approved_families=family,
        approved_edges=(edge,),
        observed_person_id=person,
        observed_event_date=observed_date,
    )


class DP241OriginalSourceInvestigationTests(unittest.TestCase):
    def test_two_distinct_permitted_methods_and_deterministic_proposals(self):
        current = plan()
        replay = plan(methods=tuple(reversed(two_methods())))
        self.assertEqual(current, replay)
        self.assertEqual(current.status, "READY_PRIVATE_PLAN")
        self.assertEqual(len({m.method_family for m in current.methods}), 2)
        self.assertTrue(
            all(
                m.fetch_permission_sha256 and m.discover_permission_sha256
                for m in current.methods
            )
        )
        self.assertTrue(
            all(
                m.validated_query_ref.startswith("reviewed-query:")
                for m in current.methods
            )
        )
        self.assertFalse(current.dispatch_authorized)
        initial = assess_recovery(current, target(), ())
        self.assertEqual(initial.status, "READY_PRIVATE_PROPOSAL")
        self.assertEqual(initial.proposed_attempt_id, current.methods[0].attempt_id)
        self.assertEqual(initial.prior_attempts, 0)
        self.assertFalse(initial.publication_authority)

    def test_two_adapters_in_same_family_are_not_distinct_methods(self):
        current = plan(
            methods=(
                method("ORIGINAL_MEDIA", "publisher"),
                method("PRIMARY_SOURCE", "publisher2"),
            )
        )
        self.assertEqual(current.status, "WAIT_EXTERNAL")
        self.assertEqual(current.reason_code, "RECOVERY_TWO_DISTINCT_METHODS_REQUIRED")
        self.assertIsNone(assess_recovery(current, target(), ()).proposed_attempt_id)

    def test_exact_permissions_for_both_operations_and_cost_budget_required(self):
        unauthorized = method(
            "ARCHIVE_HISTORY", "archive", fetched=permit("FETCH", "archive", "DENIED")
        )
        current = plan(methods=(method("ORIGINAL_MEDIA", "publisher"), unauthorized))
        self.assertEqual(current.status, "WAIT_EXTERNAL")
        self.assertEqual(
            current.reason_code, "RECOVERY_INSUFFICIENT_PERMITTED_DISTINCT_METHODS"
        )
        wrong_use = method(
            "ARCHIVE_HISTORY", "archive", discovery=permit("FETCH", "archive")
        )
        self.assertEqual(
            plan(methods=(two_methods()[0], wrong_use)).status, "WAIT_EXTERNAL"
        )
        cost_limited = plan(cost="0.3")
        self.assertEqual(cost_limited.reason_code, "RECOVERY_METHOD_COST_CAP_BLOCKED")

    def test_duplicate_method_reference_and_bogus_adapter_are_rejected(self):
        first = two_methods()[0]
        with self.assertRaisesRegex(ValueError, "DP241_DUPLICATE_METHOD_REFERENCE"):
            plan(methods=(first, first))
        invalid = replace(first, adapter_id="adapter:fake")
        with self.assertRaisesRegex(ValueError, "DP241_RESEARCH_ASSIGNMENT_MISMATCH"):
            plan(methods=(invalid, two_methods()[1]))

    def test_replayed_plan_rejects_tampered_status_fingerprint_limits_and_methods(self):
        current = plan()
        restricted = plan(
            methods=(
                method("ORIGINAL_MEDIA", "publisher"),
                method("PRIMARY_SOURCE", "publisher2"),
            )
        )
        blocked_cost = plan(cost="0.3")
        variants = (
            replace(current, plan_id="original-source-plan:forged"),
            replace(current, dispatch_authorized=True),
            replace(current, max_attempts=4),
            replace(current, cost_cap_usd=Decimal("2")),
            replace(current, methods=tuple(reversed(current.methods))),
            replace(current, methods=(current.methods[0], current.methods[0])),
            replace(
                current,
                methods=(
                    replace(current.methods[0], attempt_id="fake"),
                    current.methods[1],
                ),
            ),
            replace(
                current,
                methods=(
                    replace(current.methods[0], fetch_permission_sha256=sha("forged")),
                    current.methods[1],
                ),
            ),
            replace(
                current,
                methods=(
                    replace(current.methods[0], estimated_cost_usd=Decimal("5")),
                    current.methods[1],
                ),
            ),
            replace(restricted, status="READY_PRIVATE_PLAN"),
            replace(blocked_cost, status="READY_PRIVATE_PLAN"),
        )
        for index, altered in enumerate(variants):
            with self.subTest(index=index):
                with self.assertRaisesRegex(ValueError, "DP241_PLAN_"):
                    assess_recovery(altered, target(), ())

    def test_not_found_is_one_checked_scope_then_checked_insufficient_after_two(self):
        current = plan()
        first = receipt(current, 0, "NOT_FOUND")
        one = assess_recovery(current, target(), (first,))
        self.assertEqual(one.status, "READY_PRIVATE_PROPOSAL")
        self.assertEqual(one.prior_attempts, 1)
        self.assertEqual(one.remaining_attempts, 2)
        self.assertEqual(one.proposed_attempt_id, current.methods[1].attempt_id)
        two = assess_recovery(
            current, target(), (first, receipt(current, 1, "CHECKED_INSUFFICIENT"))
        )
        self.assertEqual(two.status, "CHECKED_INSUFFICIENT")
        self.assertEqual(len(two.checked_methods), 2)
        self.assertEqual(two.verified_root_content_ids, ())
        self.assertEqual(
            two.next_trigger, "NEW_SOURCE_VERSION_OR_NEW_AUTHORIZED_METHOD"
        )

    def test_outage_rights_cost_are_distinct_and_no_automatic_retry(self):
        current = plan()
        for label, status, reason, trigger in (
            (
                "OUTAGE",
                "WAIT_EXTERNAL",
                "RECOVERY_PROVIDER_OUTAGE",
                "RETRY_ON_PROVIDER_RECOVERY",
            ),
            (
                "RIGHTS_BLOCKED",
                "WAIT_EXTERNAL",
                "RECOVERY_FETCH_RIGHTS_BLOCKED",
                "REVIEW_SOURCE_PERMISSIONS",
            ),
            (
                "COST_BLOCKED",
                "WAIT_EXTERNAL",
                "RECOVERY_ATTEMPT_COST_BLOCKED",
                "REFRESH_COST_LEDGER",
            ),
        ):
            with self.subTest(label=label):
                outcome = assess_recovery(
                    current, target(), (receipt(current, 0, label),)
                )
                self.assertEqual(
                    (outcome.status, outcome.reason_code, outcome.next_trigger),
                    (status, reason, trigger),
                )
                self.assertIsNone(outcome.proposed_attempt_id)
        self.assertEqual(
            assess_recovery(current, target(), (), rights_current=False).reason_code,
            "RECOVERY_RIGHTS_REVALIDATION_REQUIRED",
        )
        self.assertEqual(
            assess_recovery(current, target(), (), budget_ready=False).reason_code,
            "RECOVERY_COST_CAP_OR_RECEIPTS_UNAVAILABLE",
        )

    def test_replay_duplicate_does_not_charge_twice_and_conflict_refused(self):
        current = plan()
        first = receipt(current, 0, "NOT_FOUND")
        twice = assess_recovery(current, target(), (first, first))
        self.assertEqual(twice.prior_attempts, 1)
        self.assertEqual(twice.spent_usd, Decimal("0.1"))
        with self.assertRaisesRegex(ValueError, "DP241_RECEIPT_REPLAY_CONFLICT"):
            assess_recovery(current, target(), (first, replace(first, result="OUTAGE")))
        with self.assertRaisesRegex(ValueError, "DP241_FOREIGN_RECEIPT"):
            assess_recovery(current, target(), (replace(first, plan_id="other-plan"),))
        with self.assertRaisesRegex(ValueError, "DP241_RECEIPT_RESULT_INVALID"):
            assess_recovery(
                current, target(), (replace(first, result="AUTHORITATIVE_PUBLISHED"),)
            )
        with self.assertRaisesRegex(ValueError, "DP241_FOUND_PROOF_REQUIRED"):
            assess_recovery(
                current, target(), (replace(first, result="FOUND_CANDIDATE"),)
            )

    def test_true_original_is_private_candidate_with_exact_root_binding_and_reanalysis(
        self,
    ):
        current = plan()
        proof = source_candidate()
        outcome = assess_recovery(
            current,
            target(),
            (receipt(current, 0, "FOUND_CANDIDATE", candidate=proof),),
        )
        self.assertEqual(outcome.status, "VERIFIED_PRIVATE_SOURCE_CANDIDATE")
        self.assertEqual(outcome.verified_root_content_ids, ("content:original",))
        self.assertTrue(outcome.reanalysis_required)
        self.assertFalse(outcome.publication_authority)
        self.assertIsNone(outcome.proposed_attempt_id)

    def test_found_many_mirrors_collapse_and_never_manufacture_independence(self):
        current = plan()
        proof = source_candidate()
        observations = (
            receipt(current, 0, "FOUND_CANDIDATE", candidate=proof),
            receipt(current, 1, "FOUND_CANDIDATE", candidate=proof),
        )
        outcome = assess_recovery(current, target(), observations)
        self.assertEqual(outcome.private_source_candidates, 1)
        self.assertEqual(outcome.verified_root_content_ids, ("content:original",))
        copy = source_candidate(content="content:mirror")
        result = assess_recovery(
            current, target(), (receipt(current, 0, "FOUND_CANDIDATE", candidate=copy),)
        )
        self.assertEqual(result.status, "CONFLICT")
        self.assertEqual(result.reason_code, "RECOVERY_UNPROVEN_ROOT_LINEAGE")

    def test_cross_family_approved_edge_does_not_establish_root(self):
        current = plan()
        proof = source_candidate()
        foreign_edge = replace(proof.approved_edges[0], family_id="family:unrelated")
        out = assess_recovery(
            current,
            target(),
            (
                receipt(
                    current,
                    0,
                    "FOUND_CANDIDATE",
                    candidate=replace(proof, approved_edges=(foreign_edge,)),
                ),
            ),
        )
        self.assertEqual(
            (out.status, out.reason_code),
            ("CONFLICT", "RECOVERY_UNAPPROVED_LINEAGE_FAMILY"),
        )

    def test_wrong_person_date_or_unsupported_full_quote_cannot_resolve(self):
        current = plan()
        proofs = (
            (
                source_candidate(person="person:other"),
                "RECOVERY_PERSON_MISMATCH_OR_UNVERIFIED",
            ),
            (
                source_candidate(observed_date="2025-08-10"),
                "RECOVERY_EVENT_DATE_MISMATCH_OR_UNVERIFIED",
            ),
            (
                source_candidate(
                    source_text="An unrelated transcript with no direct quotation"
                ),
                "RECOVERY_FULL_CONTEXT_UNPROVEN",
            ),
            (source_candidate(source_text=SHORT), "RECOVERY_FULL_CONTEXT_UNPROVEN"),
            (source_candidate(approved=False), "RECOVERY_UNPROVEN_ROOT_LINEAGE"),
        )
        for proof, reason in proofs:
            with self.subTest(reason=reason):
                result = assess_recovery(
                    current,
                    target(),
                    (receipt(current, 0, "FOUND_CANDIDATE", candidate=proof),),
                )
                self.assertEqual(
                    (result.status, result.reason_code), ("CONFLICT", reason)
                )
                self.assertEqual(result.verified_root_content_ids, ())

    def test_forged_candidate_source_hash_quote_and_selector_conflict(self):
        current = plan()
        proof = source_candidate()
        variants = (
            replace(proof, source_body=b"changed source"),
            replace(proof, quote_text="an invented fake quotation"),
            replace(
                proof, locator=replace(proof.locator, capture_sha256=sha("altered"))
            ),
            replace(proof, locator=replace(proof.locator, quote_start=12)),
        )
        for row in variants:
            with self.subTest(row=row.locator.quote_start):
                result = assess_recovery(
                    current,
                    target(),
                    (receipt(current, 0, "FOUND_CANDIDATE", candidate=row),),
                )
                self.assertEqual(result.status, "CONFLICT")
                self.assertEqual(
                    result.reason_code, "RECOVERY_CANDIDATE_LOCATOR_INVALID"
                )

    def test_updated_target_source_requires_revalidation_without_replaying_old_plan(
        self,
    ):
        old = target()
        current = plan(source=old)
        out = assess_recovery(
            current, old, (), current_target_version_sha256=sha("new bytes")
        )
        self.assertEqual(out.status, "STALE")
        self.assertTrue(out.reanalysis_required)
        self.assertEqual(out.next_trigger, "DP511_SOURCE_REVALIDATION")
        updated = target("Non ha detto sì, ma poi ha aggiunto una precisazione.")
        new_plan = plan(source=updated)
        self.assertNotEqual(current.plan_id, new_plan.plan_id)
        with self.assertRaisesRegex(ValueError, "DP241_FOREIGN_RECEIPT"):
            assess_recovery(new_plan, updated, (receipt(current, 0, "NOT_FOUND"),))
        with self.assertRaisesRegex(ValueError, "DP241_PLAN_TARGET_SOURCE_CHANGED"):
            assess_recovery(current, updated, ())

    def test_budget_attempt_limit_and_unbounded_receipts_fail_closed(self):
        current = plan(
            methods=two_methods() + (method("OFFICIAL_STRUCTURED", "official"),),
            max_attempts=2,
        )
        first = receipt(current, 0, "NOT_FOUND")
        second = receipt(current, 1, "NOT_FOUND")
        final = assess_recovery(current, target(), (first, second))
        self.assertEqual(final.status, "EXHAUSTED")
        self.assertEqual(final.remaining_attempts, 0)
        self.assertEqual(final.reason_code, "RECOVERY_ATTEMPT_LIMIT")
        completely_checked = plan(max_attempts=2)
        self.assertEqual(
            assess_recovery(
                completely_checked,
                target(),
                (
                    receipt(completely_checked, 0, "NOT_FOUND"),
                    receipt(completely_checked, 1, "NOT_FOUND"),
                ),
            ).status,
            "CHECKED_INSUFFICIENT",
        )
        self.assertEqual(
            assess_recovery(
                current, target(), (replace(first, spent_usd=Decimal("1")),)
            ).status,
            "WAIT_EXTERNAL",
        )
        overspent = assess_recovery(
            current, target(), (replace(first, spent_usd=Decimal("2")),)
        )
        self.assertEqual(
            overspent.reason_code, "RECOVERY_COST_CAP_OR_RECEIPTS_UNAVAILABLE"
        )
        with self.assertRaisesRegex(ValueError, "DP241_RECEIPT_INPUT_UNBOUNDED"):
            assess_recovery(current, target(), (first,) * 33)
        with self.assertRaisesRegex(ValueError, "DP241_ATTEMPT_CAP_INVALID"):
            plan(max_attempts=100)

    def test_target_tamper_and_missing_rights_are_preflight_blockers(self):
        current = target()
        with self.assertRaisesRegex(ValueError, "DP241_TARGET_LOCATOR_"):
            plan(source=replace(current, source_body=b"forged"))
        with self.assertRaisesRegex(ValueError, "DP241_TARGET_SOURCE_RIGHTS_UNCLEARED"):
            plan(
                source=replace(
                    current, capture=replace(current.capture, rights_status="UNKNOWN")
                )
            )
        with self.assertRaisesRegex(ValueError, "DP241_TARGET_QUESTION_NOT_SPECIFIC"):
            plan(source=replace(current, question="Original?"))


if __name__ == "__main__":
    unittest.main()
