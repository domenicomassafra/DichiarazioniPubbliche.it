"""DP-431: corrected public search must not retain old attribution in hidden terms.

All records are synthetic. Test only the pure propagation checker, no providers,
filesystem publication, private operational data or MiniPC access.
"""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from test_correction_propagation import check, scenarios, search_index  # noqa: E402


class DP431SearchMetadataIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.scenario = deepcopy(scenarios()[0])
        self.index = search_index(self.scenario["new_projection"])
        self.finding = next(
            record for record in self.index["records"]
            if record["kind"] == "finding"
        )

    def test_corrected_attribution_fails_closed_even_when_current_title_and_fingerprint_match(self):
        old = "Persona Uno"
        self.assertTrue(check(self.scenario, search_index=self.index).consistent)

        malicious = {
            "subtitle": f"{old} · Intervista uno",
            "primary_terms": ["Versione errata attribuita a Persona Uno"],
            "secondary_terms": [old, "Intervista uno"],
            "person_id": "person:1",
            "topic_ids": ["topic:held"],
        }
        for field, stale in malicious.items():
            with self.subTest(field=field):
                index = deepcopy(self.index)
                finding = next(row for row in index["records"] if row["kind"] == "finding")
                finding[field] = stale
                receipt = check(self.scenario, search_index=index)
                self.assertFalse(receipt.consistent, f"old attribution survives in {field}")
                self.assertIn("SEARCH_INDEX_STALE_METADATA", receipt.blockers)
                self.assertIn("search:finding:finding:v2", receipt.stale_artifacts)

    def test_finding_missing_required_v1_metadata_must_hold(self):
        self.assertTrue(check(self.scenario, search_index=self.index).consistent)
        for field in (
            "subtitle", "primary_terms", "secondary_terms", "person_id",
            "topic_ids", "route", "assessment", "published_at",
            "has_corrections", "has_rights_of_reply", "wording_type",
            "source_wording_type", "direct_quote_eligible",
        ):
            with self.subTest(field=field):
                index = deepcopy(self.index)
                row = next(item for item in index["records"] if item["kind"] == "finding")
                del row[field]
                receipt = check(self.scenario, search_index=index)
                self.assertFalse(receipt.consistent, f"missing required {field} was accepted")
                self.assertIn("SEARCH_INDEX_STALE_METADATA", receipt.blockers)

    def test_stale_person_topic_content_metadata_and_missing_fields_must_hold(self):
        self.assertTrue(check(self.scenario, search_index=self.index).consistent)
        for kind in ("person", "topic", "content"):
            actual = next(item for item in self.index["records"] if item["kind"] == kind)
            for field, stale in (
                ("subtitle", "Old private label"),
                ("secondary_terms", ["OLD_WITHDRAWN_ATTRIBUTION"]),
                ("primary_terms", ["OLD_WITHDRAWN_QUOTE"]),
                ("route", "/private-stale-route/"),
            ):
                with self.subTest(kind=kind, field=field):
                    index = deepcopy(self.index)
                    row = next(item for item in index["records"] if item["kind"] == kind)
                    row[field] = stale
                    receipt = check(self.scenario, search_index=index)
                    self.assertFalse(receipt.consistent, f"{kind}.{field} stale but accepted")
                    self.assertIn("SEARCH_INDEX_STALE_METADATA", receipt.blockers)
                    self.assertIn(f"search:{kind}:{actual['id']}", receipt.stale_artifacts)
            for missing in ("subtitle", "primary_terms", "secondary_terms"):
                with self.subTest(kind=kind, missing=missing):
                    index = deepcopy(self.index)
                    row = next(item for item in index["records"] if item["kind"] == kind)
                    del row[missing]
                    receipt = check(self.scenario, search_index=index)
                    self.assertFalse(receipt.consistent)
                    self.assertIn("SEARCH_INDEX_STALE_METADATA", receipt.blockers)

    def test_extra_metadata_and_invalid_optional_kind_membership_hold(self):
        for kind in ("finding", "person", "topic", "content"):
            with self.subTest(kind=kind):
                index = deepcopy(self.index)
                row = next(item for item in index["records"] if item["kind"] == kind)
                row["private_memo"] = "PRIVATE_UNREVIEWED_TRANSCRIPT"
                receipt = check(self.scenario, search_index=index)
                self.assertFalse(receipt.consistent)
                self.assertIn("SEARCH_INDEX_STALE_METADATA", receipt.blockers)

    def test_full_v1_dates_roles_wording_and_history_flags_are_current_only(self):
        projection = self.scenario["new_projection"]
        dossier = projection["dossiers"][0]
        dossier["speaker"]["public_roles"] = [
            {"role": "Consigliere", "organization_name": "Comune Dimostrativo"}
        ]
        dossier["finding"]["published_at"] = "2026-10-12"
        dossier["finding"]["assessment"] = "FACTUALLY_FALSE"
        dossier["source"]["published_at"] = "2026-10-10"
        dossier["corrections"] = [{"id": "correction:approved"}]
        dossier["rights_of_reply"] = [{"id": "reply:approved"}]
        dossier["wording"] = {
            "source_occurrence": {"wording_type": "VERBATIM_ORIGINAL"}
        }
        projection["topics"][0]["scope_text"] = "Ambito pubblico verificato"
        index = search_index(projection)
        finding = next(row for row in index["records"] if row["kind"] == "finding")
        self.assertEqual(finding["published_at"], "2026-10-12")
        self.assertEqual(finding["source_wording_type"], "VERBATIM_ORIGINAL")
        self.assertTrue(finding["has_corrections"])
        self.assertTrue(finding["has_rights_of_reply"])
        self.assertIn("Comune Dimostrativo", finding["secondary_terms"])
        self.assertTrue(check(self.scenario, search_index=index).consistent)
        for field, stale in (
            ("published_at", "2026-10-10"),
            ("has_corrections", False),
            ("has_rights_of_reply", False),
            ("source_wording_type", None),
            ("assessment", "SUPPORTED"),
            ("secondary_terms", ["OLD_WITHDRAWN_OFFICE"]),
        ):
            with self.subTest(field=field):
                bad = deepcopy(index)
                row = next(item for item in bad["records"] if item["kind"] == "finding")
                row[field] = stale
                receipt = check(self.scenario, search_index=bad)
                self.assertFalse(receipt.consistent)
                self.assertIn("SEARCH_INDEX_STALE_METADATA", receipt.blockers)

    def test_legacy_projection_without_first_class_contents_has_exact_fallback_records(self):
        for key in ("old_projection", "new_projection"):
            self.scenario[key].pop("contents")
        index = search_index(self.scenario["new_projection"])
        content = next(row for row in index["records"] if row["kind"] == "content")
        self.assertEqual(content["subtitle"], "Fonte pubblica")
        self.assertEqual(content["secondary_terms"], [])
        self.assertTrue(check(self.scenario, search_index=index).consistent)
        content["secondary_terms"] = ["OLD_WITHDRAWN_SOURCE"]
        receipt = check(self.scenario, search_index=index)
        self.assertFalse(receipt.consistent)
        self.assertIn("SEARCH_INDEX_STALE_METADATA", receipt.blockers)

    def test_first_class_explicitly_empty_content_does_not_force_legacy_search_record(self):
        # A first-class empty public Content catalog is valid and the actual
        # TS builder never falls back to source.content_id in this case.
        # The correction/static graph still tracks source Content lineage;
        # search *record completeness* is a different contract.
        for key in ("old_projection", "new_projection"):
            self.scenario[key]["contents"] = []
        index = search_index(self.scenario["new_projection"])
        self.assertFalse([r for r in index["records"] if r["kind"] == "content"])
        receipt = check(self.scenario, search_index=index)
        self.assertTrue(receipt.consistent, receipt.blockers)
        bad = deepcopy(index)
        bad["records"].append({"kind": "content", "id": "content:stale", "title": "PRIVATE"})
        blocked = check(self.scenario, search_index=bad)
        self.assertFalse(blocked.consistent)
        self.assertIn("SEARCH_INDEX_ORPHAN_ENTRY", blocked.blockers)


if __name__ == "__main__":
    unittest.main()
