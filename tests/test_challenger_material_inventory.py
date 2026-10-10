import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.challenger_material_inventory import (  # noqa: E402
    load_challenger_material_inventory,
)


def candidate(**changes):
    row = {
        "evidence_id": "ev:1", "retrieval_version": "retrieval:v1",
        "relation_candidate": "CONTRADICT", "status": "APPROVED",
        "content_sha256": "a" * 64, "rights_status": "CLEARED",
        "record_status": "ACTIVE", "independence_group": "origin:1",
        "review_events": [{"id": "review:1", "action": "APPROVED"}],
    }
    row.update(changes)
    return row


class FakeRuntime:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def run(self, sql, **variables):
        import json
        self.calls.append((sql, variables))
        return json.dumps(self.rows)


class ChallengerMaterialInventoryTests(unittest.TestCase):
    def test_canonical_inventory_uses_current_private_sql_and_never_authorizes(self):
        runtime = FakeRuntime([candidate()])
        inventory = load_challenger_material_inventory(runtime, claim_id="claim:1")
        self.assertEqual(inventory.candidates, 1)
        self.assertEqual(inventory.pending_or_unverified, 0)
        self.assertEqual(inventory.counterevidence_candidates, 1)
        self.assertFalse(inventory.publication_authority)
        self.assertIn("CHALLENGER_INDEPENDENT_REVIEW_AUTHORITY_UNAVAILABLE", inventory.blockers)
        self.assertEqual(runtime.calls[0][1], {"claim_id": "claim:1"})
        self.assertIn("review_event", runtime.calls[0][0])
        self.assertIn("link.claim_id = :'claim_id'", runtime.calls[0][0])

    def test_changes_to_candidates_and_reviews_invalidate_material(self):
        base = load_challenger_material_inventory(FakeRuntime([candidate()]), claim_id="c")
        changes = [
            [candidate(content_sha256="b" * 64)],
            [candidate(relation_candidate="CONTEXT")],
            [candidate(status="REJECTED")],
            [candidate(review_events=[{"id": "review:2", "action": "APPROVED"}])],
            [candidate(review_events=[{"id": "review:1", "action": "APPROVED"},
                                      {"id": "review:2", "action": "REJECTED"}])],
            [candidate(), candidate(evidence_id="ev:2", status="RETRIEVED")],
            [candidate(rights_status="UNKNOWN")],
            [candidate(independence_group="origin:other")],
            [candidate(record_status="SUPERSEDED")],
        ]
        for rows in changes:
            with self.subTest(rows=rows):
                changed = load_challenger_material_inventory(FakeRuntime(rows), claim_id="c")
                self.assertNotEqual(base.material_sha256, changed.material_sha256)

    def test_order_independence_and_unapproved_material_still_changes_hash(self):
        rows = [candidate(), candidate(evidence_id="ev:2", status="RETRIEVED")]
        a = load_challenger_material_inventory(FakeRuntime(rows), claim_id="c")
        b = load_challenger_material_inventory(FakeRuntime(rows[::-1]), claim_id="c")
        self.assertEqual(a.material_sha256, b.material_sha256)
        self.assertEqual(a.pending_or_unverified, 1)
        self.assertIn("CHALLENGER_MATERIAL_PENDING_OR_UNVERIFIED", a.blockers)

    def test_empty_is_not_evidence_of_completion(self):
        empty = load_challenger_material_inventory(FakeRuntime([]), claim_id="c")
        self.assertEqual(empty.candidates, 0)
        self.assertIn("CHALLENGER_MATERIAL_EMPTY", empty.blockers)
        self.assertFalse(empty.publication_authority)

    def test_historical_approval_followed_by_rejection_is_not_current(self):
        revoked = candidate(review_events=[
            {"id": "review:1", "action": "APPROVED"},
            {"id": "review:2", "action": "QUARANTINED"},
        ])
        inventory = load_challenger_material_inventory(FakeRuntime([revoked]), claim_id="c")
        self.assertEqual(inventory.pending_or_unverified, 1)

    def test_malformed_or_duplicate_rows_fail_closed(self):
        for rows in ([candidate(), candidate()], [{"evidence_id": "ev:1"}],
                     [candidate(review_events=[{"id": "x"}])]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                load_challenger_material_inventory(FakeRuntime(rows), claim_id="c")
        with self.assertRaises(ValueError):
            load_challenger_material_inventory(FakeRuntime([]), claim_id="")


if __name__ == "__main__":
    unittest.main()
