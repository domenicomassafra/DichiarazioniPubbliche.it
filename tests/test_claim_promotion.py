import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.claim_promotion import (  # noqa: E402
    PROMOTION_CONTEXT_SQL_V1,
    PROMOTION_VERSION,
    PromotionRequest,
    _LINK_EXISTING_SQL,
    _PROMOTE_MEDIA_NEW_SQL,
    _PROMOTE_WRITTEN_NEW_SQL,
    deterministic_promoted_claim_id,
    deterministic_promotion_id,
    deterministic_promotion_key,
    promote_claim_candidate,
)
from dichiarazioni_pubbliche.wording_contract import (  # noqa: E402
    WordingType,
    make_summary_wording,
    make_translation_wording,
    wording_contract_metadata,
)


class FakePromotionStore:
    def __init__(self, context, *, link_state="LINKED_EXISTING", written_state="CREATED", media_state="CREATED"):
        self._context = context
        self.link_state = link_state
        self.written_state = written_state
        self.media_state = media_state
        self.calls = []

    def context(self, candidate_id):
        self.calls.append(("context", candidate_id))
        return copy.deepcopy(self._context)

    def link_existing(self, **variables):
        self.calls.append(("link_existing", variables))
        return self.link_state

    def create_written(self, **variables):
        self.calls.append(("create_written", variables))
        return self.written_state

    def create_media(self, **variables):
        self.calls.append(("create_media", variables))
        return self.media_state


def written_context():
    exact_quote = "I test sull'impronta 33 diedero esito negativo."
    exact_hash = hashlib.sha256(exact_quote.encode("utf-8")).hexdigest()
    return {
        "candidate_id": "candidate:1",
        "candidate_status": "CANDIDATE",
        "content_id": "content:1",
        "normalized_claim": exact_quote,
        "proposed_claim_type": "HISTORICAL_CLAIM",
        "claim_type_version": "atomic-claim-v1",
        "temporal_scope": {"statement_date": "2025-05-21"},
        "check_worthy": True,
        "extraction_model": "test-model",
        "extraction_version": "claim-candidate-v1",
        "candidate_metadata": {
            "test": True,
            "speech_mode": "DIRECT_UTTERANCE",
            "context_integrity": {
                "state": "CLEAR_AUTOMATIC",
                "version": "context-integrity-v1",
            },
            "wording": wording_contract_metadata(
                occurrence_id="statement:1",
                source_text_sha256=exact_hash,
                normalized_claim=exact_quote,
                language="it",
                derivation_version="claim-candidate-v1",
            ),
        },
        "promoted_claim_id": None,
        "statement_candidate_id": "statement:1",
        "statement_status": "APPROVED",
        "statement_reviewed": True,
        "claim_candidate_reviewed": True,
        "speaker_person_id": "person:1",
        "speaker_is_public": True,
        "statement_text_hash": exact_hash,
        "statement_at": "2025-05-21T12:00:00+02:00",
        "attribution_method": "SOURCE_QUOTE",
        "canonical_url": "https://example.test/article",
        "title": "Article",
        "published_at": "2025-05-21T10:00:00+00:00",
        "passage_count": 1,
        "written_count": 1,
        "media_count": 0,
        "passages": [
            {
                "passage_id": "passage:1",
                "selector_type": "TEXT_POSITION",
                "start_char": 10,
                "end_char": 10 + len(exact_quote),
                "page_start": None,
                "page_end": None,
                "text_sha256": exact_hash,
                "private_text": exact_quote,
                "capture_id": "capture:1",
                "capture_sha256": "c" * 64,
                "capture_final_url": "https://example.test/article",
                "capture_status": "CAPTURED",
                "capture_hold_status": "NONE",
                "canonical_segment_id": None,
                "segment_status": None,
                "segment_publication_blocked": None,
                "segment_speaker_person_id": None,
            }
        ],
        "duplicate_target_ids": [],
        "existing_promotion": None,
    }


