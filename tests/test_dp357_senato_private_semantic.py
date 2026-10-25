"""DP-357: public canary seam for bounded private semantic use of a real Capture."""
import hashlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "poc"))

import dp357_senato_private_semantic as canary
from dichiarazioni_pubbliche.private_capture_rights import SourceUseBlocked
from dichiarazioni_pubbliche.private_semantic_matching import hints_from_vectors
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)


def sample_xml():
    return (f'<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03">'
            f'<FRBRdate name="presentazione" date="2025-05-29"/>'
            f'<speech by="#p32600"><p>{canary.EXPECTED_TEXT}</p></speech>'
            f'</akomaNtoso>').encode()


def current_rights():
    return SimpleNamespace(
        id="private-rights:original", policy_version=canary.DP330_PRIVATE_CAPTURE_POLICY,
        rights_status="CLEARED", rights_receipt_ref=canary.RIGHTS_RECEIPT,
        permitted_uses=tuple(canary.DP330_PRIVATE_CAPTURE_USES),
        attribution_requirements=("ATTRIBUTION_REQUIRED",),
        expires_at=(datetime.now(timezone.utc) + timedelta(days=4)).isoformat(),
    )


class SenatoSemanticCanaryTests(unittest.TestCase):
    def test_real_source_bound_to_hash_date_speaker_and_all_adversarial_holds(self):
        body = sample_xml()
        with patch.object(canary, "BODY_SHA256", hashlib.sha256(body).hexdigest()):
            source, variants = canary._case_from_capture(
                body, canary.EXPECTED_CAPTURE, "content:licensed"
            )
            self.assertEqual(source.proposition.normalized_text, canary.EXPECTED_TEXT)
            self.assertEqual(source.proposition.entity_keys, ("akn:speech:#p32600",))
            self.assertEqual(len(variants), 6)
            # Maximal model similarity never defeats negation, quoted source,
            # uncertain speaker, date or claim-type conflicts.
            embeddings = [[1.0, 0.0]] * (len(variants) + 1)
            hints = hints_from_vectors(source, variants, embeddings)
            self.assertEqual({hint.target_id for hint in hints} - {
                "synthetic:dp357:paraphrase"
            }, set())
            self.assertTrue(all(h.disposition == "HOLD" for h in hints))
            with self.assertRaisesRegex(ValueError, "CAPTURE_HASH_OR_ID_MISMATCH"):
                canary._case_from_capture(body + b"x", canary.EXPECTED_CAPTURE,
                                          "content:licensed")
            invalid = body.replace(b"#p32600", b"#p99999")
            with patch.object(canary, "BODY_SHA256", hashlib.sha256(invalid).hexdigest()):
                with self.assertRaisesRegex(ValueError, "SOURCE_PASSAGE_OR_DATE_UNVERIFIED"):
                    canary._case_from_capture(invalid, canary.EXPECTED_CAPTURE,
                                              "content:licensed")

    def test_missing_parse_right_blocks_before_body_read_or_model(self):
        subject = RightsSubject(
            source_family=canary.SOURCE_FAMILY, locator_kind="URL",
            locator_value=canary.CURRENT_URL, content_id="content:licensed",
        )
        previous = current_rights()
        stale = PrivateRightsRecord(
            id=previous.id, subject_fingerprint=rights_subject_fingerprint(subject),
            source_family=subject.source_family, locator_kind=subject.locator_kind,
            locator_value=subject.locator_value, content_id=subject.content_id,
            evidence_id=None, transcript_segment_id=None, canonical_segment_id=None,
            passage_id=None, rights_status="CLEARED",
            rights_receipt_ref=previous.rights_receipt_ref,
            permitted_uses=previous.permitted_uses,
            attribution_requirements=previous.attribution_requirements,
            reviewed_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            expires_at=previous.expires_at,
            reviewer_ref=canary.REVIEWER_REF, policy_version=previous.policy_version,
            record_visibility="PRIVATE", supersedes_id=None, version_state="CURRENT",
        )
        store = SimpleNamespace(find_capture=lambda *_: self.fail("capture read before use"))
        rights = SimpleNamespace(read_current=lambda _: stale)
        with patch.object(canary, "CapturePipelineStore", return_value=store), patch.object(
            canary, "_context", return_value={"id": "content:licensed"}
        ), patch.object(canary, "PrivateRightsRegistryStore", return_value=rights), patch.object(
            canary, "run_private_semantic_matching", side_effect=AssertionError("model invoked")
        ):
            # The actual SourceFamilyUseGuard checks the actual current record.
            with self.assertRaises(SourceUseBlocked):
                canary.run("private-db", Path("/no-file"))

    def test_grant_is_exact_append_only_and_rejects_unrelated_rights(self):
        original = current_rights()
        subject = SimpleNamespace()
        hit = SimpleNamespace(
            canonical_url=canary.CURRENT_URL,
            metadata={"commit": canary.CURRENT_COMMIT,
                      "blob_sha1": canary.CONTENT_BLOB_SHA1,
                      "license_id": "CC-BY-4.0",
                      "license_notice_sha256": canary.RIGHTS_RECEIPT.rsplit(":", 1)[-1]},
        )
        writes = []
        rights = SimpleNamespace(record_rights=lambda **kw: writes.append(kw) or
                                 replace_placeholder(kw))
        with patch.object(canary, "official_verified_hit", return_value=hit):
            accepted = canary._authorize_parse(rights, subject, original)
        self.assertIn("PARSE_TEXT", accepted.permitted_uses)
        self.assertEqual(writes[0]["supersedes_record_id"], original.id)
        self.assertEqual(writes[0]["expires_at"], original.expires_at)
        self.assertNotIn("EXCERPT_PUBLIC", accepted.permitted_uses)
        canary._authorize_parse(rights, subject, accepted)
        self.assertEqual(len(writes), 1)
        with self.assertRaisesRegex(SourceUseBlocked, "SCOPE_CONFLICT"):
            canary._authorize_parse(rights, subject, replace_namespace(
                original, permitted_uses=("FETCH", "EXCERPT_PUBLIC")))
        with patch.object(canary, "official_verified_hit", return_value=SimpleNamespace(
            canonical_url="https://unrelated.invalid", metadata=hit.metadata
        )):
            with self.assertRaisesRegex(SourceUseBlocked, "OFFICIAL_LICENSE_UNVERIFIED"):
                canary._authorize_parse(rights, subject, original)


def replace_placeholder(kwargs):
    return SimpleNamespace(
        id="private-rights:new",
        policy_version=kwargs["policy_version"],
        rights_status=kwargs["rights_status"],
        rights_receipt_ref=kwargs["rights_receipt_ref"],
        permitted_uses=kwargs["permitted_uses"],
        attribution_requirements=kwargs["attribution_requirements"],
        expires_at=kwargs["expires_at"],
    )


def replace_namespace(obj, **values):
    return SimpleNamespace(**(vars(obj) | values))
