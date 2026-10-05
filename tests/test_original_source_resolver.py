import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.original_source_resolver import (  # noqa: E402
    DerivationEdge,
    resolve_original_source,
    resolve_reviewed_original_source,
)


def edge(edge_id, derived, origin, *, relation="SYNDICATION", status="APPROVED", family="fam:1"):
    return DerivationEdge(
        edge_id=edge_id,
        family_id=family,
        derived_content_id=derived,
        origin_content_id=origin,
        relation_type=relation,
        status=status,
    )


class OriginalSourceResolverTests(unittest.TestCase):
    def test_resolves_multihop_approved_chain(self):
        result = resolve_original_source(
            "content:copy:2",
            [
                edge("e1", "content:copy:2", "content:copy:1"),
                edge("e2", "content:copy:1", "content:root", relation="REPUBLICATION"),
            ],
            expected_family_id="fam:1",
            family_root_content_id="content:root",
        )
        self.assertTrue(result.resolved)
        self.assertEqual(result.root_content_id, "content:root")
        self.assertEqual(
            result.path_content_ids,
            ("content:copy:2", "content:copy:1", "content:root"),
        )

    def test_candidate_edge_is_not_provenance_authority(self):
        result = resolve_original_source(
            "content:copy",
            [edge("e1", "content:copy", "content:root", status="CANDIDATE")],
            family_root_content_id="content:root",
        )
        self.assertFalse(result.resolved)
        self.assertIn("EXPECTED_ROOT_NOT_REACHED", result.blockers)

    def test_conflicting_approved_origins_fail_closed(self):
        result = resolve_original_source(
            "content:copy",
            [
                edge("e1", "content:copy", "content:root:a"),
                edge("e2", "content:copy", "content:root:b"),
            ],
        )
        self.assertFalse(result.resolved)
        self.assertEqual(result.blockers, ("CONFLICTING_APPROVED_ORIGINS",))

    def test_unknown_derivation_does_not_claim_original(self):
        result = resolve_original_source(
            "content:copy",
            [
                edge(
                    "e1",
                    "content:copy",
                    "content:maybe",
                    relation="UNKNOWN_DERIVATION",
                )
            ],
        )
        self.assertFalse(result.resolved)
        self.assertEqual(result.blockers, ("UNKNOWN_DERIVATION_RELATION",))

    def test_cycle_fails_closed(self):
        result = resolve_original_source(
            "content:a",
            [
                edge("e1", "content:a", "content:b"),
                edge("e2", "content:b", "content:a"),
            ],
        )
        self.assertFalse(result.resolved)
        self.assertIn("DERIVATION_CYCLE", result.blockers)

    def test_family_filter_prevents_cross_family_resolution(self):
        result = resolve_original_source(
            "content:copy",
            [
                edge(
                    "e1",
                    "content:copy",
                    "content:wrong-root",
                    family="fam:other",
                )
            ],
            expected_family_id="fam:1",
            family_root_content_id="content:root",
        )
        self.assertFalse(result.resolved)
        self.assertEqual(result.blockers, ("EXPECTED_ROOT_NOT_REACHED",))

    def test_reviewed_resolution_requires_approved_family(self):
        result = resolve_reviewed_original_source(
            "content:a",
            families=[],
            edges=[],
        )
        self.assertFalse(result.resolved)
        self.assertEqual(result.blockers, ("NO_APPROVED_DERIVATION_FAMILY",))

    def test_reviewed_family_root_is_self_original(self):
        result = resolve_reviewed_original_source(
            "content:root",
            families=[
                {
                    "id": "family:1",
                    "root_content_id": "content:root",
                    "status": "APPROVED",
                }
            ],
            edges=[],
        )
        self.assertTrue(result.resolved)
        self.assertEqual(result.status, "SELF_ORIGINAL")

    def test_reviewed_derived_content_resolves_but_is_not_root(self):
        result = resolve_reviewed_original_source(
            "content:copy",
            families=[
                {
                    "id": "family:1",
                    "root_content_id": "content:root",
                    "status": "APPROVED",
                }
            ],
            edges=[
                {
                    "id": "edge:1",
                    "family_id": "family:1",
                    "derived_content_id": "content:copy",
                    "origin_content_id": "content:root",
                    "relation_type": "REPUBLICATION",
                    "status": "APPROVED",
                }
            ],
        )
        self.assertTrue(result.resolved)
        self.assertEqual(result.root_content_id, "content:root")
        self.assertNotEqual(result.content_id, result.root_content_id)

    def test_conflicting_reviewed_family_roots_fail_closed(self):
        result = resolve_reviewed_original_source(
            "content:copy",
            families=[
                {"id": "f1", "root_content_id": "content:a", "status": "APPROVED"},
                {"id": "f2", "root_content_id": "content:b", "status": "APPROVED"},
            ],
            edges=[],
        )
        self.assertFalse(result.resolved)
        self.assertEqual(result.blockers, ("CONFLICTING_APPROVED_FAMILY_ROOTS",))


if __name__ == "__main__":
    unittest.main()