def media_context():
    raw = written_context()
    exact_quote = "I test sull'impronta 33 diedero esito negativo."
    prefix = "Nel servizio viene dichiarato: "
    canonical_text = prefix + exact_quote + " Fine intervento."
    quote_start = len(prefix)
    quote_end = quote_start + len(exact_quote)
    raw["written_count"] = 0
    raw["media_count"] = 1
    raw["statement_metadata"] = {
        "quote_local_start_char": quote_start,
        "quote_local_end_char": quote_end,
    }
    raw["candidate_metadata"]["context_integrity"].update(
        {
            "quote_start": quote_start,
            "quote_end": quote_end,
            "quote_sha256": raw["statement_text_hash"],
        }
    )
    raw["passages"] = [
        {
            "passage_id": "passage:media:1",
            "selector_type": "MEDIA_SEGMENT_REF",
            "start_char": None,
            "end_char": None,
            "page_start": None,
            "page_end": None,
            "text_sha256": hashlib.sha256(canonical_text.encode("utf-8")).hexdigest(),
            "private_text": None,
            "capture_id": None,
            "capture_sha256": None,
            "capture_final_url": None,
            "capture_status": None,
            "capture_hold_status": None,
            "canonical_segment_id": "canonical-segment:1",
            "segment_canonical_text": canonical_text,
            "segment_status": "RESOLVED",
            "segment_publication_blocked": False,
            "segment_speaker_person_id": "person:1",
            "segment_verbatim_method": "OFFICIAL_TRANSCRIPT",
            "segment_speaker_provenance_ok": True,
        }
    ]
    return raw


