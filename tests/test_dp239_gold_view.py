"""DP-239 local controls only: no externally certified translation gold."""

from __future__ import annotations

import hashlib
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.multilingual_derivation import (  # noqa: E402
    ActorAnchor, ImmutableOriginalReadback, build_private_translation,
)
from dichiarazioni_pubbliche.multilingual_gold import (  # noqa: E402
    TranslationGoldCase, TranslationGoldManifest, TranslationRiskPrediction,
    evaluate_translation_gold, manifest_hash,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard  # noqa: E402
from dichiarazioni_pubbliche.private_multilingual_view import read_private_multilingual_view  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)
from dichiarazioni_pubbliche.wording_contract import WordingType  # noqa: E402
from tests.test_dp239_multilingual_derivation import written_fixture  # noqa: E402


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_rights(row, *, permitted=("FETCH", "STORE_BODY", "PARSE_TEXT", "TRANSLATE"),
                  rights_status="CLEARED"):
    capture = row["capture"]
    subject = RightsSubject(
        source_family="SYNTHETIC_PRIVATE_CONTROL", locator_kind="URL",
        locator_value=capture.final_url, content_id=capture.content_id,
    )
    record = PrivateRightsRecord(
        id="rights:synthetic-reviewed", subject_fingerprint=rights_subject_fingerprint(subject),
        source_family=subject.source_family, locator_kind=subject.locator_kind,
        locator_value=subject.locator_value, content_id=subject.content_id,
        evidence_id=None, transcript_segment_id=None, canonical_segment_id=None,
        passage_id=None, rights_status=rights_status,
        rights_receipt_ref="synthetic:test-only", permitted_uses=permitted,
        attribution_requirements=(), reviewed_at="2026-10-01T00:00:00+00:00",
        expires_at="2027-10-01T00:00:00+00:00", reviewer_ref="synthetic:operator",
        policy_version="control-v1", record_visibility="PRIVATE",
        supersedes_id=None, version_state="CURRENT",
    )
    guard = SourceFamilyUseGuard(
        read_current=lambda _: record, subject=subject,
        rights_record_id=record.id, policy_version=record.policy_version,
        expected_sha256=capture.content_sha256,
        clock=lambda: datetime(2026, 10, 20, tzinfo=timezone.utc),
    )
    return guard


def private_records(row):
    return {
        row["passage"].id: ImmutableOriginalReadback(
            locator=row["locator"], passage=row["passage"], capture=row["capture"],
            source_body=row["source_body"], canonical_text=row["canonical_text"],
        ),
    }


def gold_case(case_id, draft, *, alerts=(), state="FAITHFUL", reported_author=None,
              endorsement="UNKNOWN"):
    return TranslationGoldCase(
        case_id=case_id, passage_id=draft.original.passage_id,
        original_quote_sha256=draft.original.quote_sha256,
        source_version_sha256=draft.original.source_version_sha256,
        translation_sha256=draft.translated_text_sha256,
        original_language=draft.original.language,
        target_language=draft.target_language,
        original_wording_type=draft.original.source_wording_type,
        expected_alerts=tuple(alerts), semantic_state=state,
        speaker_person_id=draft.original.speaker_person_id,
        reported_author_id=reported_author, endorsement=endorsement,
        source_rights_receipt_sha256=sha("synthetic-rights-not-a-license"),
        adjudication_receipt_sha256=sha("synthetic-gold-not-adjudicated"),
        annotator_ids=("synthetic:annotator-a", "synthetic:annotator-b"),
        adjudicator_id="synthetic:adjudicator", reference_version="controls-v1",
    )


def manifest(*cases):
    provisional = TranslationGoldManifest(
        generator_id="test-author", model_id="synthetic-provider",
        cases=tuple(cases), manifest_sha256=sha("placeholder"),
    )
    return replace(provisional, manifest_sha256=manifest_hash(provisional))


