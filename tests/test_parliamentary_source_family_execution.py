from __future__ import annotations

import copy
import sys
import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.parliamentary_amendment_revalidation import (  # noqa: E402
    evaluate_parliamentary_amendment,
)
from dichiarazioni_pubbliche.parliamentary_official_adapter import (  # noqa: E402
    normalize_parliamentary_official_record,
)
from dichiarazioni_pubbliche.parliamentary_source_family_execution import (  # noqa: E402
    ParliamentarySourceFamilyExecutionError,
    ParliamentarySourceFamilyManifest,
    ReviewedAmendmentInput,
    execute_parliamentary_source_family_fixture,
)
from dichiarazioni_pubbliche.policy.excerpt_policy import (  # noqa: E402
    EXCERPT_PUBLIC_USE_REQUIRED,
    ExcerptDisposition,
    ExcerptRequest,
    RightsStatus,
)
from tests.parliamentary_official_fixture import (  # noqa: E402
    parliamentary_official_fixture_records,
)


OLD_OBSERVED = datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc)
NEW_OBSERVED = datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc)


def camera_manifest(*, rights=RightsStatus.UNKNOWN, fixture_only=True):
    return ParliamentarySourceFamilyManifest(
        execution_ref="fixture:camera:2026-10-06",
        source_family="CAMERA_OFFICIAL",
        chamber="CAMERA",
        rights_status=rights,
        fixture_only=fixture_only,
    )


def senato_record():
    text = "Lucia Verdi: Il testo ufficiale è disponibile."
    statement = "Il testo ufficiale è disponibile."
    start = text.index(statement)
    return {
        "chamber": "SENATO",
        "sitting": {
            "id": "senato:sitting:2026-10-05:44",
            "date": "2026-10-05",
            "agenda_item_id": "senato:agenda:2026-10-05:bilancio",
            "agenda_label": "Discussione bilancio",
        },
        "speaker": {
            "id": "senato:senator:789",
            "name": "Lucia Verdi",
            "role": "Senatrice",
        },
        "statement": {
            "id": "senato:statement:2026-10-05:44:1",
            "speaker_id": "senato:senator:789",
            "date": "2026-10-05",
            "text": statement,
            "start_char": start,
            "end_char": start + len(statement),
        },
        "transcript": {
            "url": "https://www.senato.it/resoconto/44",
            "source_version": "senato-resoconto-44-v1",
            "text": text,
        },
        "video": {
            "url": "https://webtv.senato.it/evento/44",
            "source_version": "senato-webtv-44-v1",
            "start_ms": 30000,
            "end_ms": 36000,
        },
        "transcript_variant_refs": ["asr:senato-44:fixture"],
    }


def amendment_pair():
    previous = parliamentary_official_fixture_records()[0]
    current = copy.deepcopy(previous)
    current["statement"]["text"] = "Il valore comunicato è dieci."
    current["statement"]["start_char"] = 13
    current["statement"]["end_char"] = 42
    current["transcript"]["text"] = (
        "Mario Rossi: Il valore comunicato è dieci. Anna Bianchi: Chiedo la parola."
    )
    current["transcript"]["source_version"] = "camera-resoconto-101-v2-amended"
    return previous, current


def amendment_review(previous, current):
    decision = evaluate_parliamentary_amendment(
        previous=previous,
        current=current,
        previous_observed_at=OLD_OBSERVED,
        current_observed_at=NEW_OBSERVED,
        as_of=date(2026, 10, 6),
    )
    return ReviewedAmendmentInput(
        provider_id="camera-official-fixture",
        review_event_id="review:camera:statement:101:1:amendment-v2",
        review_action="APPROVED",
        reviewed_entity_ref=decision.event_key,
        previous_observed_at=OLD_OBSERVED,
        current_observed_at=NEW_OBSERVED,
        as_of=date(2026, 10, 6),
        previous_valid_from="2026-10-05",
        previous_valid_until="2026-10-06",
        current_valid_from="2026-10-06",
        current_valid_until=None,
        affected_claim_ids=("claim:parliament:1", "claim:parliament:2"),
        affected_finding_ids=("finding:parliament:1",),
    )


