"""DP-321 contract tests: all evidence identifiers are synthetic, NOT real gold."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))
from dichiarazioni_pubbliche.independent_reference_benchmark_v1 import (  # noqa: E402
    ReferenceCase,
    ReferenceLabel,
    ReferenceManifest,
    ReferencePrediction,
    ReferenceProof,
    benchmark_manifest_hash,
    compare_reference_reports,
    evaluate_independent_reference,
    validate_reference_manifest,
)


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def case(
    name: str,
    *,
    split="CALIBRATION",
    lineage=None,
    language="it",
    source_type="WRITTEN",
    claim_type="FACTUAL",
    risks=("DENIAL",),
    kind="DECIDABLE",
    rights="CLEARED",
    allowed=True,
):
    return ReferenceCase(
        case_id=f"case:{name}",
        lineage_id=lineage or f"lineage:{name}",
        split=split,
        language=language,
        source_type=source_type,
        claim_type=claim_type,
        risk_tags=risks,
        source_role="PRIMARY",
        ambiguity="DECIDABLE" if kind == "DECIDABLE" else "CONTESTED",
        source_version_sha256=h(name + ":capture"),
        locator_type="TEXT_POSITION",
        locator_start=0,
        locator_end=9,
        locator_sha256=h(name + ":locator"),
        original_quote_sha256=h(name + ":quote"),
        rights_state=rights,
        rights_receipt_sha256=h(name + ":rights"),
        license_ref="synthetic:license:" + name,
        reference_version="v1",
        proof=ReferenceProof(
            independent_source_receipt_sha256=h(name + ":source-proof"),
            independent_adjudication_sha256=h(name + ":adjudication"),
            adjudication_state="FINAL"
            if kind == "DECIDABLE"
            else "ABSTENTION_SCOPE_ONLY",
            annotator_ids=("independent:alice", "independent:bob"),
            adjudicator_id="independent:third",
            verifier_receipt_id="future:independent:" + name,
        ),
        label=ReferenceLabel(
            kind=kind,
            publication_allowed=allowed if kind == "DECIDABLE" else False,
            person_id="person:fixture" if kind == "DECIDABLE" else None,
            exact_quote_sha256=h(name + ":quote") if kind == "DECIDABLE" else None,
            endorsed=False if kind == "DECIDABLE" else None,
            factual_verdict=(
                "SUPPORTED" if claim_type == "FACTUAL" else "NOT_APPLICABLE"
            )
            if kind == "DECIDABLE"
            else None,
            denial_relation="UNRESOLVED" if kind == "DECIDABLE" else None,
        ),
    )


def manifest(*rows, generator="model:generator", tested="model:evaluated"):
    rows = rows or (case("first"),)
    base = ReferenceManifest(
        manifest_id="synthetic:benchmark",
        schema_version="independent-reference-v1",
        corpus_sha256=h("synthetic:corpus"),
        split_lock_sha256=h("synthetic:split"),
        rights_policy_version="synthetic-policy-v1",
        generator_id=generator,
        evaluated_model_id=tested,
        holdout_blind=True,
        cases=tuple(rows),
        manifest_sha256="0" * 64,
    )
    return replace(base, manifest_sha256=benchmark_manifest_hash(base))


def pred(row, *, state="PUBLIC", **kw):
    base = ReferencePrediction(
        case_id=row.case_id,
        state=state,
        person_id="person:fixture",
        quote_sha256=row.label.exact_quote_sha256,
        endorsed=False,
        factual_verdict="SUPPORTED"
        if row.claim_type == "FACTUAL"
        else "NOT_APPLICABLE",
        denial_relation="UNRESOLVED",
        claimed_rights_clearance=True,
        latency_ms=90,
        cost_usd=Decimal("0.02"),
        run_model_version="model:v1",
        source_version_sha256=row.source_version_sha256,
    )
    return replace(base, **kw)


def ALLOW_SIMULATED_EXTERNAL(_case):
    """A deliberately fake verifier. Never substitute for independent evidence."""
    return True


class IndependentReferenceBenchmarkTests(unittest.TestCase):
    def test_no_self_scored_gold_or_release_with_or_without_external_verifier(self):
        row = case("base")
        data = manifest(row)
        validate_reference_manifest(data)
        blocked = evaluate_independent_reference(data, (pred(row),))
        self.assertEqual(blocked.status, "BLOCKED_EXTERNAL_GOLD")
        self.assertEqual(blocked.reference_eligible_cases, 0)
        self.assertEqual(blocked.unverified_reference_cases, 1)
        self.assertIsNone(blocked.metrics["false_person"].rate)
        checked = evaluate_independent_reference(
            data,
            (pred(row),),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        self.assertEqual(
            checked.status, "CONTRACT_ONLY_NO_ACCEPTED_THRESHOLDS_OR_LIVE_GOLD"
        )
        self.assertEqual(checked.reference_eligible_cases, 1)
        self.assertFalse(checked.release_eligible)

    def test_hash_mutation_and_split_family_leak_blocked(self):
        row = case("a")
        with self.assertRaisesRegex(ValueError, "DP321_MANIFEST_HASH_MISMATCH"):
            validate_reference_manifest(
                replace(manifest(row), corpus_sha256=h("tampered"))
            )
        with self.assertRaisesRegex(ValueError, "DP321_SPLIT_LINEAGE_LEAKAGE"):
            validate_reference_manifest(
                manifest(row, case("b", split="HOLDOUT", lineage=row.lineage_id))
            )
        with self.assertRaisesRegex(ValueError, "DP321_CASE_ID_DUPLICATE"):
            validate_reference_manifest(manifest(row, row))
        with self.assertRaisesRegex(
            ValueError, "DP321_DUPLICATE_LINEAGE_NOT_INDEPENDENT"
        ):
            validate_reference_manifest(
                manifest(row, case("c", lineage=row.lineage_id))
            )

    def test_generator_self_label_and_unresolved_ambiguous_truth_refused(self):
        row = case("a")
        for ref in (
            replace(
                row,
                proof=replace(
                    row.proof, annotator_ids=("model:generator", "independent:bob")
                ),
            ),
            replace(row, proof=replace(row.proof, adjudicator_id="model:evaluated")),
        ):
            with self.assertRaisesRegex(ValueError, "DP321_INDEPENDENCE_CONFLICT"):
                validate_reference_manifest(manifest(ref))
        ambiguous = case("amb", kind="ABSTENTION_ONLY")
        validate_reference_manifest(manifest(ambiguous))
        with self.assertRaisesRegex(
            ValueError, "DP321_ABSTENTION_ONLY_HAS_SEMANTIC_GOLD"
        ):
            validate_reference_manifest(
                manifest(
                    replace(
                        ambiguous,
                        label=replace(ambiguous.label, factual_verdict="REFUTED"),
                    )
                )
            )

    def test_revoked_rights_cannot_claim_gold_publication(self):
        for rights in ("REVOKED", "DENIED", "UNKNOWN"):
            with self.subTest(rights=rights):
                with self.assertRaisesRegex(
                    ValueError, "DP321_RIGHTS_PUBLICATION_CONFLICT"
                ):
                    validate_reference_manifest(manifest(case(rights, rights=rights)))

    def test_privacy_risk_requires_independent_reference_before_public_label(self):
        row = case("private", risks=("PRIVACY",))
        with self.assertRaisesRegex(ValueError, "DP321_PRIVACY_CLEARANCE_NOT_ATTESTED"):
            validate_reference_manifest(manifest(row))
        confirmed = replace(
            row,
            label=replace(row.label, publication_allowed=False, privacy_sensitive=True),
        )
        report = evaluate_independent_reference(
            manifest(confirmed),
            (pred(confirmed),),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        self.assertEqual(report.metrics["rights_privacy_leak"].numerator, 1)
        self.assertEqual(report.metrics["unsupported_publication"].numerator, 1)

    def test_quoted_irony_judicial_allegation_and_temporal_uncertainty(self):
        reported = case("quoted", risks=("REPORTED_SPEECH", "IRONY"))
        allegation = case(
            "allegation", kind="ABSTENTION_ONLY", risks=("JUDICIAL", "JURISDICTION")
        )
        later = case("later", kind="ABSTENTION_ONLY", risks=("TEMPORAL_SUPERSESSION",))
        report = evaluate_independent_reference(
            manifest(reported, allegation, later),
            (pred(reported, endorsed=True), pred(allegation), pred(later)),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        self.assertEqual(report.metrics["false_endorsement"].numerator, 1)
        self.assertEqual(report.metrics["unsupported_publication"].numerator, 2)
        for risk in (
            "REPORTED_SPEECH",
            "IRONY",
            "JUDICIAL",
            "JURISDICTION",
            "TEMPORAL_SUPERSESSION",
        ):
            self.assertIn("risk:" + risk, report.strata)

    def test_legitimate_factual_and_opinion_positives_stay_measurable_but_not_approved(
        self,
    ):
        factual = case("factual")
        opinion = case("opinion", claim_type="OPINION", risks=("OPINION",))
        report = evaluate_independent_reference(
            manifest(factual, opinion),
            (pred(factual), pred(opinion)),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        self.assertEqual(
            (
                report.metrics["eligible_recall"].numerator,
                report.metrics["eligible_recall"].denominator,
            ),
            (2, 2),
        )
        self.assertEqual(report.metrics["false_person"].numerator, 0)
        self.assertEqual(report.metrics["false_factual_verdict"].denominator, 1)
        self.assertFalse(report.release_eligible)

    def test_drift_reports_no_release_threshold_or_cross_manifest_comparability(self):
        row = case("drift")
        data = manifest(row)
        baseline = evaluate_independent_reference(
            data,
            (pred(row),),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        current = evaluate_independent_reference(
            data,
            (pred(row, state="HELD"),),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        drift = compare_reference_reports(baseline, current)
        self.assertEqual(drift.status, "CONTRACT_ONLY_COMPARABLE")
        self.assertEqual(drift.metric_rate_deltas["sample_coverage"], -1.0)
        self.assertFalse(drift.release_eligible)
        other = case("other")
        other_report = evaluate_independent_reference(
            manifest(other),
            (pred(other),),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        self.assertEqual(
            compare_reference_reports(baseline, other_report).status,
            "BLOCKED_INCOMPARABLE_REFERENCE_SCOPE",
        )

    def test_drift_refuses_swapped_admitted_case_ids_with_equal_counts(self):
        a, b, c = case("a"), case("b"), case("c")
        data = manifest(a, b, c)
        predictions = (pred(a), pred(b), pred(c))
        baseline = evaluate_independent_reference(
            data,
            predictions,
            external_attestation_check=lambda row: (
                row.case_id in {a.case_id, b.case_id}
            ),
        )
        swapped = evaluate_independent_reference(
            data,
            predictions,
            external_attestation_check=lambda row: (
                row.case_id in {b.case_id, c.case_id}
            ),
        )
        self.assertEqual(baseline.manifest_sha256, swapped.manifest_sha256)
        self.assertEqual(baseline.reference_eligible_cases, 2)
        self.assertEqual(swapped.reference_eligible_cases, 2)
        self.assertEqual(baseline.metrics, swapped.metrics)
        self.assertNotEqual(
            baseline.admitted_case_ids_sha256, swapped.admitted_case_ids_sha256
        )
        self.assertEqual(baseline.status, "BLOCKED_EXTERNAL_GOLD")
        self.assertEqual(swapped.status, "BLOCKED_EXTERNAL_GOLD")
        drift = compare_reference_reports(baseline, swapped)
        self.assertEqual(drift.status, "BLOCKED_INCOMPARABLE_REFERENCE_SCOPE")
        self.assertEqual(drift.metric_rate_deltas, {})
        self.assertFalse(drift.release_eligible)
        legacy = replace(baseline, admitted_case_ids_sha256=None)
        self.assertEqual(
            compare_reference_reports(legacy, baseline).status,
            "BLOCKED_INCOMPARABLE_REFERENCE_SCOPE",
        )

    def test_independent_metric_numerators_denominators_are_separate(self):
        row = case("bad")
        wrong = pred(
            row,
            person_id="wrong",
            quote_sha256=h("cropped negation"),
            endorsed=True,
            factual_verdict="REFUTED",
            denial_relation="CONFIRMED",
        )
        report = evaluate_independent_reference(
            manifest(row),
            (wrong,),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        for metric in (
            "false_person",
            "false_quote",
            "false_endorsement",
            "false_factual_verdict",
            "false_denial",
        ):
            self.assertEqual(
                (report.metrics[metric].numerator, report.metrics[metric].denominator),
                (1, 1),
            )
        self.assertEqual(report.metrics["unsupported_publication"].numerator, 0)
        self.assertFalse(report.release_eligible)

    def test_ambiguous_and_revoked_publication_different_unsafe_signals(self):
        a = case("amb", kind="ABSTENTION_ONLY")
        b = case("rev", rights="REVOKED", allowed=False)
        report = evaluate_independent_reference(
            manifest(a, b),
            (pred(a), pred(b)),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        self.assertEqual(
            (
                report.metrics["unsupported_publication"].numerator,
                report.metrics["unsupported_publication"].denominator,
            ),
            (2, 2),
        )
        self.assertEqual(
            (
                report.metrics["rights_privacy_leak"].numerator,
                report.metrics["rights_privacy_leak"].denominator,
            ),
            (1, 2),
        )

    def test_100_percent_abstention_cannot_be_reported_as_success(self):
        a, b = case("a"), case("b")
        report = evaluate_independent_reference(
            manifest(a, b),
            (pred(a, state="ABSTAIN"), pred(b, state="HELD")),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        self.assertEqual(
            (
                report.metrics["abstention"].numerator,
                report.metrics["abstention"].denominator,
            ),
            (1, 2),
        )
        self.assertEqual(
            (
                report.metrics["eligible_recall"].numerator,
                report.metrics["eligible_recall"].denominator,
            ),
            (0, 2),
        )
        self.assertEqual(report.metrics["sample_coverage"].numerator, 0)
        self.assertFalse(report.release_eligible)

    def test_missing_prediction_does_not_disappear_from_denominator(self):
        a, b = case("a"), case("b")
        result = evaluate_independent_reference(
            manifest(a, b),
            (pred(a),),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        self.assertEqual(result.missing_predictions, 1)
        self.assertEqual(result.metrics["eligible_recall"].denominator, 2)
        self.assertEqual(result.metrics["abstention"].numerator, 1)

    def test_unattested_reference_cannot_hide_abstention_or_missing_predictions(self):
        accepted = case("accepted")
        denied = case("denied", kind="ABSTENTION_ONLY")
        missing = case("missing")
        report = evaluate_independent_reference(
            manifest(accepted, denied, missing),
            (pred(accepted), pred(denied, state="ABSTAIN")),
            external_attestation_check=lambda row: row.case_id == accepted.case_id,
        )
        self.assertEqual(report.status, "BLOCKED_EXTERNAL_GOLD")
        self.assertEqual(report.reference_eligible_cases, 1)
        self.assertEqual(report.unverified_reference_cases, 2)
        self.assertEqual(report.missing_predictions, 1)
        self.assertEqual(
            (
                report.metrics["abstention"].numerator,
                report.metrics["abstention"].denominator,
            ),
            (2, 3),
        )
        self.assertEqual(
            (
                report.metrics["sample_coverage"].numerator,
                report.metrics["sample_coverage"].denominator,
            ),
            (1, 3),
        )
        self.assertEqual(report.metrics["false_person"].denominator, 1)
        self.assertEqual(report.metrics["eligible_recall"].denominator, 1)
        self.assertEqual(
            report.strata["ambiguity:CONTESTED"]["abstention"].numerator, 1
        )
        self.assertEqual(
            report.strata["ambiguity:CONTESTED"]["abstention"].denominator, 1
        )
        self.assertFalse(report.release_eligible)

    def test_coverage_counts_observed_public_predictions_without_reference_gold(self):
        first = case("public-unverified")
        second = case("abstained-unverified")
        third = case("missing-unverified")
        report = evaluate_independent_reference(
            manifest(first, second, third),
            (pred(first), pred(second, state="ABSTAIN")),
        )
        self.assertEqual(report.status, "BLOCKED_EXTERNAL_GOLD")
        self.assertEqual(report.reference_eligible_cases, 0)
        self.assertEqual(report.unverified_reference_cases, 3)
        self.assertEqual(report.missing_predictions, 1)
        self.assertEqual(
            (report.metrics["sample_coverage"].numerator,
             report.metrics["sample_coverage"].denominator), (1, 3)
        )
        self.assertEqual(
            (report.metrics["abstention"].numerator,
             report.metrics["abstention"].denominator), (2, 3)
        )
        for error in ("false_person", "false_quote", "false_factual_verdict"):
            self.assertIsNone(report.metrics[error].rate)
        self.assertFalse(report.release_eligible)

    def test_strata_expose_language_claim_source_split_and_risk(self):
        a = case("a", risks=("DENIAL", "NEGATION"))
        b = case(
            "b",
            language="de",
            split="HOLDOUT",
            source_type="AUDIO",
            claim_type="OPINION",
            risks=("JUDICIAL",),
        )
        out = evaluate_independent_reference(
            manifest(a, b),
            (pred(a), pred(b)),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        for key in (
            "language:it",
            "language:de",
            "source:WRITTEN",
            "source:AUDIO",
            "claim:FACTUAL",
            "claim:OPINION",
            "risk:DENIAL",
            "risk:NEGATION",
            "risk:JUDICIAL",
            "split:CALIBRATION",
            "split:HOLDOUT",
        ):
            self.assertEqual(out.strata[key]["sample_coverage"].denominator, 1)

    def test_replay_wrong_case_and_version_invalid(self):
        row = case("one")
        p = pred(row)
        for predictions, code in (
            ((p, p), "DP321_PREDICTION_DUPLICATE"),
            ((replace(p, case_id="case:unknown"),), "DP321_PREDICTION_FOREIGN"),
            (
                (replace(p, source_version_sha256=h("new source")),),
                "DP321_PREDICTION_SOURCE_VERSION_DRIFT",
            ),
        ):
            with self.assertRaisesRegex(ValueError, code):
                evaluate_independent_reference(
                    manifest(row),
                    predictions,
                    external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
                )

    def test_cost_latency_zero_denominator_and_verifier_outage(self):
        row = case("a", kind="ABSTENTION_ONLY")
        p = pred(row, state="ABSTAIN", latency_ms=150, cost_usd=Decimal("0.03"))
        report = evaluate_independent_reference(
            manifest(row),
            (p,),
            external_attestation_check=ALLOW_SIMULATED_EXTERNAL,
        )
        self.assertEqual(report.cost_total_usd, Decimal("0.03"))
        self.assertEqual(report.latency_observed_count, 1)
        self.assertEqual(report.latency_total_ms, 150)
        self.assertEqual(report.metrics["false_factual_verdict"].denominator, 0)
        self.assertIsNone(report.metrics["false_factual_verdict"].rate)
        self.assertIsNone(report.metrics["false_factual_verdict"].ci95_lower)
        self.assertIsNone(report.drift_comparable_to)

        def broken(_):
            raise RuntimeError("verifier unavailable")

        blocked = evaluate_independent_reference(
            manifest(row),
            (p,),
            external_attestation_check=broken,
        )
        self.assertEqual(blocked.status, "BLOCKED_EXTERNAL_GOLD")
        self.assertEqual(blocked.reference_eligible_cases, 0)


if __name__ == "__main__":
    unittest.main()
