"""DP-418 source-exact operator compare against independently read target refs."""

from __future__ import annotations

import json
import unittest

from dichiarazioni_pubbliche.candidate_matching import (
    MATCHING_VERSION,
    deterministic_match_result_id,
    deterministic_match_run_id,
    matching_input_fingerprint,
    rank_candidate_matches,
)
from dichiarazioni_pubbliche.studio_candidate_review_ui import (
    build_candidate_comparison_read_model,
    render_candidate_comparison_workspace,
)
from tests.test_candidate_matching import item
from tests.test_studio_candidate_review_handoff import MatchStore, PromotionContext


class TargetSourceReader:
    """Independent persisted target-Context read fixture (not match output)."""

    def __init__(self, targets, *, candidate=None):
        self.snapshots = {
            (target.proposition.member_type, target.proposition.member_id): {
                "member_type": target.proposition.member_type,
                "member_id": target.proposition.member_id,
                "content_id": target.proposition.content_id,
                "passage_id": target.proposition.provenance_key,
                "capture_id": "capture:target:" + str(i),
                "capture_sha256": format(i + 15, "064x"),
                "rights_status": "CLEARED",
                "capture_status": "CAPTURED",
                "capture_hold_status": "NONE",
            }
            for i, target in enumerate(targets)
        }
        if candidate is not None:
            proposition = candidate.proposition
            self.snapshots[(proposition.member_type, proposition.member_id)] = {
                "member_type": proposition.member_type,
                "member_id": proposition.member_id,
                "content_id": proposition.content_id,
                "passage_id": proposition.provenance_key,
                "capture_id": "capture:1",
                "capture_sha256": "c" * 64,
                "rights_status": "CLEARED",
                "capture_status": "CAPTURED",
                "capture_hold_status": "NONE",
            }
        self.calls = []

    def source_context(self, target_type, target_id):
        self.calls.append((target_type, target_id))
        value = self.snapshots.get((target_type, target_id))
        return dict(value) if value is not None else None


def persisted_comparison(*, duplicate=False):
    source = MatchStore()
    source.targets = (
        item(
            "ATOMIC_CLAIM",
            "claim:same",
            "Il primo evento fu registrato.",
            content_id="content:1" if duplicate else "content:same",
            provenance_key="passage:1" if duplicate else "passage:same",
        ),
        item(
            "ATOMIC_CLAIM",
            "claim:related",
            "Il secondo evento fu registrato.",
            content_id="content:related",
            provenance_key="passage:related",
        ),
        item(
            "ATOMIC_CLAIM",
            "claim:uncertain",
            "Il documento è registrato.",
            content_id="content:uncertain",
            provenance_key="passage:uncertain",
        ),
    )
    source.fingerprint = matching_input_fingerprint(source.candidate, source.targets)
    source.run_id = deterministic_match_run_id("candidate:1", source.fingerprint)
    computed = rank_candidate_matches(source.candidate, source.targets)
    source.run = {
        "id": source.run_id,
        "claim_candidate_id": "candidate:1",
        "matching_version": MATCHING_VERSION,
        "input_fingerprint": source.fingerprint,
        "status": "COMPLETED",
        "result_count": len(computed),
    }
    source.rows = tuple(
        {
            "id": deterministic_match_result_id(
                source.run_id,
                row.target.proposition.member_type,
                row.target.proposition.member_id,
            ),
            "rank": row.rank,
            "target_type": row.target.proposition.member_type,
            "target_id": row.target.proposition.member_id,
            "match_class": row.match.match_class,
            "method": row.match.method,
            "matching_version": MATCHING_VERSION,
            "status": "CANDIDATE",
            "lexical_score": row.match.lexical_score,
            "disposition": row.disposition,
            "proposition_cluster_id": row.cluster_id,
            "supporting_features": list(row.supporting_features),
            "contradicting_features": list(row.contradicting_features),
            "private_text": "SECRET NEVER IN COMPARE",
        }
        for row in computed
    )
    return source, PromotionContext(), TargetSourceReader(
        source.targets, candidate=source.candidate,
    )