class ClaimPromotionTests(unittest.TestCase):
    def request(self, channel="WRITTEN"):
        return PromotionRequest(
            candidate_id="candidate:1",
            provenance_channel=channel,
            actor_ref="reviewer:1",
            reason="promotion checked",
        )

    def test_ids_are_deterministic_and_versioned(self):
        self.assertEqual(deterministic_promotion_id("candidate:1"), deterministic_promotion_id("candidate:1"))
        self.assertEqual(deterministic_promotion_key("candidate:1", "WRITTEN"), deterministic_promotion_key("candidate:1", "WRITTEN"))
        claim_id = deterministic_promoted_claim_id("candidate:1")
        self.assertTrue(claim_id.startswith("claim:promoted:"))
        self.assertEqual(PROMOTION_VERSION, "claim-candidate-promotion-v1")

    def test_written_candidate_creates_one_atomic_claim_with_text_provenance(self):
        store = FakePromotionStore(written_context())
        receipt = promote_claim_candidate(store, self.request())
        self.assertTrue(receipt.promoted)
        self.assertEqual(receipt.action, "CREATED")
        self.assertEqual(receipt.reason_code, "PROMOTION_CREATED")
        self.assertEqual(len(receipt.provenance_refs), 1)
        call = next(x for x in store.calls if x[0] == "create_written")
        variables = call[1]
        self.assertEqual(variables["candidate_id"], "candidate:1")
        self.assertEqual(variables["selector_type"], "TEXT_POSITION_HASH")
        self.assertEqual(variables["start_char"], 10)
        self.assertEqual(
            variables["end_char"],
            10 + len("I test sull'impronta 33 diedero esito negativo."),
        )
        self.assertTrue(str(variables["provenance_id"]).startswith("text-provenance:"))

    def test_written_quote_must_match_exact_passage_hash(self):
        context = written_context()
        context["statement_text_hash"] = hashlib.sha256(
            b"I test sull'impronta 33 diedero esito positivo."
        ).hexdigest()
        receipt = promote_claim_candidate(FakePromotionStore(context), self.request())
        self.assertFalse(receipt.promoted)
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_STATEMENT_NOT_EXACT_PASSAGE",
        )

    def test_tampered_private_passage_text_is_blocked(self):
        context = written_context()
        changed = "I test sull'impronta 33 diedero esito positivo."
        context["passages"][0]["private_text"] = changed
        context["passages"][0]["end_char"] = (
            context["passages"][0]["start_char"] + len(changed)
        )
        receipt = promote_claim_candidate(FakePromotionStore(context), self.request())
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_PASSAGE_TEXT_HASH_MISMATCH",
        )

    def test_off_by_one_written_quote_span_is_blocked(self):
        context = written_context()
        context["passages"][0]["end_char"] += 1
        receipt = promote_claim_candidate(FakePromotionStore(context), self.request())
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_QUOTE_POSITION_LENGTH_MISMATCH",
        )

    def test_non_exact_written_selector_is_blocked(self):
        context = written_context()
        context["passages"][0]["selector_type"] = "PAGE_RANGE"
        context["passages"][0]["start_char"] = None
        context["passages"][0]["end_char"] = None
        context["passages"][0]["page_start"] = 1
        context["passages"][0]["page_end"] = 1
        receipt = promote_claim_candidate(FakePromotionStore(context), self.request())
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_QUOTE_SELECTOR_NOT_EXACT",
        )

    def test_media_candidate_creates_segment_link_not_text_provenance(self):
        store = FakePromotionStore(media_context())
        receipt = promote_claim_candidate(store, self.request("MEDIA"))
        self.assertTrue(receipt.promoted)
        self.assertEqual(receipt.provenance_refs, ("canonical-segment:1",))
        self.assertTrue(any(call[0] == "create_media" for call in store.calls))
        self.assertFalse(any(call[0] == "create_written" for call in store.calls))
        create_call = next(call for call in store.calls if call[0] == "create_media")
        promotion_metadata = json.loads(create_call[1]["metadata"])
        self.assertEqual(
            promotion_metadata["quote_binding_version"],
            "exact-media-quote-binding-v1",
        )
        self.assertEqual(
            promotion_metadata["quote_binding_reason"],
            "EXACT_MEDIA_SOURCE_SPAN_VERIFIED",
        )

    def test_media_quote_binding_requires_local_offsets(self):
        context = media_context()
        context["statement_metadata"].pop("quote_local_start_char")
        receipt = promote_claim_candidate(
            FakePromotionStore(context),
            self.request("MEDIA"),
        )
        self.assertFalse(receipt.promoted)
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_MEDIA_QUOTE_OFFSETS_MISSING",
        )

    def test_media_quote_binding_blocks_off_by_one_span(self):
        context = media_context()
        context["statement_metadata"]["quote_local_end_char"] -= 1
        receipt = promote_claim_candidate(
            FakePromotionStore(context),
            self.request("MEDIA"),
        )
        self.assertFalse(receipt.promoted)
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_MEDIA_QUOTE_HASH_MISMATCH",
        )

    def test_media_quote_binding_blocks_statement_hash_mismatch(self):
        context = media_context()
        context["statement_text_hash"] = hashlib.sha256(
            b"I test sull'impronta 33 diedero esito positivo."
        ).hexdigest()
        receipt = promote_claim_candidate(
            FakePromotionStore(context),
            self.request("MEDIA"),
        )
        self.assertFalse(receipt.promoted)
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_MEDIA_QUOTE_HASH_MISMATCH",
        )

    def test_media_quote_binding_blocks_out_of_range_span(self):
        context = media_context()
        context["statement_metadata"]["quote_local_end_char"] = (
            len(context["passages"][0]["segment_canonical_text"]) + 1
        )
        receipt = promote_claim_candidate(
            FakePromotionStore(context),
            self.request("MEDIA"),
        )
        self.assertFalse(receipt.promoted)
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_MEDIA_QUOTE_SPAN_INVALID",
        )

    def test_media_quote_binding_rejects_non_integer_offsets(self):
        for value in ("10", 10.5, True):
            with self.subTest(value=value):
                context = media_context()
                context["statement_metadata"]["quote_local_start_char"] = value
                receipt = promote_claim_candidate(
                    FakePromotionStore(context),
                    self.request("MEDIA"),
                )
                self.assertFalse(receipt.promoted)
                self.assertEqual(
                    receipt.reason_code,
                    "PROMOTION_MEDIA_QUOTE_BINDING_INVALID",
                )

    def test_review_gates_fail_closed(self):
        cases = [
            ("claim_candidate_reviewed", False, "PROMOTION_CLAIM_CANDIDATE_NOT_REVIEWED"),
            ("statement_reviewed", False, "PROMOTION_STATEMENT_NOT_REVIEWED"),
            ("statement_status", "CANDIDATE", "PROMOTION_STATEMENT_NOT_REVIEWED"),
            ("speaker_person_id", None, "PROMOTION_ATTRIBUTION_MISSING"),
            ("speaker_is_public", False, "PROMOTION_ATTRIBUTION_MISSING"),
        ]
        for key, value, expected in cases:
            with self.subTest(key=key):
                context = written_context()
                context[key] = value
                store = FakePromotionStore(context)
                receipt = promote_claim_candidate(store, self.request())
                self.assertFalse(receipt.promoted)
                self.assertEqual(receipt.reason_code, expected)
                self.assertEqual([c[0] for c in store.calls], ["context"])

    def test_capture_hold_and_quarantine_block_written_promotion(self):
        for key, value, expected in (
            ("capture_hold_status", "COPYRIGHT_HOLD", "PROMOTION_CAPTURE_HOLD"),
            ("capture_status", "QUARANTINED", "PROMOTION_CAPTURE_UNUSABLE"),
            ("capture_status", "PURGE_PENDING", "PROMOTION_CAPTURE_UNUSABLE"),
        ):
            with self.subTest(key=key, value=value):
                context = written_context()
                context["passages"][0][key] = value
                receipt = promote_claim_candidate(FakePromotionStore(context), self.request())
                self.assertEqual(receipt.reason_code, expected)

    def test_provenance_must_be_exactly_one_atomic_passage(self):
        context = written_context()
        context["passage_count"] = 0
        context["passages"] = []
        receipt = promote_claim_candidate(FakePromotionStore(context), self.request())
        self.assertEqual(receipt.reason_code, "PROMOTION_PROVENANCE_MISSING")

        context = written_context()
        context["passage_count"] = 2
        context["passages"].append(copy.deepcopy(context["passages"][0]))
        receipt = promote_claim_candidate(FakePromotionStore(context), self.request())
        self.assertEqual(receipt.reason_code, "PROMOTION_PROVENANCE_NOT_ATOMIC")

    def test_channels_do_not_cross(self):
        receipt = promote_claim_candidate(FakePromotionStore(written_context()), self.request("MEDIA"))
        self.assertEqual(receipt.reason_code, "PROMOTION_CHANNEL_MISMATCH")
        receipt = promote_claim_candidate(FakePromotionStore(media_context()), self.request("WRITTEN"))
        self.assertEqual(receipt.reason_code, "PROMOTION_CHANNEL_MISMATCH")

    def test_unresolved_media_is_blocked(self):
        for key, value in (
            ("segment_status", "TRANSCRIPT_UNCERTAIN"),
            ("segment_publication_blocked", True),
            ("segment_speaker_person_id", "person:other"),
        ):
            context = media_context()
            context["passages"][0][key] = value
            receipt = promote_claim_candidate(FakePromotionStore(context), self.request("MEDIA"))
            self.assertEqual(receipt.reason_code, "PROMOTION_MEDIA_PROVENANCE_UNRESOLVED")

    def test_machine_transcripts_are_not_direct_quote_authority(self):
        for method in (
            "PLATFORM_CAPTION",
            "SINGLE_ASR",
            "MULTI_ASR_AGREEMENT",
            "UNVERIFIED",
        ):
            with self.subTest(method=method):
                context = media_context()
                context["passages"][0]["segment_verbatim_method"] = method
                receipt = promote_claim_candidate(
                    FakePromotionStore(context),
                    self.request("MEDIA"),
                )
                self.assertFalse(receipt.promoted)
                self.assertEqual(
                    receipt.reason_code,
                    "PROMOTION_MEDIA_VERBATIM_NOT_ELIGIBLE",
                )

    def test_human_audio_review_can_make_media_verbatim_eligible(self):
        context = media_context()
        context["passages"][0]["segment_verbatim_method"] = "HUMAN_AUDIO_VERIFIED"
        receipt = promote_claim_candidate(
            FakePromotionStore(context),
            self.request("MEDIA"),
        )
        self.assertTrue(receipt.promoted)

    def test_media_promotion_requires_exact_approved_speaker_proof(self):
        context = media_context()
        context["passages"][0]["segment_speaker_provenance_ok"] = False
        receipt = promote_claim_candidate(
            FakePromotionStore(context),
            self.request("MEDIA"),
        )
        self.assertFalse(receipt.promoted)
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_MEDIA_SPEAKER_PROOF_MISSING",
        )

    def test_media_context_sql_requires_strong_speaker_method_and_full_span(self):
        self.assertIn("FROM speaker_identity_candidate speaker", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("'MANUAL_REVIEW'", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("'TRANSCRIPT_LABEL'", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("'OFFICIAL_RECORD'", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("segment.start_ms >= speaker.start_ms", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("segment.end_ms <= speaker.end_ms", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("'SPEAKER_IDENTITY_CANDIDATE'", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("sc.metadata AS statement_metadata", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn(
            "segment.canonical_text AS segment_canonical_text",
            PROMOTION_CONTEXT_SQL_V1,
        )
        self.assertIn("transcript_verbatim_review_event verbatim_review", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("verbatim_review.source_variant_sha256", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("verbatim_review.source_segment_sha256", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("verbatim_review.reviewed_text_sha256", PROMOTION_CONTEXT_SQL_V1)

    def test_media_mutation_sql_requires_exact_quote_span_receipt(self):
        for sql in (_LINK_EXISTING_SQL, _PROMOTE_MEDIA_NEW_SQL):
            self.assertIn("quote_local_start_char", sql)
            self.assertIn("quote_local_end_char", sql)
            self.assertIn("context_integrity,quote_sha256", sql)
            self.assertIn("char_length(seg.canonical_text)", sql)
            self.assertIn("substring(", sql)
            self.assertIn("sha256(", sql)
            self.assertIn(") = c.statement_text_hash", sql)
            self.assertIn("'OFFICIAL_TRANSCRIPT'", sql)
            self.assertIn("transcript_verbatim_review_event verbatim_review", sql)
            self.assertIn("verbatim_review.source_variant_sha256", sql)
            self.assertIn("verbatim_review.source_segment_sha256", sql)
            self.assertIn("verbatim_review.reviewed_text_sha256", sql)

    def test_single_reviewed_duplicate_links_existing_with_receipt(self):
        context = written_context()
        context["duplicate_target_ids"] = ["claim:existing"]
        store = FakePromotionStore(context)
        receipt = promote_claim_candidate(store, self.request())
        self.assertTrue(receipt.promoted)
        self.assertEqual(receipt.action, "LINKED_EXISTING")
        self.assertEqual(receipt.target_claim_id, "claim:existing")
        self.assertTrue(any(c[0] == "link_existing" for c in store.calls))
        self.assertFalse(any(c[0] == "create_written" for c in store.calls))

    def test_ambiguous_duplicate_blocks_without_mutation(self):
        context = written_context()
        context["duplicate_target_ids"] = ["claim:a", "claim:b"]
        store = FakePromotionStore(context)
        receipt = promote_claim_candidate(store, self.request())
        self.assertEqual(receipt.reason_code, "PROMOTION_AMBIGUOUS_DUPLICATE")
        self.assertEqual([c[0] for c in store.calls], ["context"])

    def test_reported_speech_cannot_promote_or_link_existing_without_origin(self):
        for duplicate_targets in ([], ["claim:existing"]):
            with self.subTest(duplicate_targets=duplicate_targets):
                context = written_context()
                context["candidate_metadata"] = {
                    "speech_mode": "REPORTED_SPEECH",
                    "reported_origin_required": True,
                }
                context["duplicate_target_ids"] = duplicate_targets
                store = FakePromotionStore(context)
                receipt = promote_claim_candidate(store, self.request())
                self.assertFalse(receipt.promoted)
                self.assertEqual(
                    receipt.reason_code,
                    "PROMOTION_REPORTED_SPEECH_ORIGIN_REQUIRED",
                )
                self.assertFalse(
                    any(
                        call[0] in {"link_existing", "create_written"}
                        for call in store.calls
                    )
                )

    def test_missing_blank_or_unknown_speech_mode_fails_closed(self):
        for metadata in (
            {},
            {"speech_mode": ""},
            {"speech_mode": "   "},
            {"speech_mode": "UNKNOWN"},
        ):
            with self.subTest(metadata=metadata):
                context = written_context()
                context["candidate_metadata"] = metadata
                store = FakePromotionStore(context)
                receipt = promote_claim_candidate(store, self.request())
                self.assertFalse(receipt.promoted)
                self.assertEqual(
                    receipt.reason_code,
                    "PROMOTION_REPORTED_SPEECH_ORIGIN_REQUIRED",
                )
                self.assertEqual([call[0] for call in store.calls], ["context"])

    def test_reported_wording_cannot_be_upgraded_by_direct_speech_metadata(self):
        context = written_context()
        context["candidate_metadata"]["speech_mode"] = "DIRECT_UTTERANCE"
        context["candidate_metadata"]["wording"] = wording_contract_metadata(
            occurrence_id="statement:1",
            source_text_sha256=context["statement_text_hash"],
            normalized_claim=context["normalized_claim"],
            language="it",
            derivation_version="test-v1",
            source_wording_type=WordingType.REPORTED_QUOTE,
        )
        store = FakePromotionStore(context)
        receipt = promote_claim_candidate(store, self.request())
        self.assertFalse(receipt.promoted)
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_WORDING_DIRECT_SOURCE_REQUIRED",
        )
        self.assertEqual([call[0] for call in store.calls], ["context"])

    def test_summary_and_translation_metadata_remain_derived_during_promotion(self):
        context = written_context()
        summary = make_summary_wording(
            occurrence_id="statement:1",
            summary="Sintesi editoriale del contenuto.",
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            language="it",
            derivation_version="test-v1",
        )
        translation = make_translation_wording(
            occurrence_id="statement:1",
            source_text="I test sull'impronta 33 diedero esito negativo.",
            translated_text="The footprint 33 tests were negative.",
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            source_language="it",
            target_language="en",
            method="HUMAN",
            derivation_version="test-v1",
            human_reviewed=True,
        )
        context["candidate_metadata"]["wording"] = wording_contract_metadata(
            occurrence_id="statement:1",
            source_text_sha256=context["statement_text_hash"],
            normalized_claim=context["normalized_claim"],
            language="it",
            derivation_version="test-v1",
            representations=(summary, translation),
        )
        store = FakePromotionStore(context)
        receipt = promote_claim_candidate(store, self.request())
        self.assertTrue(receipt.promoted)
        self.assertTrue(any(call[0] == "create_written" for call in store.calls))
        wording = context["candidate_metadata"]["wording"]
        for representation in wording["representations"]:
            self.assertFalse(representation["direct_quote_eligible"])
            self.assertEqual(
                representation["representation_role"],
                "DERIVED_REPRESENTATION",
            )

    def test_all_mutation_sql_refuses_non_direct_speech_mode(self):
        guard = "cc.metadata->>'speech_mode'='DIRECT_UTTERANCE'"
        for sql in (
            _LINK_EXISTING_SQL,
            _PROMOTE_WRITTEN_NEW_SQL,
            _PROMOTE_MEDIA_NEW_SQL,
        ):
            self.assertIn(guard, sql)
            self.assertNotIn("COALESCE(cc.metadata->>'speech_mode'", sql)

    def test_all_mutation_sql_requires_verbatim_source_not_derived_representation(self):
        for sql in (
            _LINK_EXISTING_SQL,
            _PROMOTE_WRITTEN_NEW_SQL,
            _PROMOTE_MEDIA_NEW_SQL,
        ):
            self.assertIn(
                "cc.metadata#>>'{wording,source_occurrence,wording_type}'='VERBATIM_ORIGINAL'",
                sql,
            )
            self.assertIn(
                "cc.metadata#>>'{wording,normalized_claim,wording_type}'='PARAPHRASE'",
                sql,
            )

    def test_all_mutation_sql_requires_context_clearance(self):
        guard = (
            "cc.metadata#>>'{context_integrity,state}' IN "
            "('CLEAR_AUTOMATIC','APPROVED_CURATED')"
        )
        for sql in (
            _LINK_EXISTING_SQL,
            _PROMOTE_WRITTEN_NEW_SQL,
            _PROMOTE_MEDIA_NEW_SQL,
        ):
            self.assertIn(guard, sql)

    def test_context_risk_blocks_before_any_mutation(self):
        context = written_context()
        context["candidate_metadata"]["context_integrity"] = {
            "state": "NEEDS_CONTEXT_REVIEW",
            "signal_codes": ["NEGATION_NEAR_BOUNDARY_OMITTED"],
        }
        store = FakePromotionStore(context)
        receipt = promote_claim_candidate(store, self.request())
        self.assertFalse(receipt.promoted)
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_CONTEXT_INTEGRITY_REVIEW_REQUIRED",
        )
        self.assertEqual([call[0] for call in store.calls], ["context"])

    def test_missing_context_state_fails_closed(self):
        context = written_context()
        context["candidate_metadata"].pop("context_integrity")
        receipt = promote_claim_candidate(
            FakePromotionStore(context),
            self.request(),
        )
        self.assertEqual(
            receipt.reason_code,
            "PROMOTION_CONTEXT_INTEGRITY_MISSING",
        )

    def test_existing_promotion_replays_same_receipt(self):
        context = written_context()
        context["candidate_status"] = "PROMOTED"
        context["promoted_claim_id"] = "claim:existing"
        context["existing_promotion"] = {
            "id": "promotion:1",
            "target_claim_id": "claim:existing",
            "action": "CREATED",
            "provenance_channel": "WRITTEN",
            "provenance_refs": ["text-provenance:1"],
            "idempotency_key": "key:1",
        }
        receipt = promote_claim_candidate(FakePromotionStore(context), self.request())
        self.assertTrue(receipt.promoted)
        self.assertTrue(receipt.replayed)
        self.assertEqual(receipt.target_claim_id, "claim:existing")
        self.assertEqual(receipt.provenance_refs, ("text-provenance:1",))

    def test_promoted_candidate_without_ledger_fails_closed(self):
        context = written_context()
        context["candidate_status"] = "PROMOTED"
        context["promoted_claim_id"] = "claim:orphan"
        receipt = promote_claim_candidate(FakePromotionStore(context), self.request())
        self.assertEqual(receipt.reason_code, "PROMOTION_LEDGER_MISSING")

    def test_context_sql_uses_approved_review_and_cluster_edges_only(self):
        self.assertIn("r.entity_type='CLAIM_CANDIDATE'", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("r.entity_type='STATEMENT_CANDIDATE'", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("source.status = 'APPROVED'", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("cluster.status = 'APPROVED'", PROMOTION_CONTEXT_SQL_V1)
        self.assertIn("target.status = 'APPROVED'", PROMOTION_CONTEXT_SQL_V1)
        self.assertNotIn("evidence", PROMOTION_CONTEXT_SQL_V1.lower())
        self.assertNotIn("finding", PROMOTION_CONTEXT_SQL_V1.lower())
        self.assertNotIn("publication_status", PROMOTION_CONTEXT_SQL_V1.lower())


if __name__ == "__main__":
    unittest.main()
