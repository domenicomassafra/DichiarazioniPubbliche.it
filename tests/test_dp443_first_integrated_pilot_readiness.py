"""DP-443 source-only packet checks, never runtime acceptance."""

import hashlib
import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.bounded_private_pilot_manifest_v1 import (
    PrivatePilotSample,
    freeze_private_pilot_manifest,
)
from dichiarazioni_pubbliche.first_integrated_pilot_readiness_v1 import (
    PilotLineage,
    PilotProof,
    evaluate_first_integrated_pilot_readiness,
    fingerprint_pilot_lineage,
)


POSITIVE = (
    "SIGNED_MANIFEST",
    "SOURCE_RIGHTS",
    "CAPTURE_PASSAGE",
    "ORIGINAL_STATEMENT",
    "FACTUAL_ABSTENTION",
    "OPINION_SEPARATION",
    "PERSON_TOPIC",
    "READER_API",
    "READER_HTML",
    "READER_SEARCH",
    "READER_LINKED_DATA",
    "CORRECTION_REPLY",
    "REVOCATION_REPLAY",
    "MINIPC_READBACK",
    "INDEPENDENT_GOLD",
    "LEGAL_REVIEW",
    "PRIVACY_REVIEW",
    "EDITORIAL_AUTHORITY",
    "COST_ROLLBACK",
    "SIGNED_SCALING_DECISION",
)
NEGATIVE = (
    "RIGHTS_DENIED_HOLD",
    "MISATTRIBUTION_HOLD",
    "UNSUPPORTED_INFERENCE_HOLD",
    "REVOKED_REPLAY_HOLD",
    "PRIVATE_LEAK_HOLD",
)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class TestFirstPilotReadiness(unittest.TestCase):
    def sample(self, ident="1"):
        content = "content-" + ident
        source_hash = digest("source" if ident == "1" else "source-" + ident)
        return PrivatePilotSample(
            sample_id="case-" + ident,
            content_id=content,
            source_family="official-records" if ident == "1" else "secondary-news",
            language="it" if ident == "1" else "de",
            medium="written",
            rights_reference="rights:external:" + ident,
            capture_permission="APPROVED_EXTERNAL_REQUIRED",
            source_locator="https://example.org/pilot/" + ident,
            source_version="v1",
            source_version_sha256=source_hash,
            person_id="person-" + ident,
            attribution_role="AUTHOR",
            media_type="text/plain",
            rights_source_family="official-records"
            if ident == "1"
            else "secondary-news",
            rights_content_id=content,
            rights_version_sha256=source_hash,
            rights_source_locator="https://example.org/pilot/" + ident,
        )

    def setUp(self):
        self.manifest = freeze_private_pilot_manifest([self.sample()])
        self.lineage = PilotLineage(
            sample_id="case-1",
            content_id="content-1",
            language="it",
            source_sha256=digest("source"),
            capture_sha256=digest("capture"),
            passage_sha256=digest("passage"),
            quote_sha256=digest("literal quote"),
            statement_sha256=digest("statement"),
            reader_fingerprint_sha256=digest("public"),
            correction_fingerprint_sha256=digest("corrected"),
            revocation_fingerprint_sha256=digest("revoked"),
            git_commit="a" * 40,
            minipc_host="udodo",
        )

    def proof(self, stage, **overrides):
        fields = dict(
            stage=stage,
            outcome="HOLD" if stage in NEGATIVE else "PASS",
            sample_id="case-1",
            receipt_ref=f"urn:external:receipt:{stage}",
            signer_ref=f"urn:external:signer:{stage}",
            receipt_sha256=digest(stage),
            manifest_sha256=self.manifest.manifest_sha256,
            lineage_sha256=fingerprint_pilot_lineage(self.lineage, self.manifest),
            observed_host="udodo" if stage == "MINIPC_READBACK" else None,
        )
        return PilotProof(**(fields | overrides))

    def complete(self):
        return tuple(self.proof(stage) for stage in POSITIVE + NEGATIVE)

    def evaluate(self, proofs=(), *, lineage=None, manifest=None):
        return evaluate_first_integrated_pilot_readiness(
            self.manifest if manifest is None else manifest,
            self.lineage if lineage is None else lineage,
            proofs,
        )

    def test_missing_external_receipts_is_no_go(self):
        result = self.evaluate()
        self.assertEqual(result.disposition, "NO-GO")
        self.assertFalse(result.packet_complete)
        self.assertIn("MISSING:MINIPC_READBACK", result.blockers)
        self.assertIn("MISSING:RIGHTS_DENIED_HOLD", result.blockers)

    def test_structurally_complete_refs_still_never_authorize(self):
        result = self.evaluate(self.complete())
        self.assertEqual(result.disposition, "NO-GO")
        self.assertTrue(result.packet_complete)
        self.assertFalse(result.scaling_authorized)
        self.assertEqual(result.blockers, ("UNVERIFIED_EXTERNAL_AUTHORITY",))

    def test_verbatim_or_identical_captured_bytes_are_not_false_drift(self):
        # Original source and Capture may contain identical bytes, likewise a
        # literal Statement and the extracted quote. This cannot grant authority.
        same_bytes = replace(
            self.lineage,
            capture_sha256=self.lineage.source_sha256,
            statement_sha256=self.lineage.quote_sha256,
        )
        receipts = tuple(
            replace(
                proof,
                lineage_sha256=fingerprint_pilot_lineage(same_bytes, self.manifest),
            )
            for proof in self.complete()
        )
        result = self.evaluate(receipts, lineage=same_bytes)
        self.assertTrue(result.packet_complete)
        self.assertEqual(result.disposition, "NO-GO")

    def test_missing_one_reader_or_negative_hold_is_not_complete(self):
        for absent in ("READER_LINKED_DATA", "MISATTRIBUTION_HOLD", "INDEPENDENT_GOLD"):
            with self.subTest(absent=absent):
                proofs = tuple(
                    proof for proof in self.complete() if proof.stage != absent
                )
                result = self.evaluate(proofs)
                self.assertIn("MISSING:" + absent, result.blockers)
                self.assertFalse(result.packet_complete)

    def test_negative_hold_cannot_be_marked_pass_or_positive_marked_hold(self):
        for stage, outcome in (
            ("RIGHTS_DENIED_HOLD", "PASS"),
            ("SOURCE_RIGHTS", "HOLD"),
        ):
            with self.subTest(stage=stage):
                proofs = tuple(
                    self.proof(name, outcome=outcome)
                    if name == stage
                    else self.proof(name)
                    for name in POSITIVE + NEGATIVE
                )
                self.assertIn(
                    "OUTCOME_INVALID:" + stage, self.evaluate(proofs).blockers
                )

    def test_stale_manifest_lineage_and_wrong_host_are_held(self):
        for stage, override, code in (
            (
                "SOURCE_RIGHTS",
                {"manifest_sha256": digest("old manifest")},
                "MANIFEST_BINDING_INVALID",
            ),
            (
                "ORIGINAL_STATEMENT",
                {"lineage_sha256": digest("other source")},
                "LINEAGE_BINDING_INVALID",
            ),
            (
                "MINIPC_READBACK",
                {"observed_host": "mac-studio-dodo"},
                "MINIPC_HOST_INVALID",
            ),
        ):
            with self.subTest(stage=stage):
                proofs = tuple(
                    self.proof(name, **override) if name == stage else self.proof(name)
                    for name in POSITIVE + NEGATIVE
                )
                self.assertIn(code + ":" + stage, self.evaluate(proofs).blockers)

    def test_duplicate_or_reused_attestation_cannot_fill_multiple_gates(self):
        receipts = list(self.complete())
        self.assertIn(
            "DUPLICATE:SOURCE_RIGHTS", self.evaluate((*receipts, receipts[1])).blockers
        )
        receipts[2] = replace(receipts[2], receipt_ref=receipts[1].receipt_ref)
        self.assertIn("RECEIPT_REUSED", self.evaluate(receipts).blockers)

    def test_malformed_or_local_proof_rejected(self):
        receipts = list(self.complete())
        receipts[0] = replace(receipts[0], receipt_ref="file:///tmp/fixture.json")
        self.assertIn(
            "RECEIPT_INVALID:SIGNED_MANIFEST", self.evaluate(receipts).blockers
        )

    def test_manifest_or_lineage_not_structurally_proven(self):
        changed = replace(self.manifest, manifest_sha256=digest("tampered"))
        self.assertIn(
            "MANIFEST_INVALID",
            self.evaluate(self.complete(), manifest=changed).blockers,
        )
        changed_lineage = replace(self.lineage, capture_sha256="malformed")
        self.assertIn(
            "LINEAGE_INVALID",
            self.evaluate(self.complete(), lineage=changed_lineage).blockers,
        )
        unchanged_projection = replace(
            self.lineage,
            revocation_fingerprint_sha256=self.lineage.reader_fingerprint_sha256,
        )
        self.assertIn(
            "LINEAGE_INVALID",
            self.evaluate(self.complete(), lineage=unchanged_projection).blockers,
        )
        source_drift = replace(
            self.lineage, source_sha256=digest("other source version")
        )
        self.assertIn(
            "LINEAGE_INVALID", self.evaluate((), lineage=source_drift).blockers
        )

    def test_dp235_held_rights_cannot_look_like_complete_packet(self):
        denied = replace(
            self.sample(),
            rights_reference=None,
            rights_source_family=None,
            rights_content_id=None,
            rights_version_sha256=None,
            rights_source_locator=None,
        )
        held_manifest = freeze_private_pilot_manifest([denied])
        self.assertEqual(held_manifest.review_status, "HELD")
        self.assertIn(
            "MANIFEST_HELD", self.evaluate((), manifest=held_manifest).blockers
        )

    def test_dp235_explicit_budget_is_not_a_manifest_tamper(self):
        bounded = freeze_private_pilot_manifest(
            [self.sample()],
            max_samples=1,
            budget_eur_cents=50,
        )
        result = self.evaluate((), manifest=bounded)
        self.assertNotIn("MANIFEST_INVALID", result.blockers)
        self.assertEqual(result.disposition, "NO-GO")

    def test_independent_gold_and_qualified_review_cannot_share_a_signer(self):
        receipts = tuple(
            self.proof(stage, signer_ref="urn:external:signer:SIGNED_MANIFEST")
            if stage in ("INDEPENDENT_GOLD", "LEGAL_REVIEW")
            else self.proof(stage)
            for stage in POSITIVE + NEGATIVE
        )
        result = self.evaluate(receipts)
        self.assertIn("QUALIFIED_SIGNER_NOT_INDEPENDENT", result.blockers)

    def test_bundle_bound_and_unsupported_stage_fail_closed(self):
        self.assertIn(
            "PROOF_COUNT_EXCEEDED", self.evaluate(self.complete() * 3).blockers
        )
        self.assertIn(
            "UNKNOWN_STAGE:ARBITRARY",
            self.evaluate((*self.complete(), self.proof("ARBITRARY"))).blockers,
        )

    def test_multi_sample_manifest_is_outside_one_sample_contract(self):
        additional = self.sample("2")
        expanded = freeze_private_pilot_manifest([*self.manifest.samples, additional])
        self.assertIn(
            "MANIFEST_SCOPE_INVALID",
            self.evaluate(self.complete(), manifest=expanded).blockers,
        )


if __name__ == "__main__":
    unittest.main()
