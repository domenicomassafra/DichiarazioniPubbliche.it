"""DP-468 source-to-projection contract: genuine AKN parser, zero fabricated grants."""

from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from dichiarazioni_pubbliche.private_capture_rights import (
    SourceFamilyUseGuard, SourceUseBlocked,
)
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)
from dichiarazioni_pubbliche.public_projection import build_public_projection
from dichiarazioni_pubbliche.public_schema import PUBLIC_STATEMENT_SCHEMA_VERSION
from dichiarazioni_pubbliche.senato_public_v3_source import (
    CurrentSenatoCaptureBytes,
    PinnedSenatoV3Source,
    SenatoPublicV3Source,
)
from dichiarazioni_pubbliche.senato_akoma_corpus_handoff import (
    _canonical_document,
)
from tests.test_senato_akoma_stenographic import URL, blob_sha, fixture, imported


def setup():
    raw = fixture()
    source = imported(raw)
    canonical, _, _, included = _canonical_document(source)
    speech = included[1][0]  # Official AKN person/turn, still unapproved.
    start = canonical.index("Un dato:")
    pins = PinnedSenatoV3Source(
        content_id="content:official-senato",
        source_raw_url=URL,
        xml_sha256=hashlib.sha256(raw).hexdigest(),
        git_blob_sha1=blob_sha(raw),
        canonical_text_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
    )
    record = {
        "statement_id": "statement:senato:held",
        "version_id": "version:senato:1",
        "status": "HELD",
        "content_id": pins.content_id,
        "source_version": pins.xml_sha256,
        "speech_id": speech.speech_id,
        "official_person_uri": speech.official_person_uri,
        "person_id": "person:unapproved",
        "speaker_name": "Persona non approvata",
        "start_char": start,
        "end_char": start + len("Un dato: zero."),
    }
    return raw, pins, canonical, record