def excerpt_request(raw, *, caller_rights=RightsStatus.CLEARED):
    row = normalize_parliamentary_official_record(raw)
    assert row.video is not None
    return ExcerptRequest(
        excerpt_text=row.transcript.statement_text,
        rights_status=caller_rights,
        permitted_public_uses=(EXCERPT_PUBLIC_USE_REQUIRED,),
        rights_reviewed_on="2026-10-06",
        today="2026-10-06",
        source_url=row.transcript.source_url,
        content_id=row.record_id,
        segment_id=row.statement_id,
        transcript_variant_id=row.transcript.source_version,
        timestamp_start_seconds=row.video.start_ms / 1000,
        timestamp_end_seconds=row.video.end_ms / 1000,
        source_content_sha256=row.transcript.transcript_sha256,
        observed_source_sha256=row.transcript.transcript_sha256,
        excerpt_review_approved=True,
        profile_approved=True,
        max_excerpt_chars=200,
    )


class ParliamentarySourceFamilyExecutionTests(unittest.TestCase):
    def test_camera_batch_dedupes_exact_replay_and_is_deterministic(self):
        rows = parliamentary_official_fixture_records()
        execution = dict(
            manifest=camera_manifest(),
            current_records=[rows[0], copy.deepcopy(rows[0]), rows[1]],
        )
        first = execute_parliamentary_source_family_fixture(**execution)
        second = execute_parliamentary_source_family_fixture(**execution)

        self.assertEqual(first, second)
        self.assertEqual(first.record_count, 2)
        self.assertEqual(first.new_record_count, 2)
        self.assertEqual(first.replay_record_count, 0)
        self.assertEqual(first.amended_record_count, 0)
        self.assertRegex(first.receipt_sha256, r"^[0-9a-f]{64}$")
        self.assertEqual(
            {row.rights_status for row in first.records},
            {RightsStatus.UNKNOWN.value},
        )
        self.assertTrue(
            all(not row.public_excerpt_prerequisite_satisfied for row in first.records)
        )

    def test_previous_equal_current_is_replay_not_amendment(self):
        raw = parliamentary_official_fixture_records()[0]
        receipt = execute_parliamentary_source_family_fixture(
            manifest=camera_manifest(),
            previous_records=[raw],
            current_records=[copy.deepcopy(raw)],
        )
        self.assertEqual(receipt.record_count, 1)
        self.assertEqual(receipt.new_record_count, 0)
        self.assertEqual(receipt.replay_record_count, 1)
        self.assertEqual(receipt.amended_record_count, 0)
        self.assertEqual(receipt.records[0].state, "REPLAY")
        self.assertIsNone(receipt.records[0].reanalysis_request_id)

    def test_senato_source_family_executes_same_contract_offline(self):
        receipt = execute_parliamentary_source_family_fixture(
            manifest=ParliamentarySourceFamilyManifest(
                execution_ref="fixture:senato:2026-10-06",
                source_family="SENATO_OFFICIAL",
                chamber="SENATO",
            ),
            current_records=[senato_record()],
        )
        self.assertEqual(receipt.chamber, "SENATO")
        self.assertEqual(receipt.source_family, "SENATO_OFFICIAL")
        self.assertEqual(receipt.record_count, 1)
        self.assertEqual(receipt.records[0].state, "NEW")
        self.assertTrue(receipt.records[0].statement_id.startswith("senato:"))

    def test_execution_is_fixture_only_and_never_a_production_provider_path(self):
        with self.assertRaisesRegex(
            ParliamentarySourceFamilyExecutionError,
            "FIXTURE_ONLY_REQUIRED",
        ):
            execute_parliamentary_source_family_fixture(
                manifest=camera_manifest(fixture_only=False),
                current_records=parliamentary_official_fixture_records(),
            )

    def test_family_chamber_mismatch_fails_closed(self):
        with self.assertRaisesRegex(
            ParliamentarySourceFamilyExecutionError,
            "CHAMBER_MISMATCH",
        ):
            execute_parliamentary_source_family_fixture(
                manifest=ParliamentarySourceFamilyManifest(
                    execution_ref="fixture:mismatch",
                    source_family="CAMERA_OFFICIAL",
                    chamber="SENATO",
                ),
                current_records=[senato_record()],
            )

    def test_unknown_family_rights_cannot_be_upgraded_by_excerpt_request(self):
        raw = parliamentary_official_fixture_records()[0]
        row = normalize_parliamentary_official_record(raw)
        receipt = execute_parliamentary_source_family_fixture(
            manifest=camera_manifest(rights=RightsStatus.UNKNOWN),
            current_records=[raw],
            excerpt_requests={
                row.statement_id: excerpt_request(raw, caller_rights=RightsStatus.CLEARED)
            },
        )
        result = receipt.records[0]
        self.assertEqual(result.rights_status, RightsStatus.UNKNOWN.value)
        self.assertEqual(result.excerpt_disposition, ExcerptDisposition.PROHIBITED.value)
        self.assertIn("RIGHTS_NOT_CLEARED", result.excerpt_reason_codes)
        self.assertFalse(result.public_excerpt_prerequisite_satisfied)

    def test_explicit_synthetic_cleared_rights_still_use_dp305_exact_binding(self):
        raw = parliamentary_official_fixture_records()[0]
        row = normalize_parliamentary_official_record(raw)
        receipt = execute_parliamentary_source_family_fixture(
            manifest=camera_manifest(rights=RightsStatus.CLEARED),
            current_records=[raw],
            excerpt_requests={row.statement_id: excerpt_request(raw)},
        )
        self.assertTrue(receipt.records[0].public_excerpt_prerequisite_satisfied)

        bad = excerpt_request(raw)
        bad = copy.copy(bad)
        object.__setattr__(bad, "source_content_sha256", "0" * 64)
        with self.assertRaisesRegex(
            ParliamentarySourceFamilyExecutionError,
            "SOURCE_CONTENT_SHA256_MISMATCH",
        ):
            execute_parliamentary_source_family_fixture(
                manifest=camera_manifest(rights=RightsStatus.CLEARED),
                current_records=[raw],
                excerpt_requests={row.statement_id: bad},
            )

    def test_amended_record_requires_explicit_review_and_dp511_dp227_path(self):
        previous, current = amendment_pair()
        statement_id = previous["statement"]["id"]
        with self.assertRaisesRegex(
            ParliamentarySourceFamilyExecutionError,
            "AMENDMENT_REVIEW_REQUIRED",
        ):
            execute_parliamentary_source_family_fixture(
                manifest=camera_manifest(),
                previous_records=[previous],
                current_records=[current],
            )

        receipt = execute_parliamentary_source_family_fixture(
            manifest=camera_manifest(),
            previous_records=[previous],
            current_records=[current],
            reviewed_amendments={statement_id: amendment_review(previous, current)},
        )
        row = receipt.records[0]
        self.assertEqual(row.state, "AMENDED")
        self.assertEqual(receipt.amended_record_count, 1)
        self.assertIsNotNone(row.supersession_event_key)
        self.assertIsNotNone(row.hold_request_id)
        self.assertIsNotNone(row.reanalysis_request_id)
        self.assertFalse(row.public_excerpt_prerequisite_satisfied)

    def test_changed_amendment_review_target_fails_closed(self):
        previous, current = amendment_pair()
        statement_id = previous["statement"]["id"]
        review = amendment_review(previous, current)
        bad_review = replace(review, reviewed_entity_ref="0" * 64)
        with self.assertRaisesRegex(ValueError, "REVIEW_TARGET_MISMATCH"):
            execute_parliamentary_source_family_fixture(
                manifest=camera_manifest(),
                previous_records=[previous],
                current_records=[current],
                reviewed_amendments={statement_id: bad_review},
            )

    def test_receipt_exposes_no_publication_or_verdict_authority(self):
        receipt = execute_parliamentary_source_family_fixture(
            manifest=camera_manifest(),
            current_records=[parliamentary_official_fixture_records()[0]],
        )
        forbidden = {
            "publication_status",
            "publication_authorized",
            "publish",
            "approved",
            "verdict",
            "assessment",
        }
        self.assertTrue(forbidden.isdisjoint(receipt.__dataclass_fields__))
        self.assertTrue(forbidden.isdisjoint(receipt.records[0].__dataclass_fields__))


if __name__ == "__main__":
    unittest.main()
