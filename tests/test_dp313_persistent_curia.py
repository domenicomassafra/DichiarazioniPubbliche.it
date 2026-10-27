"""Public parser seam: source-bound court passages for durable private capture."""

import hashlib
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from dichiarazioni_pubbliche.capture_authorization import require_private_capture_rights
from dichiarazioni_pubbliche.capture_pipeline import verify_passage_roundtrip
from dichiarazioni_pubbliche.corpus_repository import PassageRecord
from dichiarazioni_pubbliche.source_watcher import FetchedBytes

from tests.test_capture_authorization import record
from tests.test_dp313_curia_private_readback import TEXT, digest, specimen
from tools.dp313_curia_persistent_pilot import (
    CONTENT_ID,
    FAMILY,
    SOURCE_URL,
    CuriaJudgmentParser,
    _existing_chain,
    fetch_official_original,
    main,
)
from tools.dp313_curia_private_intake_rights import USES
from tools.dp313_curia_private_readback import SOURCE_SHA256


class CuriaPersistentParserTests(unittest.TestCase):
    def test_apply_with_revoked_rights_must_not_fetch_official_body(self):
        with (
            patch.object(sys, "argv", ["dp313", "--apply-private-intake", "--database-url", "test-db"]),
            patch("tools.dp313_curia_persistent_pilot.CapturePipelineStore"),
            patch("tools.dp313_curia_persistent_pilot._identities"),
            patch("tools.dp313_curia_persistent_pilot._rights",
                  side_effect=RuntimeError("DP313_RIGHTS_NOT_CURRENT")),
            patch("tools.dp313_curia_persistent_pilot.fetch_official_original") as fetch,
            patch("builtins.print"),
        ):
            self.assertEqual(main(), 2)
            fetch.assert_not_called()

    def test_private_judicial_capture_requires_specific_capture_grant(self):
        current = replace(record(), content_id=CONTENT_ID, source_family=FAMILY,
                          locator_value=SOURCE_URL, permitted_uses=USES)
        require_private_capture_rights(
            current, rights_record_id=current.id, content_id=CONTENT_ID,
            canonical_url=SOURCE_URL, source_family=FAMILY,
        )
        self.assertNotIn("EXCERPT_PUBLIC", USES)

    def test_official_text_yields_exact_four_separate_held_passages(self):
        raw = specimen()
        fetched = FetchedBytes(raw, "https://juris.curia.europa.eu/juris/document/document.jsf?docid=312911&doclang=IT",
                               200, "text/html", "utf-8", len(raw))
        parser = CuriaJudgmentParser(expected_sha256=digest(TEXT))
        result = parser.parse(fetched)
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(result.canonical_text, TEXT)
        self.assertEqual(len(result.spans), 4)
        self.assertEqual([span.text for span in result.spans],
                         [TEXT[span.start_char:span.end_char] for span in result.spans])
        self.assertTrue(all(span.text_sha256 == digest(span.text) for span in result.spans))
        self.assertIn("Con decisione del 15 luglio 2022", result.spans[1].text)
        self.assertIn("è annullata", result.spans[3].text)
        first = result.spans[0]
        self.assertTrue(verify_passage_roundtrip(
            body=raw, media_type="text/html", charset="utf-8",
            passage=PassageRecord(
                id="passage:roundtrip", content_id=CONTENT_ID,
                capture_id="capture:roundtrip", selector_type="TEXT_POSITION",
                start_char=first.start_char, end_char=first.end_char,
                text_sha256=first.text_sha256, private_text=first.text,
                language="it", extraction_method=parser.parser_method,
                extraction_version=parser.parser_version,
            ), parser=parser,
        ))

    def test_changed_official_content_fails_before_private_persistence(self):
        raw = specimen(TEXT.replace("non iscrivere", "iscrivere"))
        fetched = FetchedBytes(raw, "https://juris.curia.europa.eu/juris/document/document.jsf?docid=312911&doclang=IT",
                               200, "text/html", "utf-8", len(raw))
        with self.assertRaisesRegex(ValueError, "SOURCE_DIGEST_CHANGED"):
            CuriaJudgmentParser(expected_sha256=digest(TEXT)).parse(fetched)

    def test_fetch_redirect_to_non_original_is_rejected_before_any_rights_write(self):
        original = specimen()
        redirected = FetchedBytes(original, "https://unrelated.example/curia.html",
                                  200, "text/html", "utf-8", len(original))
        with (
            patch("tools.dp313_curia_persistent_pilot.fetch_bytes", return_value=redirected),
            self.assertRaisesRegex(ValueError, "DP313_OFFICIAL_FETCH_IDENTITY_MISMATCH"),
        ):
            fetch_official_original()

    def test_reused_chain_refuses_corrupted_passage_even_with_valid_capture_hash(self):
        raw = specimen()
        source = FetchedBytes(raw, SOURCE_URL, 200, "text/html", "utf-8", len(raw))
        parsed = CuriaJudgmentParser(expected_sha256=digest(TEXT)).parse(source)
        roles = ["PARTY_ALLEGATION", "PRIOR_DECISION_REPORTED_BY_COURT",
                 "COURT_DISPOSITION", "COURT_ANNULMENT_OF_REPORTED_DECISION"]
        parts = [{"id": f"passage:{i}", "candidate": f"candidate:{i}", "role": roles[i],
                      "start": s.start_char, "end": s.end_char, "sha": s.text_sha256,
                      "text": s.text, "statement": s.text, "statement_sha": s.text_sha256,
                      "privacy": "HOLD", "public": "false", "speaker": None, "state": "HELD",
                      "family": FAMILY, "version": SOURCE_SHA256}
                 for i, s in enumerate(parsed.spans)]
        parts[1]["text"] = "testo differente dall'originale"
        row = {"id": "capture:original", "sha": hashlib.sha256(raw).hexdigest(),
                   "body": "captures/verified.body", "parts": parts}

        class Stored:
            def run(self, *_args, **_kwargs):
                return json.dumps(row)

        class Body:
            def read(self, *_args, **_kwargs):
                return raw

        with (
            patch("tools.dp313_curia_persistent_pilot.CaptureBodyStore.open_existing_readonly",
                  return_value=Body()),
            self.assertRaisesRegex(RuntimeError, "DP313_EXISTING_CHAIN_CONFLICT"),
        ):
            _existing_chain(Stored(), Path("/unused"), parsed, roles)


if __name__ == "__main__":
    unittest.main()
