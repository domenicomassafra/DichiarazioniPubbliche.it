"""Offline contract tests for the optional, private Wikidata proposal adapter."""

import hashlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.knowledge_repository import propose_alias_matches
from dichiarazioni_pubbliche.private_capture_rights import SourceUseDecision
from dichiarazioni_pubbliche.wikidata_proposal_adapter import (
    EgressApproval,
    WikibaseIntegratorReadOnly,
    WikidataLookupRequest,
    WikidataProposalAdapter,
)


NOW = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
SHA = hashlib.sha256(b"local reviewed source").hexdigest()


def statement(qid, *, start="+2015-01-01T00:00:00Z", end="+2028-01-01T00:00:00Z"):
    return {"mainsnak": {"datavalue": {"value": {"id": qid}}}, "qualifiers": {
        "P580": [{"datavalue": {"value": {"time": start, "precision": 11}}}],
        "P582": [{"datavalue": {"value": {"time": end, "precision": 11}}}],
    }}


def item(qid="Q101", *, label="Mario Rossi", revision=2030, instance="Q5", role="Q301"):
    return {
        "id": qid, "lastrevid": revision,
        "labels": {"it": {"language": "it", "value": label}},
        "aliases": {"it": [{"language": "it", "value": "M. Rossi"}]},
        "claims": {
            "P31": [{"mainsnak": {"datavalue": {"value": {"id": instance}}}}],
            "P39": [statement(role)],
        },
    }


class FakeBackend:
    def __init__(self, search=None, items=None, error=None):
        self.search_results = list(search or ["Q101"])
        self.items = items or {"Q101": item()}
        self.error = error
        self.search_calls = []
        self.fetch_calls = []

    def search(self, alias, *, language, limit, timeout):
        self.search_calls.append((alias, language, limit, timeout))
        if self.error:
            raise self.error
        return self.search_results

    def get_item(self, qid, *, timeout):
        self.fetch_calls.append((qid, timeout))
        if self.error:
            raise self.error
        return self.items[qid]


def request(**overrides):
    values = dict(local_entity_id="person:mario", entity_type="PERSON",
                  aliases=("Mario Rossi", "M. Rossi"), source_sha256=SHA,
                  reference_date="2020-06-01", role_qid="Q301")
    values.update(overrides)
    return WikidataLookupRequest(**values)


def source_use(status="PERMITTED"):
    return SourceUseDecision("DISCOVER_METADATA", status, "SOURCE_USE_CLEARED",
                             "DISCOVER_METADATA", "rights:r1", "a" * 64)


def approval(**overrides):
    values = dict(host="www.wikidata.org", purpose="PRIVATE_ENTITY_PROPOSAL",
                  reviewed_by="reviewer:test", expires_at=NOW + timedelta(hours=1),
                  source_sha256=SHA)
    values.update(overrides)
    return EgressApproval(**values)


