import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.garlasco_pilot_inventory import (  # noqa: E402
    GARLASCO_INVENTORY_VERSION,
    build_live_inventory,
    write_private_draft,
    verify_baseline_retrieval,
)
from dichiarazioni_pubbliche.garlasco_tracer import evaluate_preflight  # noqa: E402


def baseline():
    summary = {
        "claims": 30, "unique_claim_ids": 30, "content_ids": 18,
        "linked_claims": 30, "approved_text_attributions": 28, "captures": 0,
        "passages": 0, "statement_candidates": 0, "claim_candidates": 0,
        "collection_rows": 0, "collection_members": 0, "discovery_hits": 0,
        "collection_coverage_needs": 0, "public_findings": 2,
    }
    records = [{
        "id": f"content:garlasco:unit:{number:02d}",
        "source_id": "source:test-news",
        "canonical_url": f"https://news.example.test/case/{number}",
        "rights_status": "UNKNOWN",
        "source_present": True,
        "active_source_profile_count": 0,
        "title": "SECRET UNPUBLISHED SOURCE",
        "body": "PRIVATE RAW TEXT",
    } for number in range(18)]
    claims = [f"claim:garlasco:unit:{number:02d}" for number in range(30)]
    return summary, records, claims


class FakeReadOnly:
    def __init__(self, *, summary=None, records=None, claims=None, error=None):
        default = baseline()
        self.summary = default[0] if summary is None else summary
        self.records = default[1] if records is None else records
        self.claims = default[2] if claims is None else claims
        self.calls = []
        self.error = error

    def run(self, sql, **variables):
        self.calls.append(sql)
        if self.error:
            raise self.error
        if "'normalized_claim'" in sql:
            return "\n".join(json.dumps({
                "id": cid, "content_id": f"content:garlasco:unit:{idx % 18:02d}",
                "normalized_claim": f"Claim numero {idx:02d} su fonte {idx % 18:02d}",
            }) for idx, cid in enumerate(self.claims))
        if "LEFT JOIN source" in sql:
            return "\n".join(json.dumps(row) for row in self.records)
        if "json_build_object" in sql:
            return json.dumps(self.summary)
        return "\n".join(self.claims)

class SearchResult:
    def __init__(self, claim_id, content_id):
        self.id = claim_id
        self.kind = "ATOMIC_CLAIM"
        self.content_id = content_id

class FakeSearch:
    def __init__(self, *, missing_at=None, mismatched_at=None, error=False):
        self.missing_at = missing_at
        self.mismatched_at = mismatched_at
        self.error = error
        self.count = 0

    def search(self, request):
        if self.error:
            raise OSError("sensitive database query password")
        index = int(request.query.split()[2])
        self.count += 1
        if self.missing_at == index:
            return []
        content_id = f"content:garlasco:unit:{index % 18:02d}"
        if self.mismatched_at == index:
            content_id = "content:garlasco:wrong"
        return [SearchResult(f"claim:garlasco:unit:{index:02d}", content_id)]