class PrivateMultilingualViewTests(unittest.TestCase):
    def test_private_source_always_visible_original_independent_and_versioned_italian(self):
        row = written_fixture()
        originals = private_records(row)
        versions = {row["capture"].content_id: row["capture"].content_sha256}
        common = dict(
            originals_by_passage=originals, current_versions_by_content=versions,
            rights_guard=source_rights(row),
        )
        original = read_private_multilingual_view(row["passage"].id, **common)
        first = build_private_translation(**row)
        translated = read_private_multilingual_view(row["passage"].id, translation=first, **common)
        self.assertEqual(original.status, "CURRENT_ORIGINAL")
        self.assertIsNone(original.translated_text)
        self.assertEqual(translated.status, "CURRENT_HELD")
        self.assertEqual(translated.source_url, row["capture"].final_url)
        self.assertEqual(translated.original_text, original.original_text)
        self.assertEqual(translated.original_quote_sha256, original.original_quote_sha256)
        self.assertEqual(translated.original_language, "de-Latn-DE")
        self.assertEqual(translated.translated_language, "it-IT")
        self.assertEqual(translated.translation_method, "MACHINE")
        self.assertFalse(translated.translation_reviewed)
        self.assertFalse(translated.public_quote_eligible)
        second = build_private_translation(**{**row, "translated_text": "Anna muss vedere Bruno il 10/11/2026."})
        changed = read_private_multilingual_view(row["passage"].id, translation=second, **common)
        self.assertNotEqual(changed.translation_id, translated.translation_id)
        self.assertEqual(changed.original_quote_sha256, translated.original_quote_sha256)

    def test_rights_replacement_missing_permission_staleness_and_tampering_fail_closed(self):
        row = written_fixture()
        draft = build_private_translation(**row)
        originals = private_records(row)
        current = {row["capture"].content_id: row["capture"].content_sha256}

        def read(guard, *, records=originals, versions=current):
            return read_private_multilingual_view(
                row["passage"].id, originals_by_passage=records,
                current_versions_by_content=versions,
                rights_guard=guard, translation=draft,
            )

        self.assertEqual(read(source_rights(row, rights_status="REVOKED")).status, "BLOCKED")
        self.assertEqual(read(source_rights(row, permitted=("STORE_BODY", "PARSE_TEXT"))).status, "BLOCKED")
        missing_guard = read_private_multilingual_view(
            row["passage"].id, originals_by_passage=originals,
            current_versions_by_content=current, rights_guard=None, translation=draft,
        )
        self.assertEqual(missing_guard.status, "BLOCKED")
        self.assertIsNone(missing_guard.original_text)
        stale = read(source_rights(row), versions={row["capture"].content_id: sha("new")})
        self.assertEqual(stale.status, "STALE")
        self.assertIsNone(stale.translated_text)
        moved = replace(originals[row["passage"].id],
                        capture=replace(row["capture"], final_url="https://example.test/unreviewed"))
        blocked = read(source_rights(row), records={row["passage"].id: moved})
        self.assertEqual(blocked.status, "BLOCKED")
        self.assertIsNone(blocked.original_text)
        corrupted = read_private_multilingual_view(
            row["passage"].id, originals_by_passage=originals,
            current_versions_by_content=current, rights_guard=source_rights(row),
            translation=replace(draft, translated_text="forged"),
        )
        self.assertEqual(corrupted.status, "BLOCKED")
        self.assertIsNone(corrupted.original_text)