class WikidataAdapterTests(unittest.TestCase):
    def adapter(self, backend, **overrides):
        values = dict(backend=backend, enabled=True, clock=lambda: NOW,
                      monotonic=lambda: 100.0, min_interval_seconds=0)
        values.update(overrides)
        return WikidataProposalAdapter(**values)

    def test_valid_person_is_local_review_proposal_with_revision_receipt(self):
        backend = FakeBackend()
        result = self.adapter(backend).lookup(request(), source_use=source_use(), egress=approval())
        self.assertEqual(result.status, "PROPOSED")
        self.assertEqual(result.reason, "WIKIDATA_REVIEW_REQUIRED")
        self.assertEqual(len(result.proposals), 1)
        proposal = result.proposals[0]
        self.assertEqual((proposal.local_entity_id, proposal.entity_type, proposal.qid),
                         ("person:mario", "PERSON", "Q101"))
        self.assertEqual(proposal.receipt.url, "https://www.wikidata.org/wiki/Q101")
        self.assertEqual(proposal.receipt.revision, 2030)
        self.assertEqual(proposal.receipt.observed_at, NOW.isoformat())
        self.assertEqual(proposal.receipt.source_sha256, SHA)
        self.assertEqual(proposal.receipt.rights_decision_fingerprint, "a" * 64)
        self.assertEqual(proposal.to_resolution_candidate(content_id="content:1").status, "CANDIDATE")
        self.assertEqual(proposal.to_resolution_candidate(content_id="content:1").target_id, "person:mario")
        self.assertEqual(backend.search_calls[0][:3], ("Mario Rossi", "it", 5))

    def test_homonyms_hold_even_when_both_have_valid_role(self):
        backend = FakeBackend(search=["Q101", "Q202"], items={"Q101": item(), "Q202": item("Q202")})
        result = self.adapter(backend).lookup(request(), source_use=source_use(), egress=approval())
        self.assertEqual((result.status, result.reason, result.proposals), ("HOLD", "HOMONYMS", ()))

    def test_unresolved_homonym_is_not_silently_discarded(self):
        backend = FakeBackend(search=["Q101", "Q202"], items={"Q101": item(), "Q202": item("Q202", revision=None)})
        result = self.adapter(backend).lookup(request(), source_use=source_use(), egress=approval())
        self.assertEqual(result.status, "HOLD")
        self.assertEqual(result.proposals, ())

    def test_type_role_and_epoch_filter(self):
        bad = [item(instance="Q43229"), item(role="Q999"),
               {**item(), "claims": {"P31": item()["claims"]["P31"],
                                    "P39": [statement("Q301", start="+2022-01-01T00:00:00Z")]}}]
        for row in bad:
            with self.subTest(row=row):
                result = self.adapter(FakeBackend(items={"Q101": row})).lookup(
                    request(), source_use=source_use(), egress=approval())
                self.assertEqual((result.status, result.proposals), ("HOLD", ()))

    def test_organization_and_topic_require_explicit_type_and_alias(self):
        org = item(instance="Q43229")
        org["claims"].pop("P39")
        org["claims"]["P571"] = [{"mainsnak": {"datavalue": {
            "value": {"time": "+2010-01-01T00:00:00Z", "precision": 11}}}}]
        res = self.adapter(FakeBackend(items={"Q101": org})).lookup(
            request(entity_type="ORGANIZATION", local_entity_id="organization:mario",
                    role_qid=None), source_use=source_use(), egress=approval())
        self.assertEqual(res.status, "PROPOSED")
        self.assertEqual(self.adapter(FakeBackend(items={"Q101": org})).lookup(
            request(entity_type="ORGANIZATION", local_entity_id="organization:mario",
                    role_qid=None, reference_date="2000-01-01"),
            source_use=source_use(), egress=approval()).status, "HOLD")
        topic = item(instance="Q11862829")
        topic["claims"].pop("P39")
        self.assertEqual(self.adapter(FakeBackend(items={"Q101": topic})).lookup(
            request(entity_type="TOPIC", local_entity_id="topic:mario", role_qid=None,
                    type_qids=("Q11862829",)), source_use=source_use(), egress=approval()).status,
            "PROPOSED")
        self.assertEqual(self.adapter(FakeBackend(items={"Q101": topic})).lookup(
            request(entity_type="TOPIC", local_entity_id="topic:mario", role_qid=None,
                    type_qids=()), source_use=source_use(), egress=approval()).status, "HOLD")
        self.assertEqual(self.adapter(FakeBackend(items={"Q101": org})).lookup(
            request(entity_type="ORGANIZATION", local_entity_id="organization:mario",
                    role_qid=None, reference_date="2020-01-01"),
            source_use=source_use(), egress=approval()).status, "PROPOSED")

    def test_malformed_results_fail_closed(self):
        for invalid in ["BAD", "Q0", 100]:
            with self.subTest(invalid=invalid):
                backend = FakeBackend(search=[invalid])
                self.assertEqual(self.adapter(backend).lookup(
                    request(), source_use=source_use(), egress=approval()).status, "HOLD")
        for row in [{**item(), "lastrevid": "not-a-revision"},
                    {**item(), "aliases": {"it": "not-a-list"}},
                    {**item(), "claims": {"P31": "bad"}}]:
            with self.subTest(row=row):
                self.assertEqual(self.adapter(FakeBackend(items={"Q101": row})).lookup(
                    request(), source_use=source_use(), egress=approval()).status, "HOLD")

    def test_timeout_rights_and_egress_fail_closed(self):
        for kwargs in [dict(source_use=None, egress=approval()),
                       dict(source_use=source_use("DENIED"), egress=approval()),
                       dict(source_use=source_use(), egress=None),
                       dict(source_use=source_use(), egress=approval(host="evil.example")),
                       dict(source_use=source_use(), egress=approval(expires_at=NOW)),
                       dict(source_use=source_use(), egress=approval(source_sha256="b" * 64))]:
            backend = FakeBackend()
            result = self.adapter(backend).lookup(request(), **kwargs)
            self.assertEqual(result.status, "HOLD")
            self.assertEqual(backend.search_calls, [])
        backend = FakeBackend(error=TimeoutError("no response"))
        self.assertEqual(self.adapter(backend).lookup(
            request(), source_use=source_use(), egress=approval()).reason, "PROVIDER_FAILURE")

    def test_disabled_by_default_and_bad_inputs_do_not_trigger_egress(self):
        backend = FakeBackend()
        self.assertEqual(WikidataProposalAdapter(backend=backend).lookup(
            request(), source_use=source_use(), egress=approval()).reason, "ADAPTER_DISABLED")
        self.assertEqual(self.adapter(backend).lookup(
            request(aliases=("",)), source_use=source_use(), egress=approval()).status, "HOLD")
        self.assertEqual(backend.search_calls, [])

    def test_bounded_cache_and_rate_limit_keep_receipt_observation(self):
        backend = FakeBackend()
        t = [100.0]
        adapter = self.adapter(backend, monotonic=lambda: t[0], min_interval_seconds=1.0,
                               cache_max_entries=1, cache_ttl_seconds=10)
        good = dict(source_use=source_use(), egress=approval())
        first = adapter.lookup(request(), **good)
        second = adapter.lookup(request(), **good)
        self.assertEqual(first, second)
        self.assertEqual(len(backend.search_calls), 2)  # two pre-existing local aliases
        self.assertEqual(adapter.lookup(request(), source_use=source_use("REVOKED"),
                                        egress=approval()).status, "HOLD")
        self.assertEqual(adapter.lookup(request(aliases=("M. Rossi",)), **good).reason, "RATE_LIMIT")
        t[0] += 1.0
        self.assertEqual(adapter.lookup(request(aliases=("M. Rossi",)), **good).status, "PROPOSED")
        self.assertLessEqual(adapter.cache_size, 1)

    def test_provider_read_only_api_is_bounded_and_anonymous(self):
        searches = []
        fetches = []

        class FakeItem:
            def get(self, **kwargs):
                fetches.append(kwargs)
                return SimpleNamespace(lastrevid=123, get_json=lambda: item())

        class FakeWBI:
            def __init__(self):
                self.item = FakeItem()

        fake_module = ModuleType("wikibaseintegrator")
        fake_module.WikibaseIntegrator = FakeWBI
        fake_module.wbi_helpers = SimpleNamespace(search_entities=lambda **kw: searches.append(kw) or ["Q101"])
        with patch.dict(sys.modules, {"wikibaseintegrator": fake_module}):
            client = WikibaseIntegratorReadOnly(user_agent="DP test (https://example.test)", spacing_seconds=0)
            self.assertEqual(client.search("Mario Rossi", language="it", limit=5, timeout=3), ["Q101"])
            self.assertEqual(client.get_item("Q101", timeout=3)["lastrevid"], 123)
        self.assertEqual(searches[0]["search_type"], "item")
        self.assertTrue(searches[0]["strict_language"])
        self.assertEqual(fetches[0]["allow_anonymous"], True)
        self.assertEqual(fetches[0]["entity_id"], "Q101")
        for entry in searches + fetches:
            self.assertEqual(entry["mediawiki_api_url"], "https://www.wikidata.org/w/api.php")
            self.assertEqual(entry["timeout"], (3, 3))
            self.assertEqual(entry["max_retries"], 1)
            self.assertEqual(entry["retry_after"], 0)
            self.assertIs(entry["allow_redirects"], False)

    def test_comparison_with_existing_local_alias_path(self):
        entities = [{"entity_type": "PERSON", "entity_id": "person:mario",
                     "canonical_name": "Mario Rossi", "aliases": ["M. Rossi"]}]
        existing = propose_alias_matches(mention_text="Mario Rossi", entity_type="PERSON", entities=entities)
        self.assertEqual(existing[0].decision, "CANDIDATE")
        proposed = self.adapter(FakeBackend()).lookup(request(), source_use=source_use(), egress=approval())
        self.assertEqual(existing[0].entity_id, proposed.proposals[0].local_entity_id)
        self.assertEqual(proposed.proposals[0].to_resolution_candidate(content_id="content:1").status,
                         "CANDIDATE")


if __name__ == "__main__":
    unittest.main()
