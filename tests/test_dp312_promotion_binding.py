"""Source-bound speech-act promotion regressions for DP-312."""

import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.claim_promotion import (  # noqa: E402
    PROMOTION_CONTEXT_SQL_V1, PromotionRequest, _LINK_EXISTING_SQL,
    _PROMOTE_MEDIA_NEW_SQL, _PROMOTE_WRITTEN_NEW_SQL, promote_claim_candidate,
)
from dichiarazioni_pubbliche.wording_contract import wording_contract_metadata  # noqa: E402
from test_claim_promotion import FakePromotionStore, written_context  # noqa: E402


class DP312PromotionBindingTests(unittest.TestCase):
    def request(self):
        return PromotionRequest(
            candidate_id="candidate:1", provenance_channel="WRITTEN",
            actor_ref="reviewer:1", reason="promotion checked",
        )

    def test_private_semantic_classification_cannot_promote_quotation_or_criticism(self):
        for speech_act in ("REPORT", "QUOTE", "CRITIQUE", "QUESTION", "PERFORMANCE", "UNKNOWN"):
            with self.subTest(speech_act=speech_act):
                context = written_context()
                context["candidate_metadata"]["speech_act_context"] = {
                    "state": "HOLD_FOR_CONTEXT",
                    "speech_act": speech_act,
                }
                store = FakePromotionStore(context)
                result = promote_claim_candidate(store, self.request())
                self.assertFalse(result.promoted)
                self.assertEqual(result.reason_code, "PROMOTION_NON_ASSERTIVE_SPEECH_ACT")
                self.assertEqual([name for name, _args in store.calls], ["context"])

        context = written_context()
        context["candidate_metadata"]["speech_act_context"] = {
            "state": "HOLD_FOR_CONTEXT", "speech_act": "ASSERTION",
        }
        self.assertEqual(
            promote_claim_candidate(FakePromotionStore(context), self.request()).reason_code,
            "PROMOTION_SPEECH_ACT_CONTEXT_UNVERIFIED",
        )

    def test_private_assertion_must_replay_against_approved_source_and_identity(self):
        from dichiarazioni_pubbliche.context_integrity import assess_speech_act_context

        source = "Io sostengo che il piano funziona."
        semantic = assess_speech_act_context(
            source_text=source,
            source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            quote_start=0, quote_end=len(source), turn_start=0, turn_end=len(source),
            utterer_id="person:1", turn_speaker_ids=("person:1",),
            source_part_ref="passage:parent", turn_complete=True, language="it",
        ).to_metadata()
        self.assertEqual(semantic["state"], "CANDIDATE_PRIVATE")
        self.assertEqual(semantic["speech_act"], "ASSERTION")
        base = written_context()
        base["candidate_metadata"]["parent_passage_id"] = "passage:parent"
        base["candidate_metadata"]["context_integrity"]["source_sha256"] = semantic["source_sha256"]
        base["candidate_metadata"]["speech_act_context"] = semantic
        base["speech_act_source_text"] = source
        base["statement_text_hash"] = semantic["quote_sha256"]
        base["statement_metadata"] = {"speech_act_context": semantic}
        base["passages"][0]["private_text"] = source
        base["passages"][0]["text_sha256"] = semantic["quote_sha256"]
        base["passages"][0]["end_char"] = base["passages"][0]["start_char"] + len(source)
        base["candidate_metadata"]["wording"] = wording_contract_metadata(
            occurrence_id="statement:1", source_text_sha256=semantic["quote_sha256"],
            normalized_claim=base["normalized_claim"], language="it",
            derivation_version="test-v1",
        )
        self.assertTrue(promote_claim_candidate(FakePromotionStore(base), self.request()).promoted)

        for field, tampered in (
            ("binding_sha256", "0" * 64),
            ("quote_sha256", "0" * 64),
            ("utterer_id", "person:other"),
            ("source_part_ref", "passage:other"),
            ("source_sha256", "0" * 64),
            ("state", "HOLD_FOR_CONTEXT"),
            ("stance", "UNKNOWN"),
        ):
            with self.subTest(field=field):
                context = copy.deepcopy(base)
                context["candidate_metadata"]["speech_act_context"][field] = tampered
                context["statement_metadata"]["speech_act_context"][field] = tampered
                store = FakePromotionStore(context)
                receipt = promote_claim_candidate(store, self.request())
                self.assertEqual(receipt.reason_code, "PROMOTION_SPEECH_ACT_CONTEXT_UNVERIFIED")
                self.assertEqual([call[0] for call in store.calls], ["context"])

        for field, changed in (
            ("speech_act_source_text", source + " Non lo sostengo."),
            ("statement_text_hash", "0" * 64),
        ):
            with self.subTest(field=field):
                context = copy.deepcopy(base)
                context[field] = changed
                self.assertEqual(
                    promote_claim_candidate(FakePromotionStore(context), self.request()).reason_code,
                    "PROMOTION_SPEECH_ACT_CONTEXT_UNVERIFIED",
                )

        desynced = copy.deepcopy(base)
        desynced["statement_metadata"]["speech_act_context"] = {"speech_act": "REPORT"}
        self.assertEqual(
            promote_claim_candidate(FakePromotionStore(desynced), self.request()).reason_code,
            "PROMOTION_SPEECH_ACT_CONTEXT_UNVERIFIED",
        )

        stripped = copy.deepcopy(base)
        stripped["candidate_metadata"].pop("speech_act_context")
        self.assertEqual(
            promote_claim_candidate(FakePromotionStore(stripped), self.request()).reason_code,
            "PROMOTION_SPEECH_ACT_CONTEXT_UNVERIFIED",
        )

    def test_all_mutation_sql_rejects_non_assertive_speech_act(self):
        guard = "cc.metadata#>>'{speech_act_context,speech_act}' IN ('ASSERTION','OPINION')"
        for sql in (_LINK_EXISTING_SQL, _PROMOTE_WRITTEN_NEW_SQL, _PROMOTE_MEDIA_NEW_SQL):
            self.assertIn(guard, sql)
            self.assertIn(
                "cc.metadata->'speech_act_context' IS NULL AND sc.metadata->'speech_act_context' IS NULL",
                sql,
            )
            for condition in (
                "cc.metadata#>>'{speech_act_context,state}'='CANDIDATE_PRIVATE'",
                "cc.metadata#>>'{speech_act_context,stance}'='ENDORSE'",
                "cc.metadata#>>'{speech_act_context,utterer_id}'=sc.speaker_person_id",
                "cc.metadata#>>'{speech_act_context,quote_sha256}'=sc.statement_text_hash",
                "cc.metadata#>>'{speech_act_context,source_part_ref}'=cc.metadata->>'parent_passage_id'",
                "cc.metadata#>>'{speech_act_context,source_sha256}'=cc.metadata#>>'{context_integrity,source_sha256}'",
                "cc.metadata->'speech_act_context'=sc.metadata->'speech_act_context'",
            ):
                self.assertIn(condition, sql)
        self.assertIn("'speech_act_source_text'", PROMOTION_CONTEXT_SQL_V1)
        for sql in (_LINK_EXISTING_SQL, _PROMOTE_WRITTEN_NEW_SQL, _PROMOTE_MEDIA_NEW_SQL):
            self.assertIn("COALESCE(source_parent.private_text, source_segment.canonical_text)", sql)
            self.assertIn("'hex')=cc.metadata#>>'{speech_act_context,source_sha256}'", sql)

    def test_extracted_unverified_turn_stays_held_until_source_review(self):
        from dichiarazioni_pubbliche.context_integrity import assess_speech_act_context

        source = "Io sostengo che il piano funziona."
        semantic = assess_speech_act_context(
            source_text=source, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            quote_start=0, quote_end=len(source), turn_start=0, turn_end=len(source),
            utterer_id="person:1", turn_speaker_ids=("person:1",),
            source_part_ref="passage:parent", turn_complete=False, language="it",
        ).to_metadata()
        self.assertEqual(semantic["state"], "HOLD_FOR_CONTEXT")
        self.assertIn("TURN_COMPLETENESS_UNVERIFIED", semantic["signal_codes"])
        context = written_context()
        context["candidate_metadata"]["speech_act_context"] = semantic
        context["statement_metadata"] = {"speech_act_context": semantic}
        context["speech_act_source_text"] = source
        context["candidate_metadata"]["parent_passage_id"] = "passage:parent"
        self.assertEqual(
            promote_claim_candidate(FakePromotionStore(context), self.request()).reason_code,
            "PROMOTION_SPEECH_ACT_CONTEXT_UNVERIFIED",
        )