class TranslationGoldTests(unittest.TestCase):
    def test_synthetic_de_and_it_controls_need_external_adjudication(self):
        rows = []
        for case_id, de, it, flags, reported in (
            ("negation", "Anna hat nicht zugestimmt.", "Anna ha acconsentito.", ("NEGATION_MISMATCH",), False),
            ("modality", "Anna muss gehen.", "Anna può andare.", ("MODALITY_MISMATCH",), False),
            ("reported", "Anna sagte: „Bruno kommt.“", "Anna ha detto: «Bruno arriva.»",
             ("QUOTED_SPEAKER_ENDORSEMENT_UNVERIFIED",), True),
        ):
            row = written_fixture(de)
            row["translated_text"] = it
            row["actor_anchors"] = tuple(ActorAnchor("person:" + name.lower(), name)
                                         for name in ("Anna", "Bruno") if name in de)
            if reported:
                row["source_wording_type"] = WordingType.REPORTED_QUOTE
            rows.append((case_id, build_private_translation(**row), flags, reported))
        italian = written_fixture("Anna non sostiene la misura.")
        italian["source_language"] = "it-IT"
        italian["passage"] = replace(italian["passage"], language="it-IT")
        italian["translated_text"] = "Anna non sostiene la misura."
        italian["actor_anchors"] = (ActorAnchor("person:anna", "Anna"),)
        rows.append(("it-original", build_private_translation(**italian), (), False))
        cases = tuple(gold_case(case_id, draft, alerts=flags,
                                state="UNRESOLVED" if reported else "MISMATCH" if flags else "FAITHFUL",
                                reported_author="person:bruno" if reported else None,
                                endorsement="NOT_ENDORSED" if reported else "UNKNOWN")
                      for case_id, draft, flags, reported in rows)
        predictions = tuple(TranslationRiskPrediction(case_id, draft) for case_id, draft, _, _ in rows)
        spec = manifest(*cases)
        unverified = evaluate_translation_gold(spec, predictions)
        self.assertEqual(unverified.status, "BLOCKED_EXTERNAL_GOLD")
        self.assertEqual(unverified.unverified_gold_cases, 4)
        self.assertIsNone(unverified.risk_alert_recall)
        self.assertEqual(unverified.detected_critical_alerts, 0)
        control = evaluate_translation_gold(spec, predictions, external_attestation_check=lambda _: True)
        self.assertEqual(control.status, "CONTRACT_ONLY_PRIVATE_HOLD")
        self.assertEqual(control.risk_alert_recall, 1.0)
        self.assertEqual(control.detected_critical_alerts, 3)
        self.assertEqual(control.missed_critical_alerts, 0)
        self.assertFalse(control.release_eligible)
        self.assertFalse(control.publication_authority)

        # The regression evaluator detects missing critical warnings and
        # a reported speaker incorrectly interpreted as endorsing the quote.
        changed = list(predictions)
        changed[0] = replace(changed[0], translation=replace(
            changed[0].translation, signal_codes=(),
        ))
        changed[2] = replace(changed[2], predicted_endorsement="ENDORSED",
                             attributed_reported_author_id="person:anna")
        adversarial = evaluate_translation_gold(spec, tuple(changed), external_attestation_check=lambda _: True)
        self.assertEqual(adversarial.missed_critical_alerts, 1)
        self.assertEqual(adversarial.false_endorsements, 1)
        self.assertEqual(adversarial.wrong_speakers, 1)

    def test_case_hash_replay_independence_and_unknown_predictions_fail_closed(self):
        draft = build_private_translation(**written_fixture())
        case = gold_case("case", draft)
        spec = manifest(case)
        with self.assertRaisesRegex(ValueError, "MANIFEST_INVALID"):
            evaluate_translation_gold(replace(spec, manifest_sha256=sha("altered")), ())
        with self.assertRaisesRegex(ValueError, "INDEPENDENCE_CONFLICT"):
            bad = replace(case, adjudicator_id="synthetic:annotator-a")
            evaluate_translation_gold(manifest(bad), ())
        with self.assertRaisesRegex(ValueError, "PREDICTION_INVALID"):
            evaluate_translation_gold(spec, (TranslationRiskPrediction("foreign", draft),))
        wrong_hash = manifest(replace(case, source_version_sha256=sha("changed source")))
        bad_binding = evaluate_translation_gold(
            wrong_hash, (TranslationRiskPrediction("case", draft),),
            external_attestation_check=lambda _: True,
        )
        self.assertEqual(bad_binding.mismatched_bindings, 1)
        self.assertFalse(bad_binding.publication_authority)


if __name__ == "__main__":
    unittest.main()
