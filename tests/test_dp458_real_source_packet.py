"""DP-458: protect verified EU AVS cue minute and private-only scope."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)
from tools import dp458_real_source_packet as packet
from tools import dp458_current_private_terms as current_terms


class DP458RealSourcePacketTests(unittest.TestCase):
    @staticmethod
    def expired_private_rights():
        subject = RightsSubject(packet.FAMILY, "URL", packet.URL,
                                content_id=packet.CONTENT)
        return PrivateRightsRecord(
            id="private-rights:expired",
            subject_fingerprint=rights_subject_fingerprint(subject),
            source_family=packet.FAMILY, locator_kind="URL",
            locator_value=packet.URL, content_id=packet.CONTENT,
            evidence_id=None, transcript_segment_id=None,
            canonical_segment_id=None, passage_id=None,
            rights_status="CLEARED", rights_receipt_ref="receipt:old",
            permitted_uses=tuple(sorted(packet.USES)),
            attribution_requirements=("NO_PUBLIC_MEDIA", "PUBLIC_QUOTE_REVIEW_REQUIRED"),
            reviewed_at="2026-10-26T12:00:00+00:00",
            expires_at="2026-11-02T12:00:00+00:00",
            reviewer_ref="agent:old", policy_version=packet.POLICY,
            record_visibility="PRIVATE", supersedes_id=None,
            version_state="CURRENT",
        )

    @staticmethod
    def official_page(url, *, valid=True, **_kwargs):
        if url == packet.PAGE:
            body = f"I-293056 European Parliament {packet.QUOTE}".encode()
        else:
            body = (
                "Creative Commons Attribution 4.0 International License; "
                "identifiable private individuals; third parties; "
                "Any reuse must not distort"
            ).encode() if valid else b"Unknown terms"
        return SimpleNamespace(
            status_code=200, final_url=url, media_type="text/html", body=body,
        )

    def test_expired_private_rights_refresh_supersedes_current_without_public_use(self):
        old = self.expired_private_rights()
        now = datetime.now(timezone.utc)
        store = Mock()
        store.read_current.return_value = old
        store.record_rights.return_value = replace(
            old, id="private-rights:renewed",
            reviewed_at=now.isoformat(),
            expires_at=(now + timedelta(days=7)).isoformat(),
            supersedes_id=old.id,
        )
        with patch.object(packet, "PrivateRightsRegistryStore", return_value=store):
            with patch.object(current_terms, "fetch_bytes", side_effect=self.official_page) as fetch:
                _, _, saved = packet.rights(
                    SimpleNamespace(database_url="test"), False, refresh_private=True,
                )
        self.assertEqual(saved.id, "private-rights:renewed")
        self.assertEqual(fetch.call_count, 2)
        kwargs = store.record_rights.call_args.kwargs
        self.assertEqual(kwargs["supersedes_record_id"], old.id)
        self.assertEqual(set(kwargs["permitted_uses"]), set(packet.USES))
        self.assertNotIn("EXCERPT_PUBLIC", kwargs["permitted_uses"])
        self.assertEqual(kwargs["rights_status"], "CLEARED")
        self.assertTrue(kwargs["rights_receipt_ref"].startswith(
            "eu-avs:I-293056:current-private:"
        ))

    def test_refresh_rejects_official_terms_drift_before_registry_write(self):
        store = Mock()
        store.read_current.return_value = self.expired_private_rights()
        with patch.object(packet, "PrivateRightsRegistryStore", return_value=store):
            with patch.object(current_terms, "fetch_bytes", side_effect=lambda url, **kw:
                              self.official_page(url, valid=False)):
                with self.assertRaisesRegex(RuntimeError, "RIGHTS_OFFICIAL_EVIDENCE_CHANGED"):
                    packet.rights(
                        SimpleNamespace(database_url="test"), False, refresh_private=True,
                    )
        store.record_rights.assert_not_called()

    def test_first_private_grant_also_checks_current_official_source(self):
        now = datetime.now(timezone.utc)
        new = replace(
            self.expired_private_rights(), id="private-rights:first",
            reviewed_at=now.isoformat(),
            expires_at=(now + timedelta(days=7)).isoformat(),
        )
        store = Mock()
        store.read_current.return_value = None
        store.record_rights.return_value = new
        with patch.object(packet, "PrivateRightsRegistryStore", return_value=store):
            with patch.object(current_terms, "fetch_bytes", side_effect=self.official_page):
                packet.rights(SimpleNamespace(database_url="test"), True)
        self.assertTrue(store.record_rights.called)
        self.assertIn("current-private:",
                      store.record_rights.call_args.kwargs["rights_receipt_ref"])
        self.assertNotIn("EXCERPT_PUBLIC",
                         store.record_rights.call_args.kwargs["permitted_uses"])

    def test_cue_12_preserves_hours_minutes_seconds(self):
        self.assertEqual(packet.vtt_timestamp_ms("00:01:14.669"), 74669)
        self.assertEqual(packet.vtt_timestamp_ms("00:01:18.940"), 78940)
        self.assertEqual((packet.START, packet.END), (74669, 78940))
        self.assertEqual(packet.END - packet.START, 4271)
        self.assertEqual(packet.VERSION, "dp458-original-source-v2")

    def test_old_seconds_only_extraction_does_not_match_real_cue(self):
        self.assertNotEqual(packet.START, 14669)
        self.assertNotEqual(packet.END, 18940)
        self.assertEqual(packet.vtt_timestamp_ms("00:00:14.669"), 14669)

    def test_invalid_cue_formats_are_not_silently_accepted(self):
        for bad in ("01:14.669", "00:61:14.669", "00:01:61.000",
                    "00:01:14", "-00:01:14.669", "00:01:14.66"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                packet.vtt_timestamp_ms(bad)

    def test_private_use_and_source_revision_are_pinned(self):
        self.assertEqual(packet.CANDIDATE, "statement:dp458:I-293056:cue12")
        self.assertEqual(packet.CANONICAL, "canonical:dp458:I-293056:cue12")
        self.assertEqual(
            packet.ORIGINAL_SHA,
            "225b145412687af1ac0fa7a5f03a010541fcf8cd81be3494418f59614ec57593",
        )
        self.assertEqual(
            packet.VTT_SHA,
            "2de8e201c68ede5735330bfa9f48b87da0ebdddca679f71ffd6be3d0aa58c2de",
        )
        self.assertEqual(packet.sha(packet.QUOTE),
                         "5678722cae3853f90810d5825d8b5a1f1b17592245a3650b179ff67afd840a96")
        self.assertIn("PLAYBACK", packet.USES)
        self.assertIn("ASR_MEDIA", packet.USES)
        self.assertNotIn("EXCERPT_PUBLIC", packet.USES)



    def test_full_persisted_chain_rejects_any_text_or_speaker_drift(self):
        row = {
            "quote": packet.QUOTE, "sha": packet.sha(packet.QUOTE),
            "start": packet.START, "end": packet.END,
            "raw_start": packet.START, "raw_end": packet.END,
            "candidate_version": packet.VERSION,
            "status": "TRANSCRIPT_UNCERTAIN", "blocked": True,
            "candidate_status": "HELD",
            "raw_text": packet.QUOTE, "canonical_text": packet.QUOTE,
            "speaker_id": packet.PERSON, "variant_text": packet.QUOTE,
            "variant_sha": packet.sha(packet.QUOTE),
            "variant_vtt_sha": packet.VTT_SHA,
        }
        packet.verify_source_chain(row)
        for field, bad in (
            ("raw_text", "Not the publisher cue"),
            ("canonical_text", "Not the publisher cue"),
            ("speaker_id", "person:wrong-speaker"),
            ("variant_text", "Tampered source caption"),
            ("variant_sha", "0" * 64),
            ("variant_vtt_sha", "0" * 64),
            ("start", 14669), ("blocked", False),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(
                RuntimeError, "DP458_STATEMENT_READBACK_FAILED"
            ):
                packet.verify_source_chain({**row, field: bad})

    def test_real_vtt_bytes_hash_and_cue_must_match(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from tools.dp458_cue_correction import CAPTION_NAME, pinned_caption
        raw = (
            "WEBVTT\\n\\n12\\n00:01:14.669 --> 00:01:18.940\\n"
            + packet.QUOTE + "\\n"
        ).replace("\\n", "\n").encode()
        with tempfile.TemporaryDirectory() as temporary:
            location = Path(temporary) / CAPTION_NAME
            location.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            pinned_caption(Path(temporary), expected_sha=digest,
                           expected_start=packet.START, expected_end=packet.END,
                           exact_quote=packet.QUOTE)
            for kwargs in (
                {"expected_sha": "0" * 64},
                {"expected_start": 14669},
                {"exact_quote": "Another transcript"},
            ):
                options = dict(expected_sha=digest, expected_start=packet.START,
                               expected_end=packet.END, exact_quote=packet.QUOTE)
                options.update(kwargs)
                with self.assertRaises(RuntimeError):
                    pinned_caption(Path(temporary), **options)
            location.write_bytes(raw.replace(b"more", b"less"))
            with self.assertRaisesRegex(RuntimeError, "DP458_VTT_VERSION_CHANGED"):
                pinned_caption(Path(temporary), expected_sha=digest,
                               expected_start=packet.START, expected_end=packet.END,
                               exact_quote=packet.QUOTE)

    def test_cas_updates_both_timestamps_in_one_postgres_statement(self):
        import json
        from tools.dp458_cue_correction import correct_persisted_cue
        class FakeStore:
            commands = []
            def run(self, sql, **params):
                self.commands.append(sql)
                if "SELECT json_build_object" in sql:
                    return json.dumps({
                        "hash": packet.sha(packet.QUOTE), "candidate_status": "HELD",
                        "transcript": "TRANSCRIPT_UNCERTAIN", "blocked": True,
                        "binding_count": 0, "start": 14669, "end": 18940,
                        "raw_start": 14669, "raw_end": 18940,
                    })
                return ""
        store=FakeStore()
        correct_persisted_cue(
            store, canonical=packet.CANONICAL, segment=packet.SEGMENT,
            candidate=packet.CANDIDATE, passage=packet.PASSAGE,
            exact_quote_sha=packet.sha(packet.QUOTE),
            start=packet.START, end=packet.END, vtt_sha=packet.VTT_SHA,
            version=packet.VERSION,
        )
        atomic = [sql for sql in store.commands if "DO $dp458$" in sql]
        self.assertEqual(len(atomic), 1)
        self.assertIn("UPDATE canonical_transcript_segment", atomic[0])
        self.assertIn("UPDATE transcript_segment", atomic[0])
        self.assertIn("RAISE EXCEPTION 'DP458_VTT_TIMING_CAS_FAILED'", atomic[0])
        self.assertFalse(any(
            "UPDATE canonical_transcript_segment" in sql and "DO $dp458$" not in sql
            for sql in store.commands
        ))

if __name__ == "__main__":
    unittest.main()