class GarlascoPilotInventoryTests(unittest.TestCase):
    def test_all_thirty_historic_claims_retrievable_by_exact_content_binding(self):
        searcher = FakeSearch()
        result = verify_baseline_retrieval(FakeReadOnly(), searcher)
        self.assertEqual(result["baseline_claims"], 30)
        self.assertEqual(result["searchable_and_linkable"], 30)
        self.assertEqual(result["missing"], 0)
        self.assertTrue(result["all_30_retrievable"])
        self.assertFalse(result["publication_authority"])
        self.assertEqual(searcher.count, 30)
        self.assertNotIn("normalized_claim", json.dumps(result))

        bad = verify_baseline_retrieval(FakeReadOnly(), FakeSearch(missing_at=8))
        self.assertEqual(bad["searchable_and_linkable"], 29)
        self.assertFalse(bad["all_30_retrievable"])
        wrong_content = verify_baseline_retrieval(FakeReadOnly(), FakeSearch(mismatched_at=4))
        self.assertEqual(wrong_content["missing"], 1)

        with self.assertRaisesRegex(RuntimeError, "SEARCH_UNAVAILABLE") as ctx:
            verify_baseline_retrieval(FakeReadOnly(), FakeSearch(error=True))
        self.assertNotIn("sensitive", str(ctx.exception))
        short = baseline()[2][:27]
        with self.assertRaisesRegex(ValueError, "NOT_30"):
            verify_baseline_retrieval(FakeReadOnly(claims=short), FakeSearch())

    def test_truthful_incomplete_real_seed_refuses_false_green(self):
        reader = FakeReadOnly()
        result = build_live_inventory(reader)
        receipt = result.receipt()
        self.assertEqual(receipt["version"], GARLASCO_INVENTORY_VERSION)
        self.assertFalse(receipt["complete_pilot"])
        self.assertFalse(receipt["publication_authority"])
        self.assertEqual(receipt["seed_items"], 18)
        self.assertEqual(receipt["missing_items"], 82)
        self.assertEqual(receipt["baseline_claims"], 30)
        self.assertEqual(receipt["counts"]["approved_text_attributions"], 28)
        self.assertIn("PILOT_ITEM_COUNT_NOT_100", receipt["blockers"])
        self.assertIn("DISCOVERY_PROVENANCE_MISSING", receipt["blockers"])
        self.assertIn("CONTENT_RIGHTS_UNRESOLVED", receipt["blockers"])
        self.assertIn("PERSISTED_COLLECTION_INCOMPLETE", receipt["blockers"])
        self.assertIn("SOURCE_INTELLIGENCE_PROFILE_MISSING", receipt["blockers"])
        self.assertIn("CAPTURE_PASSAGE_COVERAGE_MISSING", receipt["blockers"])
        self.assertEqual(len(reader.calls), 3)
        self.assertTrue(all("INSERT INTO" not in sql and "DELETE FROM" not in sql for sql in reader.calls))
        self.assertNotIn("PRIVATE RAW TEXT", json.dumps(receipt))
        self.assertNotIn("canonical_url", json.dumps(receipt))
        self.assertNotIn("news.example", json.dumps(receipt))
        structural = evaluate_preflight(result.seed_manifest, observed_baseline_claim_ids=result.seed_manifest.baseline_claim_ids)
        self.assertFalse(structural.ready)

    def test_private_draft_is_exact_real_seed_not_a_fake_discovery_manifest(self):
        result = build_live_inventory(FakeReadOnly())
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp) / "private"
            parent.mkdir(mode=0o700)
            os.chmod(parent, 0o700)
            path = parent / "draft.json"
            write_private_draft(path, result)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            raw = json.loads(path.read_text())
            self.assertEqual(raw["status"], "INCOMPLETE_UNREVIEWED_SEED_NOT_FOR_INGESTION")
            self.assertEqual(len(raw["items"]), 18)
            self.assertEqual(len(raw["baseline_claim_ids"]), 30)
            self.assertTrue(all(item["discovery_ref"] == "" for item in raw["items"]))
            self.assertTrue(all(item["source_family"] == "UNCLASSIFIED" for item in raw["items"]))
            self.assertTrue(all(item["rights_status"] == "UNKNOWN" for item in raw["items"]))
            self.assertNotIn("SECRET UNPUBLISHED SOURCE", json.dumps(raw))
            with self.assertRaises(FileExistsError):
                write_private_draft(path, result)
            os.chmod(parent, 0o755)
            with self.assertRaisesRegex(ValueError, "PERMISSIONS"):
                write_private_draft(parent / "unsafe.json", result)

    def test_private_draft_refuses_symlink_parent_without_writing_destination(self):
        inventory = build_live_inventory(FakeReadOnly())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "trusted"
            private.mkdir(mode=0o700)
            alias = root / "alias"
            alias.symlink_to(private, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "DESTINATION_UNSAFE"):
                write_private_draft(alias / "draft.json", inventory)
            self.assertFalse((private / "draft.json").exists())

    def test_parent_path_swap_cannot_redirect_private_draft_to_attacker_directory(self):
        inventory = build_live_inventory(FakeReadOnly())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "trusted"
            private.mkdir(mode=0o700)
            moved = root / "moved-trusted"
            other = root / "untrusted"
            other.mkdir(mode=0o700)
            real_open = os.open
            swapped = False

            def simulated_race(filename, flags, mode=0o777, *, dir_fd=None):
                nonlocal swapped
                if dir_fd is not None and not swapped:
                    swapped = True
                    private.rename(moved)
                    private.symlink_to(other, target_is_directory=True)
                if dir_fd is not None:
                    return real_open(filename, flags, mode, dir_fd=dir_fd)
                return real_open(filename, flags, mode)

            with patch("dichiarazioni_pubbliche.garlasco_pilot_inventory.os.open", side_effect=simulated_race):
                write_private_draft(private / "draft.json", inventory)
            self.assertTrue(swapped)
            self.assertFalse((other / "draft.json").exists())
            self.assertTrue((moved / "draft.json").is_file())
            self.assertEqual(stat.S_IMODE((moved / "draft.json").stat().st_mode), 0o600)

    def test_bad_db_json_missing_fk_duplicate_out_of_scope_and_unsafe_urls_fail_closed(self):
        for version in (
            FakeReadOnly(error=OSError("postgres password=SECRET")),
            FakeReadOnly(summary=baseline()[0] | {"claims": 31}),
            FakeReadOnly(summary=baseline()[0] | {"unique_claim_ids": 29}),
            FakeReadOnly(records=[baseline()[1][0]] * 18),
            FakeReadOnly(records=[baseline()[1][0] | {"id": "content:other"}] + baseline()[1][1:]),
            FakeReadOnly(records=[baseline()[1][0] | {"canonical_url": "http://127.0.0.1/private"}] + baseline()[1][1:]),
            FakeReadOnly(records=[baseline()[1][0] | {"rights_status": "APPROVED_BY_MODEL"}] + baseline()[1][1:]),
        ):
            with self.subTest(version=version), self.assertRaises((ValueError, RuntimeError)) as ctx:
                build_live_inventory(version)
            self.assertNotIn("SECRET", str(ctx.exception))

    def test_approved_text_quote_provenance_does_not_clear_content_rights(self):
        result = build_live_inventory(FakeReadOnly())
        self.assertEqual(result.receipt()["counts"]["approved_text_attributions"], 28)
        self.assertIn("CONTENT_RIGHTS_UNRESOLVED", result.blockers)
        self.assertTrue(all(item.rights_status == "UNKNOWN" for item in result.seed_manifest.items))


if __name__ == "__main__":
    unittest.main()
