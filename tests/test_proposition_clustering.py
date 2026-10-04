import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.proposition_clustering import (  # noqa: E402
    APPROVE_CLUSTER_MEMBER_SQL_V1,
    APPROVE_DERIVATION_CANDIDATE_SQL_V1,
    APPROVE_DERIVATION_FAMILY_SQL_V1,
    APPROVE_PROPOSITION_CLUSTER_SQL_V1,
    ContentDerivationCandidateRecord,
    PropositionInput,
    PropositionMatch,
    classify_proposition_pair,
    detect_exact_body_derivation,
    make_cluster,
    make_cluster_member,
    make_derivation_candidate,
    make_derivation_family,
    normalize_proposition,
    propose_evidence_independence_group,
    token_jaccard,
)


class PropositionClusteringTests(unittest.TestCase):
    def test_normalization_is_stable(self):
        self.assertEqual(
            normalize_proposition("  L'IMPRONTA 33 — non era sangue! "),
            "l impronta 33 non era sangue",
        )
        self.assertEqual(token_jaccard("DNA Sempio", "Sempio DNA"), 1.0)

    def test_duplicate_extraction_requires_same_source_selector(self):
        left = PropositionInput(
            member_type="CLAIM_CANDIDATE",
            member_id="candidate:1",
            content_id="content:1",
            normalized_text="I test sull'impronta 33 furono negativi.",
            provenance_key="passage:1",
            entity_keys=("entity:impronta33",),
        )
        right = PropositionInput(
            member_type="CLAIM_CANDIDATE",
            member_id="candidate:2",
            content_id="content:1",
            normalized_text="I test sull'impronta 33 furono negativi.",
            provenance_key="passage:1",
            entity_keys=("entity:impronta33",),
        )
        match = classify_proposition_pair(left, right)
        self.assertEqual(match.match_class, "DUPLICATE_EXTRACTION")
        self.assertEqual(match.method, "SOURCE_SELECTOR_OVERLAP")

    def test_same_proposition_across_sources_is_not_duplicate_extraction(self):
        left = PropositionInput(
            member_type="ATOMIC_CLAIM", member_id="claim:1", content_id="content:1",
            normalized_text="Il computer non risultava acceso dopo il 10 agosto.",
            provenance_key="passage:1",
        )
        right = PropositionInput(
            member_type="CLAIM_CANDIDATE", member_id="candidate:2", content_id="content:2",
            normalized_text="Il computer non risultava acceso dopo il 10 agosto.",
            provenance_key="passage:9",
        )
        match = classify_proposition_pair(left, right)
        self.assertEqual(match.match_class, "SAME_PROPOSITION")
        self.assertEqual(match.method, "EXACT_NORMALIZED")

    def test_related_but_different_is_not_same_proposition(self):
        left = PropositionInput(
            member_type="ATOMIC_CLAIM", member_id="claim:1", content_id="content:1",
            normalized_text="I test sull'impronta 33 per il sangue furono negativi.",
            entity_keys=("entity:impronta33",), topic_keys=("topic:sangue",),
        )
        right = PropositionInput(
            member_type="CLAIM_CANDIDATE", member_id="candidate:2", content_id="content:2",
            normalized_text="Nell'impronta 33 vi erano sei o sette minuzie coincidenti.",
            entity_keys=("entity:impronta33",), topic_keys=("topic:impronta",),
        )
        match = classify_proposition_pair(left, right)
        self.assertEqual(match.match_class, "RELATED")
        self.assertNotEqual(match.match_class, "SAME_PROPOSITION")

    def test_unrelated_claims_can_be_classified_different(self):
        left = PropositionInput(
            member_type="ATOMIC_CLAIM", member_id="claim:1", content_id="content:1",
            normalized_text="La pena fu ridotta per il rito abbreviato.",
        )
        right = PropositionInput(
            member_type="CLAIM_CANDIDATE", member_id="candidate:2", content_id="content:2",
            normalized_text="Il cromosoma Y era incompleto.",
        )
        match = classify_proposition_pair(left, right)
        self.assertEqual(match.match_class, "DIFFERENT")
        self.assertTrue(match.contradicting_features)

    def test_cluster_member_keeps_related_candidate_without_deleting_it(self):
        cluster = make_cluster("I test sull'impronta 33 furono negativi.", "MANUAL_REVIEW")
        candidate = PropositionInput(
            member_type="CLAIM_CANDIDATE", member_id="candidate:1", content_id="content:1",
            normalized_text="I test sull'impronta 33 per il sangue furono negativi.",
        )
        match = PropositionMatch(
            match_class="RELATED", method="MANUAL_REVIEW", lexical_score=0.6,
            supporting_features=({"code": "SAME_CASE_DIFFERENT_PROPOSITION"},),
        )
        member = make_cluster_member(cluster, candidate, match)
        self.assertEqual(member.match_class, "RELATED")
        self.assertEqual(member.status, "CANDIDATE")
        self.assertEqual(member.target_columns()["claim_candidate_id"], "candidate:1")

    def test_exact_body_hash_derivation_is_candidate_not_approval(self):
        family = make_derivation_family("content:root")
        edge = detect_exact_body_derivation(
            family=family,
            derived_content_id="content:copy",
            origin_content_id="content:root",
            derived_sha256="a" * 64,
            origin_sha256="a" * 64,
        )
        self.assertIsNotNone(edge)
        self.assertEqual(edge.relation_type, "REPUBLICATION")
        self.assertEqual(edge.derivation_method, "EXACT_BODY_HASH")
        self.assertEqual(edge.status, "CANDIDATE")
        self.assertEqual(edge.lexical_score, 1.0)

    def test_ten_copied_articles_fit_one_family_without_deletion(self):
        family = make_derivation_family("content:root")
        edges = [
            make_derivation_candidate(
                family=family,
                derived_content_id=f"content:copy:{i}",
                origin_content_id="content:root",
                relation_type="SYNDICATION",
                method="EXPLICIT_SOURCE_CREDIT",
                supporting_features=({"code": "CREDITS_ROOT"},),
            )
            for i in range(10)
        ]
        self.assertEqual(len(edges), 10)
        self.assertEqual(len({edge.id for edge in edges}), 10)
        self.assertEqual({edge.family_id for edge in edges}, {family.id})
        self.assertEqual({edge.origin_content_id for edge in edges}, {"content:root"})
        self.assertEqual({edge.derived_content_id for edge in edges}, {f"content:copy:{i}" for i in range(10)})

    def test_independence_handoff_requires_explicit_approved_family_and_edges(self):
        family = make_derivation_family("content:root")
        edge = make_derivation_candidate(
            family=family,
            derived_content_id="content:copy",
            origin_content_id="content:root",
            relation_type="REPUBLICATION",
            method="EXACT_BODY_HASH",
            supporting_features=({"code": "EXACT_BODY_SHA256"},),
        )
        self.assertIsNone(propose_evidence_independence_group(family, [edge]))

        approved_family = replace(family, status="APPROVED")
        self.assertIsNone(propose_evidence_independence_group(approved_family, [edge]))

        approved_edge = replace(edge, status="APPROVED")
        proposal = propose_evidence_independence_group(approved_family, [approved_edge])
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.content_ids, ("content:copy", "content:root"))
        self.assertTrue(proposal.proposed_group.startswith("derivation:"))

    def test_approval_sql_records_review_and_does_not_touch_evidence(self):
        for sql in (
            APPROVE_PROPOSITION_CLUSTER_SQL_V1,
            APPROVE_CLUSTER_MEMBER_SQL_V1,
            APPROVE_DERIVATION_FAMILY_SQL_V1,
            APPROVE_DERIVATION_CANDIDATE_SQL_V1,
        ):
            lowered = sql.lower()
            self.assertIn("insert into review_event", lowered)
            self.assertIn("action", lowered)
            self.assertIn("'approved'", lowered)
            self.assertNotIn("update evidence", lowered)
            self.assertNotIn("insert into evidence", lowered)
            self.assertNotIn("finding", lowered)
            self.assertNotIn("publication", lowered)

    def test_derivation_refuses_self_edge(self):
        family = make_derivation_family("content:root")
        with self.assertRaisesRegex(ValueError, "DERIVATION_SELF_REFUSED"):
            ContentDerivationCandidateRecord(
                id="edge:self",
                family_id=family.id,
                derived_content_id="content:root",
                origin_content_id="content:root",
                relation_type="REPUBLICATION",
                derivation_method="MANUAL_REVIEW",
            )


if __name__ == "__main__":
    unittest.main()
