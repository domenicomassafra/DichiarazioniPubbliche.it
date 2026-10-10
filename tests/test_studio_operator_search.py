import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.corpus_search import CorpusSearchResult  # noqa: E402
from dichiarazioni_pubbliche.studio_operator_search import search_private_corpus  # noqa: E402


def item(**overrides):
    defaults = {
        "kind": "PASSAGE",
        "id": "passage:example-1",
        "label": "Sensitive private headline",
        "snippet": "Unpublished private transcript body",
        "content_id": "content:example-1",
        "passage_id": "passage:example-1",
        "source_id": "source:official",
        "person_id": "person:private",
        "topic_id": None,
        "event_id": None,
        "event_at": None,
        "status": "HELD",
        "claim_type": None,
        "check_worthy": None,
        "lexical_score": 0.9,
        "trigram_score": 0.2,
    }
    return CorpusSearchResult(**(defaults | overrides))


class FakeStore:
    def __init__(self, rows=None, error=None):
        self.rows = [item()] if rows is None else rows
        self.error = error
        self.requests = []

    def search(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.rows


class StudioOperatorSearchTests(unittest.TestCase):
    def test_full_dp116_filter_contract_reaches_lexical_store_without_raw_response(self):
        store = FakeStore()
        receipt = search_private_corpus(
            store, query="ricerca mirata", kinds=("PASSAGE",),
            collection_id="research:garlasco", source_id="source:official",
            person_id="person:one", topic_id="topic:one", event_id="event:one",
            status="APPROVED", claim_type="FACTUAL", check_worthy=False,
            from_at="2026-01-01T00:00:00Z", to_at="2026-10-01T23:59:59Z",
            limit=5,
        )
        request = store.requests[0]
        self.assertEqual(request.collection_id, "research:garlasco")
        self.assertEqual(request.source_id, "source:official")
        self.assertEqual(request.person_id, "person:one")
        self.assertEqual(request.topic_id, "topic:one")
        self.assertEqual(request.event_id, "event:one")
        self.assertEqual(request.kinds, ("PASSAGE",))
        self.assertEqual(request.status, "APPROVED")
        self.assertEqual(request.claim_type, "FACTUAL")
        self.assertIs(request.check_worthy, False)
        self.assertEqual(request.from_at, "2026-01-01T00:00:00Z")
        self.assertEqual(request.to_at, "2026-10-01T23:59:59Z")
        self.assertEqual(request.limit, 5)
        self.assertNotIn("ricerca mirata", json.dumps(receipt.to_dict()))
        self.assertNotIn("Unpublished private transcript body", json.dumps(receipt.to_dict()))

    def test_invalid_optional_filter_dates_and_booleans_fail_closed(self):
        for extras in (
            {"check_worthy": "false"},
            {"check_worthy": 0},
            {"person_id": "bad\nref"},
            {"status": "invalid\nstatus"},
            {"from_at": "2026-01-01"},
            {"to_at": "2026-01-01"},
            {"from_at": "x" * 41},
            {"to_at": 42},
        ):
            with self.subTest(extras=extras), self.assertRaises(ValueError):
                search_private_corpus(FakeStore(), query="valid", **extras)

    def test_result_is_metadata_only_and_uses_private_lexical_backend(self):
        store = FakeStore()
        receipt = search_private_corpus(
            store, query="documenti verbale", kinds=("PASSAGE",), source_id="source:official"
        )
        self.assertEqual(store.requests[0].query, "documenti verbale")
        self.assertEqual(store.requests[0].kinds, ("PASSAGE",))
        self.assertEqual(store.requests[0].source_id, "source:official")
        self.assertEqual(receipt.result_count, 1)
        encoded = json.dumps(receipt.to_dict())
        self.assertIn("passage:example-1", encoded)
        self.assertTrue(receipt.private_only)
        self.assertFalse(receipt.publication_authority)
        for secret in (
            "Sensitive private headline", "Unpublished private transcript body",
            "person:private", "documenti verbale", "0.9",
        ):
            self.assertNotIn(secret, encoded)

    def test_empty_search_is_not_a_fake_ready_result(self):
        receipt = search_private_corpus(FakeStore(rows=[]), query="missing")
        self.assertEqual(receipt.result_count, 0)
        self.assertEqual(receipt.results, ())

    def test_provider_is_not_used_and_backend_error_does_not_leak(self):
        store = FakeStore(error=RuntimeError("password=do-not-copy SQL private-content"))
        with self.assertRaisesRegex(RuntimeError, "^STUDIO_PRIVATE_SEARCH_UNAVAILABLE$") as ctx:
            search_private_corpus(store, query="private search")
        self.assertIsNone(ctx.exception.__cause__)
        self.assertNotIn("do-not-copy", str(ctx.exception))

    def test_invalid_filter_length_kind_and_tampered_result_fail_closed(self):
        for opts in (
            {"query": ""},
            {"query": "x" * 129},
            {"query": "query", "limit": 21},
            {"query": "query", "limit": 0},
            {"query": "query", "limit": True},
            {"query": "query", "kinds": ("UNKNOWN",)},
            {"query": "query", "source_id": "unsafe\nsecret"},
        ):
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                search_private_corpus(FakeStore(), **opts)
        with self.assertRaisesRegex(ValueError, "STUDIO_SEARCH_RESULT_REFERENCE_INVALID"):
            search_private_corpus(FakeStore(rows=[item(id="leak\nsecret")]), query="safe")
        with self.assertRaisesRegex(ValueError, "STUDIO_SEARCH_BACKEND_LIMIT_BROKEN"):
            search_private_corpus(FakeStore(rows=[item(), item()]), query="safe", limit=1)

    def test_no_public_server_or_provider_dependency(self):
        code = (ROOT / "poc" / "dichiarazioni_pubbliche" / "studio_operator_search.py").read_text()
        for forbidden in ("http.server", "socketserver", "fastapi", "flask", "fetch_bytes", "requests.get"):
            self.assertNotIn(forbidden, code)
        cmd = [
            sys.executable, "-m", "dichiarazioni_pubbliche.studio_operator_search",
            "--query", "",
        ]
        process = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT / "poc")})
        self.assertEqual(process.returncode, 2)
        self.assertIn("STUDIO_QUERY_LENGTH_INVALID", process.stdout)


if __name__ == "__main__":
    unittest.main()
