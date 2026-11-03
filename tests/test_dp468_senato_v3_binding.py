"""The production Senato adapter never converts stored metadata into public authority."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock

from dichiarazioni_pubbliche.autonomous_runner_v3 import SQLiteRunJournal
from dichiarazioni_pubbliche.public_projection import build_public_projection
from dichiarazioni_pubbliche.senato_v3_binding import bind_senato_public_v3
from tests.test_autonomous_publication import written_candidate
from tests.test_dp468_senato_public_v3_source import setup


class SenatoV3BindingTests(TestCase):
    def setUp(self):
        self.tempdir = TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.journal = SQLiteRunJournal(Path(self.tempdir.name) / "reviews.sqlite3")
        self.raw, self.pins, _, record = setup()
        self.approved = {**record, "status": "APPROVED", "quote": "Un dato: zero."}
        self.capture = Mock()
        self.capture.find_capture.return_value = {
            "content_id": self.pins.content_id,
            "content_sha256": self.pins.xml_sha256,
            "final_url": self.pins.source_raw_url,
            "status": "CAPTURED", "hold_status": "NONE",
            "rights_status": "CLEARED", "body_purged_at": None,
            "body_ref": "body:private",
        }

        def query(sql, **_parameters):
            if "FROM statement_candidate s" in sql:
                return json.dumps([self.approved])
            if "FROM public_statement_authority_event" in sql:
                return "[]"
            raise AssertionError("unexpected persistent query")

        self.capture.run.side_effect = query
        self.body = Mock(read=Mock(return_value=self.raw))
        self.guard = Mock()
        self.guard.subject.source_family = "senato_open_data_akn"

    def bind(self, **overrides):
        arguments = dict(
            pins=self.pins, capture_store=self.capture, body_store=self.body,
            private_source_guard=self.guard, journal=self.journal,
            read_current_candidate=lambda _id, _version: None,
            verify_provider_execution=lambda _receipt: False,
            verify_authority_review=lambda _receipt: False,
            processing_family_approved=lambda: True,
            primary_agent_id="agent:primary",
            primary_model_id="antigravity/gemini-3.8-flash-tiered",
            independent_agent_id="agent:second",
            independent_model_id="antigravity/gemini-3-flash",
        )
        arguments.update(overrides)
        return bind_senato_public_v3(**arguments)

    def test_approved_private_row_without_authenticated_provider_receipts_is_omitted(self):
        source = self.bind()
        self.assertEqual(len(source.projectable_public_statements()), 1)
        result = build_public_projection(
            source, generated_at="2026-11-03T11:00:00Z", include_public_statements=True,
        )
        self.assertEqual(result["statements"], [])
        self.assertFalse(source.autonomous_publication_evidence(
            self.approved["statement_id"], self.approved["version_id"],
        ))

    def test_missing_independent_verifiers_cannot_be_bound(self):
        for missing in (
            "verify_provider_execution", "verify_authority_review",
            "processing_family_approved", "read_current_candidate",
        ):
            with self.subTest(missing=missing):
                with self.assertRaisesRegex(ValueError, "DP468_TRUSTED_AUTHORITY_REQUIRED"):
                    self.bind(**{missing: None})

    def test_current_model_receipts_are_accepted_only_while_provider_witness_confirms(self):
        from tests.test_dp413_persisted_review_reader import (
            PRIMARY, SECOND, PersistedReviewReaderTests,
        )
        provider = PersistedReviewReaderTests(methodName="runTest")
        provider.setUp()
        self.addCleanup(provider.doCleanups)
        canonical = setup()[2]
        record = self.approved
        provider.current = replace(
            written_candidate(),
            record_id=record["statement_id"],
            record_version_id=record["version_id"],
            source_version=self.pins.xml_sha256,
            source_url=self.pins.source_raw_url,
            source_kind="WRITTEN",
            snapshot_url=self.pins.source_raw_url,
            snapshot_sha256=self.pins.xml_sha256,
            source_text_sha256=self.pins.canonical_text_sha256,
            captured_at=datetime.now(timezone.utc).isoformat(),
            segment_start=record["start_char"],
            segment_end=record["end_char"],
            quote=record["quote"],
            transcript_segment=record["quote"],
            alignment_confidence=None,
            speaker_id=record["person_id"],
            public_role_source_url="https://www.senato.it/leg/19/assemblea",
            public_context_source_url="https://www.senato.it/leg/19/assemblea",
            person_is_minor=False,
            sensitive_third_party_data=False,
            privacy_cleared=True,
            rights_cleared=True,
            source_length_chars=len(canonical),
            contains_editorial_judgment=False,
        )
        source = self.bind(
            journal=provider.journal,
            read_current_candidate=provider.read_candidate,
            verify_provider_execution=provider.provider_witness,
            primary_agent_id="agent:primary", primary_model_id=PRIMARY,
            independent_agent_id="agent:independent", independent_model_id=SECOND,
        )
        statement_id, version_id = record["statement_id"], record["version_id"]
        self.assertIsNone(source.autonomous_publication_evidence(statement_id, version_id))
        provider.complete()  # Test fixture: simulated gateway completions and separate witness.
        proof = source.autonomous_publication_evidence(statement_id, version_id)
        self.assertIsNotNone(proof)
        self.assertEqual(proof.candidate, provider.current)
        # Provider proof alone cannot grant the independently reviewed rights.
        self.assertEqual(build_public_projection(
            source, generated_at="2026-11-03T11:00:00Z", include_public_statements=True,
        )["statements"], [])
        provider.gateway_events.clear()
        self.assertIsNone(source.autonomous_publication_evidence(statement_id, version_id))
