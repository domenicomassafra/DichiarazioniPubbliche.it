"""Synthetic private Italian NER gold; no external model or source material."""

import hashlib
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.candidate_extraction import (  # noqa: E402
    AliasLexiconRow, CandidateExtractionError, extract_passage_candidates,
)
from dichiarazioni_pubbliche.candidate_spacy_private import (  # noqa: E402
    ApprovedSpaCyModel, SpaCyItalianPrivateAdapter,
    extract_passage_candidates_with_spacy,
)
from dichiarazioni_pubbliche.private_candidate_commit_fence import (  # noqa: E402
    PrivateCandidateCommitFence,
)
from test_candidate_extraction import (  # noqa: E402
    FakeProvider, FakeStore, written_context_for,
)

GOLD = (
    'Giulia Riva ha detto: «La stampa citava “Giulia Riva” a Valleverde». '
    'Agenzia Faro riferì: «Giulia Riva aveva detto sì». '
    'La parola organizzare non è un nome.'
)
ENTITIES = (
    ("Giulia Riva", "PER", 3),
    ("Agenzia Faro", "ORG", 1),
    ("Valleverde", "LOC", 1),
)


class FakeEntity:
    def __init__(self, text, start, end, label):
        self.text, self.start_char, self.end_char, self.label_ = text, start, end, label


class FakeDocument:
    def __init__(self, text, entities):
        self.text, self.ents = text, entities


class FakeItalianPipeline:
    lang = "it"
    meta = {"license": "MIT"}
    pipe_names = ("ner",)

    def __init__(self, invalid=False):
        self.invalid = invalid

    def to_bytes(self):
        return b"synthetic-italian-ner-fixture-v1"

    def __call__(self, text):
        spans = []
        for literal, label, _ in ENTITIES:
            position = 0
            while (start := text.find(literal, position)) >= 0:
                spans.append(FakeEntity(text[start:start + len(literal)], start,
                                        start + len(literal), label))
                position = start + len(literal)
        if self.invalid:
            spans.append(FakeEntity("tampered", 0, 6, "PER"))
        return FakeDocument(text, tuple(spans))


def approval(pipeline=None, **changes):
    pipeline = pipeline or FakeItalianPipeline()
    details = {
        "source_url": "https://example.org/synthetic-italian-ner-fixture",
        "revision": "fixture-v1",
        "license_id": "MIT",
        "pipeline_sha256": hashlib.sha256(pipeline.to_bytes()).hexdigest(),
    }
    details.update(changes)
    return ApprovedSpaCyModel(**details)


def fixture():
    context = written_context_for(GOLD, content_id="synthetic-gold")
    aliases = (
        AliasLexiconRow("PERSON", "person:unconfirmed-a", "Giulia Riva",
                        "Giulia Riva", "CANONICAL_NAME"),
        AliasLexiconRow("PERSON", "person:unconfirmed-b", "Giulia Riva",
                        "Giulia Riva", "ALIAS"),
    )
    store = FakeStore(context=context, aliases=aliases)
    statement_start = GOLD.index("La stampa")
    statement_end = statement_start + len('La stampa citava “Giulia Riva” a Valleverde')
    provider = FakeProvider({"statements": [{
        "start_char": statement_start, "end_char": statement_end,
        "normalized_statement": 'La stampa citava Giulia Riva a Valleverde.',
        "speaker_mention": None, "speech_mode": "REPORTED_SPEECH",
        "entity_mentions": [], "claims": [],
    }]})
    fence = PrivateCandidateCommitFence(
        collection_id="collection:synthetic", content_id=context.content_id,
        capture_id=context.capture_id, passage_id=context.passage_id,
        passage_sha256=context.text_sha256,
        canonical_url="https://example.org/synthetic-gold",
        source_family="synthetic-source", rights_record_id="rights:synthetic",
    )
    return context, store, provider, fence


class SpaCyPrivateCandidateTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = FakeItalianPipeline()
        self.adapter = SpaCyItalianPrivateAdapter(
            self.pipeline, approval=approval(self.pipeline)
        )

    def test_gold_homonyms_nested_quotes_reported_speech_and_negative_word(self):
        """Five synthetic gold mentions, with exact offsets/hashes; no guessed identity."""
        context, store, provider, fence = fixture()
        spans = self.adapter.propose(
            text=GOLD, text_sha256=context.text_sha256, language="it"
        )
        self.assertEqual(len(spans), 5)
        self.assertEqual(
            {label: sum(span.label == label for span in spans)
             for label in ("PER", "ORG", "LOC")},
            {"PER": 3, "ORG": 1, "LOC": 1},
        )
        self.assertEqual(len({s.start_char for s in spans if s.label == "PER"}), 3)
        self.assertFalse(any("organizzare" in span.text for span in spans))
        for span in spans:
            self.assertEqual(GOLD[span.start_char:span.end_char], span.text)
            self.assertEqual(hashlib.sha256(span.text.encode()).hexdigest(), span.text_sha256)

        receipt = extract_passage_candidates_with_spacy(
            passage_id=context.passage_id, store=store, provider=provider,
            adapter=self.adapter, authorization_guard=lambda: None, commit_fence=fence,
        )
        self.assertEqual(receipt.status, "COMPLETED")
        batch = store.committed_batches[0]
        self.assertEqual(len(batch.mentions), 11)  # six known-alias + five spaCy
        self.assertEqual(len(batch.resolutions), 6)
        self.assertEqual(
            {candidate.target_id for candidate in batch.resolutions},
            {"person:unconfirmed-a", "person:unconfirmed-b"},
        )
        ner_mentions = [m for m in batch.mentions if m.metadata.get("ner_backend") == "spacy"]
        self.assertEqual(len(ner_mentions), 5)
        self.assertTrue(all(m.extraction_method == "MODEL" for m in ner_mentions))
        self.assertTrue(all(m.metadata["review_required"] for m in ner_mentions))
        self.assertIsNone(next(m for m in ner_mentions
                               if m.metadata["ner_label"] == "LOC").proposed_entity_type)
        self.assertEqual(batch.statements[0].statement.speaker_person_id, None)
        self.assertEqual(batch.claims, ())
        self.assertEqual(batch.statements[0].statement.metadata["speech_mode"], "REPORTED_SPEECH")

        replay = extract_passage_candidates_with_spacy(
            passage_id=context.passage_id, store=store, provider=provider,
            adapter=self.adapter, authorization_guard=lambda: None, commit_fence=fence,
        )
        self.assertTrue(replay.replayed)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(len(store.committed_batches), 1)

    def test_existing_extraction_remains_equal_when_opt_in_disabled(self):
        context, store, provider, _ = fixture()
        receipt = extract_passage_candidates(
            passage_id=context.passage_id, store=store, provider=provider
        )
        self.assertEqual(receipt.status, "COMPLETED")
        self.assertEqual(len(store.committed_batches[0].mentions), 6)
        self.assertEqual(len(store.committed_batches[0].resolutions), 6)
        self.assertEqual(store.committed_batches[0].claims, ())

    def test_missing_rights_fence_fails_before_any_private_read_or_provider_call(self):
        context, store, provider, fence = fixture()
        with patch.object(store, "load_passage", wraps=store.load_passage) as read:
            for guard, active_fence in ((None, fence), (lambda: None, None)):
                with self.subTest(guard=bool(guard)):
                    with self.assertRaisesRegex(CandidateExtractionError, "AUTHORITY_REQUIRED"):
                        extract_passage_candidates_with_spacy(
                            passage_id=context.passage_id, store=store,
                            provider=provider, adapter=self.adapter,
                            authorization_guard=guard, commit_fence=active_fence,
                        )
            read.assert_not_called()
        self.assertEqual(provider.calls, 0)

    def test_revoked_guard_blocks_before_private_read(self):
        context, store, provider, fence = fixture()
        def revoked():
            raise CandidateExtractionError("PRIVATE_RIGHTS_REVOKED")
        with patch.object(store, "load_passage", wraps=store.load_passage) as read:
            with self.assertRaisesRegex(CandidateExtractionError, "PRIVATE_RIGHTS_REVOKED"):
                extract_passage_candidates_with_spacy(
                    passage_id=context.passage_id, store=store, provider=provider,
                    adapter=self.adapter, authorization_guard=revoked, commit_fence=fence,
                )
            read.assert_not_called()
        self.assertEqual(provider.calls, 0)

    def test_revocation_after_provider_call_holds_all_candidate_writes(self):
        context, store, provider, fence = fixture()
        checks = 0

        def guard():
            nonlocal checks
            checks += 1
            if checks >= 6:
                raise CandidateExtractionError("PRIVATE_RIGHTS_REVOKED")

        receipt = extract_passage_candidates_with_spacy(
            passage_id=context.passage_id, store=store, provider=provider,
            adapter=self.adapter, authorization_guard=guard, commit_fence=fence,
        )
        self.assertEqual(receipt.status, "BLOCKED")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(store.committed_batches, [])

    def test_provider_and_spacy_overlap_keeps_single_candidate(self):
        context, store, provider, fence = fixture()
        begin = GOLD.index("Giulia Riva")
        provider.payload["statements"][0]["entity_mentions"] = [{
            "start_char": begin, "end_char": begin + len("Giulia Riva"),
            "entity_type": "PERSON",
        }]
        result = extract_passage_candidates_with_spacy(
            passage_id=context.passage_id, store=store, provider=provider,
            adapter=self.adapter, authorization_guard=lambda: None, commit_fence=fence,
        )
        self.assertEqual(result.status, "COMPLETED")
        batch = store.committed_batches[0]
        overlaps = [m for m in batch.mentions if m.start_char == begin
                    and m.proposed_entity_type == "PERSON"
                    and m.extraction_method == "MODEL"]
        self.assertEqual(len(overlaps), 1)

    def test_stale_hash_and_wrong_language_hold_without_calls(self):
        for changed in (
            {"text_sha256": "f" * 64},
            {"language": "en"},
        ):
            with self.subTest(changed=changed):
                context, store, provider, fence = fixture()
                store.context = replace(context, **changed)
                with self.assertRaises(CandidateExtractionError):
                    extract_passage_candidates_with_spacy(
                        passage_id=context.passage_id, store=store, provider=provider,
                        adapter=self.adapter, authorization_guard=lambda: None,
                        commit_fence=fence,
                    )
                self.assertEqual(provider.calls, 0)
                self.assertEqual(store.committed_batches, [])

    def test_bad_spans_fail_closed(self):
        invalid = FakeItalianPipeline(invalid=True)
        adapter = SpaCyItalianPrivateAdapter(invalid, approval=approval(invalid))
        context, _, _, _ = fixture()
        with self.assertRaisesRegex(CandidateExtractionError, "SPAN_INVALID"):
            adapter.propose(text=GOLD, text_sha256=context.text_sha256, language="it")

    def test_model_approval_license_hash_and_ner_are_mandatory(self):
        for kwargs, code in (
            ({"license_id": "CC-BY-NC-SA-3.0"}, "LICENSE_NOT_APPROVED"),
            ({"pipeline_sha256": "0" * 64}, "DIGEST_MISMATCH"),
            ({"source_url": "http://unsafe.test/model"}, "SOURCE_INVALID"),
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(CandidateExtractionError, code):
                    SpaCyItalianPrivateAdapter(self.pipeline, approval=approval(self.pipeline, **kwargs))
        self.pipeline.meta["license"] = "CC BY-NC-SA 3.0"
        with self.assertRaisesRegex(CandidateExtractionError, "LICENSE_MISMATCH"):
            SpaCyItalianPrivateAdapter(self.pipeline, approval=approval(self.pipeline))
        self.pipeline.meta["license"] = "MIT"
        self.pipeline.pipe_names = ("tokenizer",)
        with self.assertRaisesRegex(CandidateExtractionError, "NER_MISSING"):
            SpaCyItalianPrivateAdapter(self.pipeline, approval=approval(self.pipeline))

    def test_missing_local_model_fails_closed_without_auto_download(self):
        with self.assertRaisesRegex(CandidateExtractionError, "MODEL_UNAVAILABLE"):
            SpaCyItalianPrivateAdapter.load(
                Path("/nonexistent/dp-spacy-italian-model"), approval=approval()
            )

    def test_pipeline_mutation_after_approval_is_blocked(self):
        self.pipeline.invalid = True
        self.pipeline.to_bytes = lambda: b"mutated-unapproved-model"
        context, _, _, _ = fixture()
        with self.assertRaisesRegex(CandidateExtractionError, "SPACY_MODEL_CHANGED"):
            self.adapter.propose(
                text=GOLD, text_sha256=context.text_sha256, language="it"
            )

    def test_real_spacy_entity_ruler_gold_when_optional_package_installed(self):
        try:
            import spacy
        except ImportError:
            self.skipTest("optional spaCy not installed in stdlib contributor profile")
        nlp = spacy.blank("it")
        nlp.meta["license"] = "MIT"
        ruler = nlp.add_pipe("entity_ruler")
        ruler.add_patterns([
            {"label": label, "pattern": phrase} for phrase, label, _ in ENTITIES
        ])
        adapter = SpaCyItalianPrivateAdapter(nlp, approval=approval(nlp))
        context, _, _, _ = fixture()
        spans = adapter.propose(
            text=GOLD, text_sha256=context.text_sha256, language="it"
        )
        self.assertEqual([(s.start_char, s.end_char, s.label)
                          for s in spans], [(s.start_char, s.end_char, s.label)
                                            for s in self.adapter.propose(
                                                text=GOLD, text_sha256=context.text_sha256,
                                                language="it")])


if __name__ == "__main__":
    unittest.main()
