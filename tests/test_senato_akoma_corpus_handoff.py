"""Source/Capture/Passage/Statement held-handoff regression for DP-233."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from dichiarazioni_pubbliche.corpus_repository import (
    normalize_content_capture,
    normalize_passage,
    normalize_statement_candidate,
)
from dichiarazioni_pubbliche.senato_akoma_corpus_handoff import (
    SenatoAkomaParser,
    prepare_senato_corpus_handoff,
    verify_senato_handoff_roundtrip,
)
from dichiarazioni_pubbliche.senato_akoma_stenographic import SenatoAkomaError
from dichiarazioni_pubbliche.source_watcher import FetchedBytes
from tests.test_senato_akoma_stenographic import URL, blob_sha, fixture


class SenatoCorpusHandoffTests(unittest.TestCase):
    def _prepare(self, source: bytes | None = None):
        raw = fixture() if source is None else source
        return prepare_senato_corpus_handoff(
            raw, source_raw_url=URL, expected_blob_sha1=blob_sha(raw),
            content_id="content:official-senato-bulk-2025-05-29-310",
            observed_at="2026-10-10T10:00:00Z",
        )

    def test_canonical_records_private_source_bound_and_held(self):
        result = self._prepare()
        self.assertEqual(len(result.passages), 2)
        self.assertEqual(len(result.statements), 2)
        self.assertEqual(len(result.held_speeches), 1)
        capture = normalize_content_capture(result.capture.to_dict())
        self.assertEqual(capture.final_url, URL)
        self.assertEqual(capture.rights_status, "UNKNOWN")
        self.assertEqual(capture.hold_status, "RIGHTS_HOLD")
        self.assertEqual(capture.status, "QUARANTINED")
        self.assertEqual(capture.retention_class, "POLICY_PENDING")
        self.assertIsNone(capture.body_ref)
        self.assertEqual(capture.metadata["source_license_id"], "CC-BY-4.0")
        self.assertEqual(capture.metadata["source_commit_sha"], "a" * 40)
        self.assertEqual(capture.metadata["source_blob_sha1"], blob_sha(fixture()))
        self.assertEqual(result.claim_extraction_status, "BLOCKED_PENDING_PRIVATE_RIGHTS_AND_PROVIDER")

        self.assertNotEqual(result.statements[0].metadata["source_official_person_uri"],
                            result.statements[1].metadata["source_official_person_uri"])
        for passage, statement in zip(result.passages, result.statements, strict=True):
            p = normalize_passage(passage.to_dict())
            s = normalize_statement_candidate(statement.to_dict())
            self.assertEqual(s.passage_ids, (p.id,))
            self.assertEqual(s.status, "HELD")
            self.assertIsNone(s.speaker_person_id)
            self.assertIsNone(s.attribution_method)
            self.assertEqual(s.metadata["quote_review_status"], "UNREVIEWED_NORMALIZED_XML_TEXT")
            self.assertEqual(p.text_sha256, hashlib.sha256(s.normalized_statement.encode()).hexdigest())
            self.assertEqual(p.capture_id, capture.id)
            self.assertLess(p.start_char, p.end_char)

    def test_persisted_isolated_records_roundtrip_without_corpus_writes(self):
        prepared = self._prepare()
        with tempfile.TemporaryDirectory(prefix="senato-dp233-test-") as scratch:
            store = Path(scratch) / "private-handoff.json"
            store.write_text(json.dumps({
                "capture": prepared.capture.to_dict(),
                "passages": [p.to_dict() for p in prepared.passages],
                "statements": [s.to_dict() for s in prepared.statements],
                "source_sha256": prepared.source.source_sha256,
                "canonical_text_sha256": prepared.canonical_text_sha256,
                "license_id": prepared.source.source_license_id,
            }, sort_keys=True, ensure_ascii=False), encoding="utf-8")
            reread = json.loads(store.read_text(encoding="utf-8"))
            capture = normalize_content_capture(reread["capture"])
            passages = tuple(normalize_passage(p) for p in reread["passages"])
            statements = tuple(normalize_statement_candidate(s) for s in reread["statements"])
            self.assertEqual(capture.content_sha256, reread["source_sha256"])
            self.assertEqual([p.id for p in passages], [p.id for p in prepared.passages])
            self.assertEqual([s.id for s in statements], [s.id for s in prepared.statements])
            self.assertTrue(all(s.status == "HELD" and s.speaker_person_id is None for s in statements))
            self.assertTrue(all(p.capture_id == capture.id for p in passages))
            self.assertEqual(reread["license_id"], "CC-BY-4.0")
        self.assertFalse(store.exists())

    def test_parser_hook_checks_effective_final_url_and_blob(self):
        raw = fixture()
        parser = SenatoAkomaParser(source_raw_url=URL, expected_blob_sha1=blob_sha(raw))
        def fetched(final_url: str, body: bytes = raw) -> FetchedBytes:
            return FetchedBytes(
                body=body, final_url=final_url, status_code=200,
                media_type="application/akn+xml", charset="utf-8",
                content_length=len(body),
            )
        good = parser.parse(fetched(URL))
        self.assertEqual(good.status, "SUCCEEDED")
        self.assertEqual(len(good.spans), 2)
        self.assertEqual(good.metadata["held_speech_count"], 1)
        self.assertEqual(good.metadata["speaker_and_quote_approval"], "NOT_GRANTED")
        self.assertEqual(good.metadata["source_blob_sha1"], blob_sha(raw))
        self.assertEqual(parser.parse(fetched("https://evil.example/")).error_category,
                         "SENATO_AKN_SOURCE_REDIRECT_MISMATCH")
        self.assertEqual(parser.parse(fetched(URL, raw + b" ")).error_category,
                         "SENATO_AKN_BLOB_MISMATCH")

    def test_revision_changes_ids_and_unknown_observation_refused(self):
        first = self._prepare()
        second = self._prepare(fixture().replace(b"Un dato", b"Due dati"))
        self.assertNotEqual(first.capture.id, second.capture.id)
        self.assertNotEqual(first.passages[1].id, second.passages[1].id)
        self.assertNotEqual(first.statements[1].id, second.statements[1].id)
        with self.assertRaisesRegex(ValueError, "OBSERVATION_TIMEZONE_REQUIRED"):
            prepare_senato_corpus_handoff(
                fixture(), source_raw_url=URL, expected_blob_sha1=blob_sha(fixture()),
                content_id="content:example", observed_at="2026-10-10T10:00:00",
            )

    def test_readback_verifier_rejects_altered_passage_selector_text_and_rights(self):
        original = self._prepare()
        verify_senato_handoff_roundtrip(original, fixture())
        cases = (
            replace(original, passages=(replace(original.passages[0], start_char=1), original.passages[1])),
            replace(original, passages=(replace(original.passages[0], private_text="altered"), original.passages[1])),
            replace(original, statements=(replace(original.statements[0], speaker_person_id="person:guessed"),
                                          original.statements[1])),
            replace(original, capture=replace(original.capture, rights_status="CLEARED")),
        )
        for corrupted in cases:
            with self.subTest(corrupted=corrupted), self.assertRaisesRegex(
                SenatoAkomaError, "HANDOFF_SOURCE_ROUNDTRIP_MISMATCH"
            ):
                verify_senato_handoff_roundtrip(corrupted, fixture())
        with self.assertRaisesRegex(SenatoAkomaError, "BLOB_MISMATCH"):
            verify_senato_handoff_roundtrip(original, fixture() + b" ")


if __name__ == "__main__":
    unittest.main()