class PersistedOperatorComparisonTests(unittest.TestCase):
    def preview(self, match=None, promotion=None, targets=None):
        if match is None:
            match, promotion, targets = persisted_comparison()
        return build_candidate_comparison_read_model(
            match,
            promotion,
            targets,
            run_id=match.run_id,
            claim_candidate_id="candidate:1",
        )

    def test_persisted_match_and_independent_target_source_comparison(self):
        match, promotion, target_reader = persisted_comparison()
        read = self.preview(match, promotion, target_reader)
        self.assertEqual(read["currentness"], "CURRENT")
        self.assertEqual(read["matching_version"], MATCHING_VERSION)
        self.assertEqual(read["candidate"]["content_id"], "content:1")
        self.assertEqual(read["candidate"]["passage_id"], "passage:1")
        self.assertEqual(read["candidate"]["capture_id"], "capture:1")
        self.assertEqual(read["candidate"]["capture_sha256"], "c" * 64)
        self.assertEqual(read["candidate"]["rights_status"], "CLEARED")
        self.assertEqual(len(read["comparisons"]), 3)
        self.assertEqual(
            {row["target_id"]: row["relation"] for row in read["comparisons"]},
            {
                "claim:same": "SAME_PROPOSITION",
                "claim:related": "RELATED",
                "claim:uncertain": "UNCERTAIN",
            },
        )
        for row in read["comparisons"]:
            self.assertIn(
                row["relation"],
                {
                    "DUPLICATE_EXTRACTION",
                    "SAME_PROPOSITION",
                    "RELATED",
                    "DIFFERENT",
                    "UNCERTAIN",
                },
            )
            self.assertEqual(
                row["source"]["passage_id"],
                "passage:" + row["target_id"].split(":", 1)[1],
            )
            self.assertEqual(row["source"]["member_id"], row["target_id"])
            self.assertTrue(row["matching_method"])
            self.assertIsInstance(row["supporting_feature_codes"], tuple)
            self.assertIsInstance(row["contradicting_feature_codes"], tuple)
            self.assertFalse(row["equivalence_approved"])
            self.assertFalse(row["promotion_authority"])
        self.assertIn(
            "DP117_TRANSACTIONAL_PROMOTION_REVALIDATION_REQUIRED",
            read["promotion_blockers"],
        )
        self.assertFalse(read["promotion_authority"])
        self.assertFalse(read["review_authority"])
        self.assertFalse(read["publication_authority"])
        self.assertEqual(
            len(target_reader.calls), 8,
            "candidate and each target must be independently re-read",
        )
        self.assertEqual(read, self.preview(match, promotion, target_reader))
        html = render_candidate_comparison_workspace(read).decode()
        for expected in (
            "claim:same",
            "claim:related",
            "claim:uncertain",
            "Capture",
            "Passage",
            "Diritti fonte CLEARED",
            "Proposta non approvata",
        ):
            self.assertIn(expected, html)
        for leak in (
            "SECRET NEVER",
            "Il primo evento fu",
            "lexical_score",
            "normalized_text",
            "private_text",
            "0.99",
        ):
            self.assertNotIn(leak, html + json.dumps(read))

    def test_cross_candidate_target_and_source_bindings_fail_closed(self):
        for change in (
            {"content_id": "content:other"},
            {"passage_id": "passage:other"},
            {"member_id": "claim:foreign"},
            {"member_type": "CLAIM_CANDIDATE"},
        ):
            match, promotion, targets = persisted_comparison()
            key = ("ATOMIC_CLAIM", "claim:same")
            targets.snapshots[key].update(change)
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(
                    ValueError, "DP418_COMPARISON_TARGET_BINDING_INVALID"
                ),
            ):
                self.preview(match, promotion, targets)
        match, promotion, targets = persisted_comparison()
        promotion.data["content_id"] = "content:foreign"
        with self.assertRaisesRegex(ValueError, "PROMOTION_CONTEXT_BINDING_MISMATCH"):
            self.preview(match, promotion, targets)

    def test_rights_revoked_or_candidate_capture_held_never_equivalent(self):
        match, promotion, targets = persisted_comparison()
        targets.snapshots[("ATOMIC_CLAIM", "claim:same")]["rights_status"] = "REVOKED"
        result = self.preview(match, promotion, targets)
        revoked = next(
            row for row in result["comparisons"] if row["target_id"] == "claim:same"
        )
        self.assertEqual(revoked["operator_status"], "BLOCKED_TARGET_SOURCE_RIGHTS")
        self.assertEqual(revoked["action"], "RECHECK_TARGET_RIGHTS")
        self.assertFalse(revoked["comparison_usable"])
        self.assertFalse(result["promotion_authority"])
        promotion.data["passages"][0]["capture_hold_status"] = "RIGHTS"
        held = self.preview(match, promotion, targets)
        self.assertIn("DP418_CANDIDATE_SOURCE_HELD", held["promotion_blockers"])
        self.assertTrue(
            all(not row["comparison_usable"] for row in held["comparisons"])
        )

    def test_candidate_rights_must_be_independently_rechecked(self):
        for status in ("REVOKED", "UNKNOWN", "EXPIRED", "DENIED"):
            match, promotion, targets = persisted_comparison()
            candidate_key = ("CLAIM_CANDIDATE", "candidate:1")
            targets.snapshots[candidate_key]["rights_status"] = status
            preview = self.preview(match, promotion, targets)
            with self.subTest(rights_status=status):
                self.assertIn(
                    "DP418_CANDIDATE_SOURCE_RIGHTS",
                    preview["promotion_blockers"],
                )
                self.assertTrue(all(
                    not row["comparison_usable"] for row in preview["comparisons"]
                ))
        match, promotion, targets = persisted_comparison()
        targets.snapshots.pop(("CLAIM_CANDIDATE", "candidate:1"))
        preview = self.preview(match, promotion, targets)
        self.assertIn("DP418_CANDIDATE_SOURCE_UNAVAILABLE", preview["promotion_blockers"])
        self.assertTrue(all(not row["comparison_usable"] for row in preview["comparisons"]))

    def test_candidate_capture_version_mismatch_or_revocation_race_is_refused(self):
        match, promotion, targets = persisted_comparison()
        targets.snapshots[("CLAIM_CANDIDATE", "candidate:1")]["capture_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "CANDIDATE_SOURCE_BINDING_INVALID"):
            self.preview(match, promotion, targets)

        match, promotion, targets = persisted_comparison()

        class RevokedCandidateDuringRead(TargetSourceReader):
            def source_context(self, kind, identifier):
                row = super().source_context(kind, identifier)
                if (kind, identifier) == ("CLAIM_CANDIDATE", "candidate:1") and (
                    self.calls.count((kind, identifier)) == 2
                ):
                    row["rights_status"] = "REVOKED"
                return row

        volatile = RevokedCandidateDuringRead(match.targets, candidate=match.candidate)
        with self.assertRaisesRegex(ValueError, "CHANGED_DURING_READ"):
            self.preview(match, promotion, volatile)

    def test_missing_or_stale_target_readback_does_not_forge_equal_source(self):
        match, promotion, targets = persisted_comparison()
        targets.snapshots.pop(("ATOMIC_CLAIM", "claim:same"))
        missing = self.preview(match, promotion, targets)
        same = next(
            row for row in missing["comparisons"] if row["target_id"] == "claim:same"
        )
        self.assertEqual(same["operator_status"], "BLOCKED_TARGET_SOURCE_UNAVAILABLE")
        self.assertFalse(same["comparison_usable"])
        self.assertIsNone(same["source"])
        match, promotion, targets = persisted_comparison()
        match.targets = (
            item(
                "ATOMIC_CLAIM",
                "claim:same",
                "Dati ritrattati.",
                content_id="content:same",
                provenance_key="passage:same",
            ),
            *match.targets[1:],
        )
        stale = self.preview(match, promotion, targets)
        self.assertEqual(stale["currentness"], "STALE")
        self.assertTrue(
            all(not row["comparison_usable"] for row in stale["comparisons"])
        )

    def test_duplicate_extraction_requires_same_capture_and_source_version(self):
        match, promotion, targets = persisted_comparison(duplicate=True)
        wrong_capture = self.preview(match, promotion, targets)
        duplicate = next(
            row
            for row in wrong_capture["comparisons"]
            if row["target_id"] == "claim:same"
        )
        self.assertEqual(duplicate["relation"], "DUPLICATE_EXTRACTION")
        self.assertEqual(
            duplicate["operator_status"], "BLOCKED_DUPLICATE_CAPTURE_MISMATCH"
        )
        self.assertFalse(duplicate["comparison_usable"])
        targets.snapshots[("ATOMIC_CLAIM", "claim:same")].update(
            {
                "capture_id": "capture:1",
                "capture_sha256": "c" * 64,
            }
        )
        valid = self.preview(match, promotion, targets)
        duplicate = next(
            row for row in valid["comparisons"] if row["target_id"] == "claim:same"
        )
        self.assertEqual(duplicate["operator_status"], "OPERATOR_COMPARE_PENDING")
        self.assertEqual(duplicate["action"], "CHECK_SAME_SOURCE_EXTRACTION")
        self.assertFalse(duplicate["equivalence_approved"])

    def test_source_rights_drift_between_reads_refuses_complete_comparison(self):
        match, promotion, targets = persisted_comparison()

        class RevokedMidPreview(TargetSourceReader):
            def source_context(self, kind, identifier):
                row = super().source_context(kind, identifier)
                if (kind, identifier) == ("ATOMIC_CLAIM", "claim:same") and (
                    self.calls.count((kind, identifier)) == 2
                ):
                    row["rights_status"] = "REVOKED"
                return row

        volatile = RevokedMidPreview(match.targets, candidate=match.candidate)
        with self.assertRaisesRegex(ValueError, "DP418_COMPARISON_CHANGED_DURING_READ"):
            self.preview(match, promotion, volatile)

    def test_forged_persisted_algorithm_or_feature_is_not_reconstructed_as_current(
        self,
    ):
        for corruption, reason in (
            ({"method": "FORGED_APPROVAL"}, "MATCH_CLASS_INVALID"),
            ({"matching_version": "candidate-matching-old"}, "RESULT_VERSION_INVALID"),
            (
                {"supporting_features": [{"code": "FORGED_CONFIDENCE"}]},
                "FEATURE_CODE_INVALID",
            ),
        ):
            match, promotion, targets = persisted_comparison()
            match.rows = ({**match.rows[0], **corruption}, *match.rows[1:])
            with (
                self.subTest(corruption=corruption),
                self.assertRaisesRegex(ValueError, reason),
            ):
                self.preview(match, promotion, targets)


if __name__ == "__main__":
    unittest.main()
