"""DP-418: real match snapshot, private pending-review queue, and no approvals."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.candidate_matching import (  # noqa: E402
    MATCHING_VERSION, deterministic_match_run_id,
    deterministic_match_result_id, matching_input_fingerprint, rank_candidate_matches,
)
from dichiarazioni_pubbliche.studio_candidate_review import (  # noqa: E402
    LocalCandidateReviewHandoffQueue, inspect_candidate_review_readiness,
    submit_candidate_review_handoff, inspect_persisted_review_handoff,
)
from dichiarazioni_pubbliche.reviewer_identity_authority import (  # noqa: E402
    LocalFileReviewerIdentityAuthority, provision_reviewer_credential,
)
from dichiarazioni_pubbliche.studio_candidate_review_ui import (  # noqa: E402
    render_candidate_review_workspace,
)
from tests.test_candidate_matching import item  # noqa: E402
from tests.test_claim_promotion import written_context  # noqa: E402


class MatchStore:
    def __init__(self) -> None:
        self.candidate = item(
            "CLAIM_CANDIDATE", "candidate:1", "Il primo evento fu registrato.",
            content_id="content:1", provenance_key="passage:1",
        )
        self.targets = (
            item("ATOMIC_CLAIM", "claim:1", "Il primo evento fu registrato.",
                 content_id="content:2", provenance_key="passage:2"),
        )
        self.fingerprint = matching_input_fingerprint(self.candidate, self.targets)
        self.run_id = deterministic_match_run_id("candidate:1", self.fingerprint)
        results = rank_candidate_matches(self.candidate, self.targets)
        self.run = {
            "id": self.run_id, "claim_candidate_id": "candidate:1",
            "matching_version": MATCHING_VERSION,
            "input_fingerprint": self.fingerprint,
            "status": "COMPLETED", "result_count": len(results),
        }
        self.rows = tuple({
            "id": deterministic_match_result_id(
                self.run_id, result.target.proposition.member_type,
                result.target.proposition.member_id,
            ),
            "rank": result.rank,
            "target_type": result.target.proposition.member_type,
            "target_id": result.target.proposition.member_id,
            "match_class": result.match.match_class,
            "method": result.match.method,
            "matching_version": MATCHING_VERSION,
            "status": "CANDIDATE",
            "lexical_score": result.match.lexical_score,
            "disposition": result.disposition,
            "proposition_cluster_id": result.cluster_id,
            "supporting_features": list(result.supporting_features),
            "contradicting_features": list(result.contradicting_features),
            "private_raw_source": "SECRET SHOULD NEVER BE IN INSPECTOR",
        } for result in results)
        self.loads = 0

    def get_run(self, run_id):
        return self.run

    def load_results(self, run_id):
        return self.rows

    def load_candidate(self, candidate_id):
        self.loads += 1
        return self.candidate

    def load_targets(self, candidate_id, *, limit=200):
        return self.targets


class PromotionContext:
    def __init__(self):
        self.data = written_context()
        self.calls = 0

    def context(self, candidate_id):
        self.calls += 1
        return self.data


class CandidateReviewHandoffTests(unittest.TestCase):
    def test_persisted_handoff_reloads_disk_and_redacts_reviewer_identity(self):
        receipt = self.submit()
        view = inspect_persisted_review_handoff(
            self.queue, handoff_id=receipt["handoff_id"],
            run_id=self.match.run_id, claim_candidate_id="candidate:1",
        )
        self.assertTrue(view["persisted"])
        self.assertEqual(view["status"], "QUEUED_FOR_HUMAN_REVIEW")
        self.assertFalse(view["review_decision_recorded"])
        self.assertFalse(view["reviewer_identity_verified"])
        self.assertEqual(view["currentness"], "NOT_REVALIDATED")
        for secret in ("reviewer-one", "operator:reviewer-one",
                       "actor_ref", "credential_id", "credential_fingerprint"):
            self.assertNotIn(secret, json.dumps(view))
        for changed in ({"run_id": "run:other"}, {"claim_candidate_id": "candidate:other"}):
            with self.assertRaisesRegex(ValueError, "SCOPE_INVALID"):
                inspect_persisted_review_handoff(
                    self.queue, handoff_id=receipt["handoff_id"],
                    **({"run_id": self.match.run_id,
                        "claim_candidate_id": "candidate:1"} | changed),
                )
        path = self.queue_root / (receipt["handoff_id"] + ".json")
        saved = json.loads(path.read_text())
        saved["reason_code"] = "TAMPERED"
        path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, "TAMPERED"):
            inspect_persisted_review_handoff(
                self.queue, handoff_id=receipt["handoff_id"],
                run_id=self.match.run_id, claim_candidate_id="candidate:1",
            )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        root.chmod(0o700)
        self.queue_root = root / "queue"
        self.queue_root.mkdir(mode=0o700)
        self.authority_root = root / "identity"
        provision_reviewer_credential(
            self.authority_root, credential_id="reviewer-one",
            actor_ref="operator:reviewer-one", key_version="v1",
            secret_hex="1" * 64,
        )
        self.queue = LocalCandidateReviewHandoffQueue(self.queue_root)
        self.authority = LocalFileReviewerIdentityAuthority(self.authority_root)
        self.match = MatchStore()
        self.promotion = PromotionContext()

    def packet(self):
        return inspect_candidate_review_readiness(
            self.match, self.promotion,
            run_id=self.match.run_id, claim_candidate_id="candidate:1",
        )

    def submit(self, **overrides):
        kwargs = {
            "run_id": self.match.run_id, "claim_candidate_id": "candidate:1",
            "result_id": self.match.rows[0]["id"],
            "action": "REVIEW_PROMOTION", "credential_id": "reviewer-one",
            "credential_secret_hex": "1" * 64,
            "reason_code": "NEEDS_HUMAN_REVIEW",
            "expected_input_fingerprint": self.match.fingerprint,
        } | overrides
        return submit_candidate_review_handoff(
            self.match, self.promotion, self.queue, self.authority, **kwargs,
        )

    def test_currentness_and_blockers_are_based_on_real_match_inputs(self):
        packet = self.packet()
        self.assertEqual(packet["currentness"], "CURRENT")
        self.assertEqual(packet["currentness_reason"], "EXACT_INPUT_AND_RESULT_REPLAY")
        self.assertTrue(packet["review_queue_eligible"])
        self.assertFalse(packet["review_authority"])
        self.assertFalse(packet["promotion_authority"])
        self.assertFalse(packet["publication_authority"])
        self.assertIn("DP117_TRANSACTIONAL_PROMOTION_REVALIDATION_REQUIRED", packet["promotion_blockers"])
        self.assertEqual(packet["source_references"][0]["passage_id"], "passage:1")
        self.assertEqual(packet["source_references"][0]["capture_sha256"], "c" * 64)
        encoded = json.dumps(packet)
        for forbidden in (
            "SECRET SHOULD NEVER BE", "Il primo evento fu", "https://example.test",
            "normalized_claim", "private_text", "lexical_score",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_same_proposition_requires_human_review_and_cannot_queue_direct_link(self):
        baseline = self.packet()
        self.promotion.data["same_proposition_target_ids"] = ["claim:1"]
        preview = self.packet()
        self.assertEqual(preview["currentness"], "CURRENT")
        self.assertIn("PROMOTION_SAME_PROPOSITION_REVIEW_REQUIRED", preview["promotion_blockers"])
        self.assertNotEqual(baseline["review_context_sha256"], preview["review_context_sha256"])
        with self.assertRaisesRegex(ValueError, "LINK_NOT_SUGGESTED"):
            self.submit(action="REVIEW_LINK")
        self.assertEqual(list(self.queue_root.iterdir()), [])
        receipt = self.submit(action="REVIEW_PROMOTION")
        self.assertEqual(receipt["status"], "QUEUED_FOR_HUMAN_REVIEW")
        self.assertFalse(receipt["promotion_authority"])

    def test_exact_input_or_feature_change_becomes_stale(self):
        self.match.targets = (
            item("ATOMIC_CLAIM", "claim:1", "Un testo nuovo e diverso.",
                 content_id="content:2", provenance_key="passage:2"),
        )
        stale = self.packet()
        self.assertEqual(stale["currentness"], "STALE")
        self.assertFalse(stale["review_queue_eligible"])
        self.assertIn("MATCH_RUN_STALE_OR_CHANGED", stale["promotion_blockers"])
        with self.assertRaisesRegex(ValueError, "STALE_OR_BLOCKED"):
            self.submit()

    def test_unauthorized_and_revoked_handoff_never_writes(self):
        for overrides in (
            {"credential_id": "nonexistent"},
            {"credential_secret_hex": "2" * 64},
            {"reason_code": "UNKNOWN\nPRIVATE"},
            {"expected_input_fingerprint": "a" * 64},
            {"action": "APPROVED"},
            {"action": "REVIEW_LINK", "result_id": "not-existing"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.submit(**overrides)
        self.assertEqual(list(self.queue_root.iterdir()), [])
        self.authority.revoke("reviewer-one")
        with self.assertRaisesRegex(ValueError, "REVOKED"):
            self.submit()
        self.assertEqual(list(self.queue_root.iterdir()), [])

    def test_handoff_is_idempotent_durable_and_never_approves(self):
        first = self.submit()
        self.assertEqual(first["status"], "QUEUED_FOR_HUMAN_REVIEW")
        self.assertEqual(first["currentness"], "CURRENT_AT_ENQUEUE")
        self.assertFalse(first["review_authority"])
        self.assertFalse(first["publication_authority"])
        self.assertFalse(first["promotion_authority"])
        self.assertEqual(first, self.submit())
        self.assertGreaterEqual(self.match.loads, 4, "each call rechecks source before enqueue")
        self.assertEqual(len(list(self.queue_root.iterdir())), 1)
        saved = self.queue.read(first["handoff_id"])
        self.assertEqual(saved, first)
        self.assertEqual(os.stat(self.queue_root / (first["handoff_id"] + ".json")).st_mode & 0o777, 0o600)
        payload = json.dumps(first)
        self.assertNotIn("SECRET", payload)
        self.assertNotIn("normalized_claim", payload)
        self.assertNotIn("private_text", payload)
        self.assertNotIn("APPROVED", payload)
        self.assertFalse(hasattr(self.match, "promote_claim_candidate"))

    def test_private_keyboard_native_inspector_renders_persisted_receipt_only(self):
        packet = self.packet()
        handoff = self.queue.read(self.submit()["handoff_id"])
        html = render_candidate_review_workspace(packet, persisted_handoff=handoff).decode()
        self.assertIn("<details><summary>", html)
        self.assertIn("grid-template-columns:repeat(auto-fit", html)
        self.assertIn("<meta name='viewport'", html)
        self.assertIn("candidate-review:", html)
        self.assertIn("QUEUED_FOR_HUMAN_REVIEW", html)
        self.assertIn("SAME_PROPOSITION", html)
        self.assertIn("Stessa proposizione suggerita, senza prova di duplicazione", html)
        self.assertIn("Attualità: CURRENT", html)
        for raw in ("SECRET SHOULD NEVER", "Il primo evento", "private_text", "lexical_score"):
            self.assertNotIn(raw, html)
        with self.assertRaisesRegex(ValueError, "HANDOFF_INVALID"):
            render_candidate_review_workspace(
                packet,
                persisted_handoff=handoff | {"publication_authority": True},
            )

    def test_receipt_tamper_and_private_root_permissions_fail_closed(self):
        saved = self.submit()
        path = self.queue_root / (saved["handoff_id"] + ".json")
        row = json.loads(path.read_text())
        row["status"] = "APPROVED"
        path.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "TAMPERED"):
            self.queue.read(saved["handoff_id"])
        self.queue_root.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "ROOT_UNSAFE"):
            LocalCandidateReviewHandoffQueue(self.queue_root)

    def test_mismatch_during_revalidation_refuses_persistence(self):
        original = self.match.load_candidate
        def changed(candidate_id):
            value = original(candidate_id)
            if self.match.loads >= 2:
                self.match.targets = (
                    item("ATOMIC_CLAIM", "claim:1", "Nuovi dati mutati."),
                )
            return value
        self.match.load_candidate = changed
        with self.assertRaisesRegex(ValueError, "CHANGED_DURING_ENQUEUE"):
            self.submit()
        self.assertEqual(list(self.queue_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
