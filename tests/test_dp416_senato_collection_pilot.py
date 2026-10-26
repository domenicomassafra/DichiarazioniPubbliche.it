"""DP416: source-specific private Collection -> held Candidate acceptance seam."""
from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "poc"))

import dp416_senato_collection_pilot as pilot
from dichiarazioni_pubbliche.private_capture_rights import SourceUseBlocked, evaluate_source_use
from tests.test_dp236_source_use import CAPTURE_USES, SUBJECT, reviewed


def prepared_speech(*, speaker=None):
    sentence = "Prefazione. " + pilot.EXPECTED_TEXT
    fingerprint = hashlib.sha256(sentence.encode()).hexdigest()
    passage = SimpleNamespace(
        id=pilot._TARGET_PASSAGE, capture_id=pilot.EXPECTED_CAPTURE,
        text_sha256=fingerprint, private_text=sentence,
    )
    statement = SimpleNamespace(
        id=pilot._TARGET_STATEMENT, passage_ids=(passage.id,),
        statement_text_hash=fingerprint, normalized_statement=sentence,
        status="HELD", speaker_person_id=None, attribution_method=None,
        metadata={"source_speaker_ref": speaker or pilot.EXPECTED_SPEAKER},
    )
    return SimpleNamespace(
        capture=SimpleNamespace(id=pilot.EXPECTED_CAPTURE),
        statements=(statement,), passages=(passage,),
    )


class SenatoPrivateCollectionPilotTests(unittest.TestCase):
    def test_current_private_use_is_separate_from_parse_and_public_use(self):
        now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)

        def decision(record, use):
            return evaluate_source_use(
                record, subject=SUBJECT, rights_record_id="private-rights:approved",
                policy_version="private-use-policy-v1", use=use, now=now,
            ).status

        baseline = reviewed()
        self.assertEqual(decision(baseline, "EXTRACT_CANDIDATES"), "DENIED")
        granted = reviewed(permitted_uses=CAPTURE_USES + ("EXTRACT_CANDIDATES",))
        self.assertEqual(decision(granted, "EXTRACT_CANDIDATES"), "PERMITTED")
        self.assertEqual(decision(granted, "EXCERPT_PUBLIC"), "DENIED")
        self.assertEqual(decision(replace(granted, version_state="HISTORICAL"), "EXTRACT_CANDIDATES"), "REVOKED")

    def test_exact_pinned_document_derives_one_held_statement_without_identity(self):
        passage, statement = pilot._select(prepared_speech())
        self.assertEqual(statement.passage_ids, (passage.id,))
        self.assertEqual(statement.status, "HELD")
        self.assertIsNone(statement.speaker_person_id)
        self.assertIsNone(statement.attribution_method)
        with self.assertRaisesRegex(ValueError, "PINNED_SPEECH_OR_PASSAGE_MISMATCH"):
            pilot._select(prepared_speech(speaker="#other"))

    def test_grant_only_exact_private_derivation_and_preserve_existing_expiry(self):
        original = SimpleNamespace(
            id="private-rights:old", permitted_uses=tuple(sorted(pilot._BASE_USES)),
            attribution_requirements=("ATTRIBUTION_REQUIRED",),
            expires_at="2026-11-23T21:53:43+00:00",
        )
        rights = SimpleNamespace(read_current=Mock(return_value=original), record_rights=Mock())
        pilot._grant_private_derivation(rights, object(), original)
        supplied = rights.record_rights.call_args.kwargs
        self.assertEqual(set(supplied["permitted_uses"]), pilot._BASE_USES | {"EXTRACT_CANDIDATES"})
        self.assertEqual(supplied["expires_at"], original.expires_at)
        self.assertEqual(supplied["supersedes_record_id"], original.id)
        self.assertNotIn("EXCERPT_PUBLIC", supplied["permitted_uses"])
        self.assertNotIn("OMNIROUTE_MODEL_EXTRACTION_PRIVATE", supplied["permitted_uses"])

        original.permitted_uses += ("EXCERPT_PUBLIC",)
        with self.assertRaisesRegex(SourceUseBlocked, "SCOPE_CONFLICT"):
            pilot._grant_private_derivation(rights, object(), original)
        self.assertEqual(rights.record_rights.call_count, 1)

    def test_stale_rights_cannot_be_superseded(self):
        current = SimpleNamespace(id="private-rights:new")
        rights = SimpleNamespace(read_current=lambda _: current, record_rights=Mock())
        with self.assertRaisesRegex(SourceUseBlocked, "RIGHTS_CHANGED_BEFORE_GRANT"):
            pilot._grant_private_derivation(rights, object(), SimpleNamespace(id="private-rights:old"))
        rights.record_rights.assert_not_called()


if __name__ == "__main__":
    unittest.main()