class SenatoPublicV3ProducerTests(unittest.TestCase):
    def build(self, source):
        return build_public_projection(
            source, generated_at="2026-10-31T12:00:00Z",
            include_public_statements=True,
        )

    def test_real_xml_without_public_authority_remains_empty(self):
        raw, pins, canonical, _ = setup()
        source = SenatoPublicV3Source(pins, read_original_bytes=lambda: raw)
        self.assertEqual(source.get_statement_source_text(pins.content_id, pins.xml_sha256), canonical)
        bundle = self.build(source)
        self.assertEqual(bundle["schema_version"], PUBLIC_STATEMENT_SCHEMA_VERSION)
        self.assertEqual(bundle["statements"], [])
        self.assertEqual(bundle["dossiers"], [])
        self.assertEqual(bundle["omitted_count"], 0)

    def test_live_capture_and_private_use_guard_around_original_read(self):
        raw, pins, _, _ = setup()
        row = {
            "id": "capture:real",
            "content_id": pins.content_id,
            "content_sha256": pins.xml_sha256,
            "final_url": pins.source_raw_url,
            "status": "CAPTURED",
            "hold_status": "NONE",
            "rights_status": "CLEARED",
            "body_ref": "body:private",
            "body_purged_at": None,
        }
        capture = Mock(find_capture=Mock(return_value=row))
        body = Mock(read=Mock(return_value=raw))
        guard = Mock(require=Mock())
        guard.subject.source_family = "senato_open_data_akn"
        read_bytes = CurrentSenatoCaptureBytes(
            pins, capture_store=capture, body_store=body,
            private_source_guard=guard,
        )
        source = SenatoPublicV3Source(pins, read_original_bytes=read_bytes)
        self.assertEqual(source.projectable_public_statements(), [])
        self.assertEqual(
            source.get_statement_source_text(pins.content_id, pins.xml_sha256),
            setup()[2],
        )
        self.assertEqual(guard.require.call_count, 2)
        self.assertEqual(capture.find_capture.call_count, 2)
        body.read.assert_called_once_with(
            "body:private", expected_sha256=pins.xml_sha256, max_bytes=3_000_000,
        )

    def test_private_parse_right_is_bound_to_exact_senato_subject_before_body_read(self):
        raw, pins, _, _ = setup()
        capture_row = {
            "content_id": pins.content_id, "content_sha256": pins.xml_sha256,
            "final_url": pins.source_raw_url, "status": "CAPTURED",
            "hold_status": "NONE", "rights_status": "CLEARED",
            "body_ref": "body:private", "body_purged_at": None,
        }
        now = datetime(2026, 10, 31, 8, tzinfo=timezone.utc)

        def guard_for(*, content_id, url, family):
            subject = RightsSubject(
                source_family=family, locator_kind="URL",
                locator_value=url, content_id=content_id,
            )
            record = PrivateRightsRecord(
                id="private-rights:senato", subject_fingerprint=rights_subject_fingerprint(subject),
                source_family=family, locator_kind="URL", locator_value=url,
                content_id=content_id, evidence_id=None,
                transcript_segment_id=None, canonical_segment_id=None, passage_id=None,
                rights_status="CLEARED", rights_receipt_ref="receipt:source",
                permitted_uses=("PARSE_TEXT",), attribution_requirements=(),
                reviewed_at=(now - timedelta(days=1)).isoformat(),
                expires_at=(now + timedelta(days=1)).isoformat(),
                reviewer_ref="reviewer:source", policy_version="private-use-policy-v1",
                record_visibility="PRIVATE", supersedes_id=None, version_state="CURRENT",
            )
            return SourceFamilyUseGuard(
                read_current=lambda _: record, subject=subject,
                rights_record_id=record.id, policy_version=record.policy_version,
                expected_sha256=pins.xml_sha256, clock=lambda: now,
            )

        for details in (
            {"content_id": "content:other", "url": "https://example.org/other.xml",
             "family": "senato_open_data_akn"},
            {"content_id": pins.content_id, "url": pins.source_raw_url,
             "family": "other_official_source"},
        ):
            with self.subTest(details=details):
                body_store = Mock(read=Mock(return_value=raw))
                reader = CurrentSenatoCaptureBytes(
                    pins,
                    capture_store=Mock(find_capture=Mock(return_value=capture_row)),
                    body_store=body_store,
                    private_source_guard=guard_for(**details),
                )
                with self.assertRaises(SourceUseBlocked):
                    reader()
                body_store.read.assert_not_called()

        accepted = CurrentSenatoCaptureBytes(
            pins,
            capture_store=Mock(find_capture=Mock(return_value=capture_row)),
            body_store=Mock(read=Mock(return_value=raw)),
            private_source_guard=guard_for(
                content_id=pins.content_id, url=pins.source_raw_url,
                family="senato_open_data_akn",
            ),
        )
        self.assertEqual(accepted(), raw)

    def test_capture_hold_revocation_and_midread_swap_refuse_original(self):
        raw, pins, _, _ = setup()
        good = {
            "content_id": pins.content_id,
            "content_sha256": pins.xml_sha256,
            "final_url": pins.source_raw_url,
            "status": "CAPTURED",
            "hold_status": "NONE",
            "rights_status": "CLEARED",
            "body_ref": "body:private",
            "body_purged_at": None,
        }
        for damage in (
            {"hold_status": "RIGHTS_HOLD"},
            {"status": "QUARANTINED"},
            {"body_ref": None},
            {"final_url": "https://invalid.example/source"},
            {"rights_status": "UNKNOWN"},
        ):
            with self.subTest(damage=damage):
                guard = Mock(require=Mock())
                guard.subject.source_family = "senato_open_data_akn"
                reader = CurrentSenatoCaptureBytes(
                    pins,
                    capture_store=Mock(find_capture=Mock(return_value={**good, **damage})),
                    body_store=Mock(read=Mock(return_value=raw)),
                    private_source_guard=guard,
                )
                with self.assertRaisesRegex(ValueError, "CURRENT_CAPTURE_UNAVAILABLE"):
                    reader()
        guard = Mock(require=Mock())
        guard.subject.source_family = "senato_open_data_akn"
        reader = CurrentSenatoCaptureBytes(
            pins,
            capture_store=Mock(find_capture=Mock(side_effect=[
                good, {**good, "hold_status": "RIGHTS_HOLD"},
            ])),
            body_store=Mock(read=Mock(return_value=raw)),
            private_source_guard=guard,
        )
        with self.assertRaisesRegex(ValueError, "CAPTURE_CHANGED_DURING_READ"):
            reader()
        guard = Mock(require=Mock(side_effect=RuntimeError("PRIVATE_RIGHTS_REVOKED")))
        guard.subject.source_family = "senato_open_data_akn"
        reader = CurrentSenatoCaptureBytes(
            pins, capture_store=Mock(find_capture=Mock(return_value=good)),
            body_store=Mock(read=Mock(return_value=raw)),
            private_source_guard=guard,
        )
        with self.assertRaisesRegex(RuntimeError, "PRIVATE_RIGHTS_REVOKED"):
            reader()

    def test_private_held_candidate_and_fake_approval_without_receipts_never_emits(self):
        raw, pins, canonical, record = setup()
        self.assertEqual(
            SenatoPublicV3Source(
                pins, read_original_bytes=lambda: raw,
                read_current_candidates=lambda: [record],
            ).projectable_public_statements(), [],
        )
        approved = {**record, "status": "APPROVED"}
        source = SenatoPublicV3Source(
            pins, read_original_bytes=lambda: raw,
            read_current_candidates=lambda: [approved],
        )
        prepared = source.projectable_public_statements()
        self.assertEqual(prepared[0]["original_text"], "Un dato: zero.")
        self.assertEqual(
            canonical[prepared[0]["locator"]["start_char"]:prepared[0]["locator"]["end_char"]],
            prepared[0]["original_text"],
        )
        self.assertEqual(prepared[0]["source_kind"], "WRITTEN")
        self.assertEqual(self.build(source)["statements"], [])
        # Even someone falsely calling the first five gates approved cannot
        # substitute for genuine autonomous packets or challenge state.
        supplied = SenatoPublicV3Source(
            pins, read_original_bytes=lambda: raw,
            read_current_candidates=lambda: [approved],
            read_current_attestations=lambda *_: {"rights": {"status": "APPROVED"}},
            read_current_challenge_hold=lambda *_: False,
        )
        self.assertEqual(self.build(supplied)["statements"], [])

    def test_source_revision_or_blob_mismatch_fails_before_candidate_emission(self):
        raw, pins, _, record = setup()
        for changed in (raw.replace(b"Un dato:", b"Due dati:"), b""):
            with self.subTest(changed=changed[:20]):
                source = SenatoPublicV3Source(
                    pins, read_original_bytes=lambda: changed,
                    read_current_candidates=lambda: [record],
                )
                with self.assertRaisesRegex(ValueError, "DP468_IMMUTABLE_XML_MISMATCH"):
                    source.projectable_public_statements()
        with self.assertRaisesRegex(ValueError, "SENATO_AKN_BLOB_MISMATCH"):
            SenatoPublicV3Source(
                replace(pins, git_blob_sha1="0" * 40),
                read_original_bytes=lambda: raw,
                read_current_candidates=lambda: [record],
            ).projectable_public_statements()
        with self.assertRaisesRegex(ValueError, "DP468_CANONICAL_TEXT_MISMATCH"):
            SenatoPublicV3Source(
                replace(pins, canonical_text_sha256="f" * 64),
                read_original_bytes=lambda: raw,
                read_current_candidates=lambda: [record],
            ).projectable_public_statements()

    def test_official_identity_span_version_and_duplicate_guards(self):
        raw, pins, _, record = setup()
        for change in (
            {"official_person_uri": "http://dati.senato.it/osr/Persona/9999"},
            {"start_char": record["end_char"]},
            {"source_version": "0" * 64},
            {"status": "HELD"},
            {"speech_id": "senato:other"},
            {"start_char": 0},
        ):
            with self.subTest(change=change):
                source = SenatoPublicV3Source(
                    pins, read_original_bytes=lambda: raw,
                    read_current_candidates=lambda: [{**record, "status": "APPROVED", **change}],
                )
                self.assertEqual(source.projectable_public_statements(), [])
        duplicate = {**record, "status": "APPROVED"}
        source = SenatoPublicV3Source(
            pins, read_original_bytes=lambda: raw,
            read_current_candidates=lambda: [duplicate, duplicate],
        )
        self.assertEqual(source.projectable_public_statements(), [])
        with self.assertRaisesRegex(ValueError, "SOURCE_VERSION_NOT_CURRENT"):
            source.get_statement_source_text(pins.content_id, "stale")

    def test_missing_unknown_challenge_cannot_pass_autonomous_gate(self):
        raw, pins, _, record = setup()
        adapter = SenatoPublicV3Source(
            pins, read_original_bytes=lambda: raw,
            read_current_candidates=lambda: [{**record, "status": "APPROVED"}],
        )
        self.assertIsNone(adapter.statement_publication_attestations("a", "b"))
        self.assertIsNone(adapter.autonomous_publication_evidence("a", "b"))
        self.assertIsNone(adapter.current_statement_challenge_hold("a", "b"))
        self.assertEqual(self.build(adapter)["statements"], [])


if __name__ == "__main__":
    unittest.main()
