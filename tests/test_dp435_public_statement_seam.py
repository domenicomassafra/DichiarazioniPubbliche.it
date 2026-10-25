"""DP-435/437 isolated Statement seam: no DB, publication, or real rights grant."""

from __future__ import annotations

import copy
import hashlib
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    build_public_projection,
    write_public_bundle,
)
from dichiarazioni_pubbliche.autonomous_publication import (  # noqa: E402
    AgentReview,
    AutonomousCandidate,
    AutonomousProofPacket,
    SpeakerSignal,
    candidate_fingerprint,
)
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    PUBLIC_SCHEMA_VERSION,
    PUBLIC_STATEMENT_SCHEMA_VERSION,
    PublicSchemaValidationError,
    projection_dataset_sha256,
    validate_public_bundle,
    validate_public_statement,
)


STAMP = "2026-10-11T12:00:00+00:00"
SOURCE = "Domanda: quanto costa? Risposta: costa 10 euro, non 20."
QUOTE = "costa 10 euro, non 20."
START = SOURCE.index(QUOTE)
def SHA(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class IsolatedStatementSource:
    """Distinct candidate, immutable-source, and decision interfaces."""

    def __init__(self, *, source_kind="WRITTEN"):
        self.source_text = SOURCE
        locator = {"start_char": START, "end_char": START + len(QUOTE)}
        if source_kind == "TIMED":
            locator.update({"segment_id": "segment:1", "start_ms": 2000, "end_ms": 4000})
        self.row = {
            "statement_id": "statement:1",
            "version_id": "statement-version:1",
            "person_id": "person:1",
            "speaker_name": "Persona dimostrativa",
            "content_id": "content:1",
            "source_title": "Documento dimostrativo",
            "source_url": "https://example.org/documento",
            "source_version": "source-version:1",
            "source_sha256": SHA(SOURCE),
            "original_text": QUOTE,
            "language": "it",
            "statement_date": "2026-10-10",
            "source_kind": source_kind,
            "locator": locator,
            "finding_id": None,
            "summary": None,
            "translation": None,
        }
        self.gates = {}
        for name in ("rights", "attribution", "context", "wording", "publication"):
            self.gates[name] = {
                "status": "APPROVED",
                "decision_id": f"decision:{name}:1",
                "review_event_id": f"review:{name}:1",
                "statement_id": "statement:1",
                "version_id": "statement-version:1",
                "person_id": "person:1",
                "content_id": "content:1",
                "source_sha256": SHA(SOURCE),
                "quote_sha256": SHA(QUOTE),
                "source_version": "source-version:1",
                "statement_date": "2026-10-10",
                "span_start": START,
                "span_end": START + len(QUOTE),
                "source_url": "https://example.org/documento",
                "source_title": "Documento dimostrativo",
            }
        self.gates["rights"].update({
            "use_scope": "PUBLIC_EXACT_EXCERPT", "expires_at": "2026-12-31T00:00:00+00:00",
            "policy_version": "rights-v1", "jurisdiction": "IT",
        })
        self.gates["context"].update({"speech_act": "OPINION", "endorsed": True})
        self.gates["attribution"]["speaker_name"] = "Persona dimostrativa"
        self.gates["wording"]["method"] = (
            "SOURCE_TEXT_VERIFIED" if source_kind == "WRITTEN" else "OFFICIAL_TRANSCRIPT"
        )
        self.gates["wording"].update({"language": "it", "source_kind": source_kind})
        if source_kind == "TIMED":
            self.gates["wording"].update({
                "segment_id": "segment:1", "start_ms": 2000, "end_ms": 4000,
            })
            self.gates["attribution"].update({
                "segment_id": "segment:1", "start_ms": 2000, "end_ms": 4000,
            })

    def projectable_findings(self):
        return []

    def projectable_public_statements(self):
        return [self.row]

    def get_statement_source_text(self, content_id, source_version):
        if (content_id, source_version) != ("content:1", "source-version:1"):
            raise ValueError("missing immutable source")
        return self.source_text

    def statement_publication_attestations(self, statement_id, version_id):
        if (statement_id, version_id) != ("statement:1", "statement-version:1"):
            raise ValueError("missing independent review")
        return self.gates

    def autonomous_publication_evidence(self, statement_id, version_id):
        if (statement_id, version_id) != (
            self.row["statement_id"], self.row["version_id"]
        ):
            raise ValueError("unrecognized statement version")
        locator = self.row["locator"]
        timed = self.row["source_kind"] == "TIMED"
        packet = AutonomousCandidate(
            record_id=statement_id,
            source_url=self.row["source_url"],
            source_kind=self.row["source_kind"],
            snapshot_url="https://archive.example.org/original",
            snapshot_sha256=SHA(self.source_text),
            captured_at=STAMP,
            segment_start=locator["start_ms"] / 1000 if timed else locator["start_char"],
            segment_end=locator["end_ms"] / 1000 if timed else locator["end_char"],
            quote=self.row["original_text"],
            transcript_segment=self.row["original_text"],
            alignment_confidence=0.99,
            speaker_id=self.row["person_id"],
            speaker_signals=(
                SpeakerSignal("official_channel", "https://example.org/channel"),
                SpeakerSignal("source_caption", "https://example.org/caption"),
            ),
            public_role_source_url="https://www.wikidata.org/wiki/Q123",
            public_context_source_url=None,
            person_is_minor=False,
            sensitive_third_party_data=False,
            privacy_cleared=True,
            privacy_citation_url="https://www.garanteprivacy.it/",
            rights_cleared=True,
            rights_citation_url="https://www.normattiva.it/",
            source_length_chars=len(self.source_text),
            contains_editorial_judgment=False,
        )
        fingerprint = candidate_fingerprint(packet)
        stages = ("PROVENANCE", "WORDING", "SPEAKER", "PERSON", "RIGHTS_PRIVACY")
        return AutonomousProofPacket(
            candidate=packet,
            primary=AgentReview("agent:1", "model:1", fingerprint, stages, True),
            independent=AgentReview("agent:2", "model:2", fingerprint, stages, True),
        )

    def current_statement_challenge_hold(self, statement_id, version_id):
        if (statement_id, version_id) != (
            self.row["statement_id"], self.row["version_id"]
        ):
            raise ValueError("unrecognized statement version")
        return False


class PublicStatementContractTests(unittest.TestCase):
    def build_v3(self, source):
        return build_public_projection(
            source, generated_at=STAMP, include_public_statements=True,
        )

    def test_default_v2_unchanged_even_when_source_has_v3_candidates(self):
        source = IsolatedStatementSource()
        old = build_public_projection(source, generated_at=STAMP)
        self.assertEqual(old["schema_version"], PUBLIC_SCHEMA_VERSION)
        self.assertNotIn("statements", old)
        self.assertNotIn("statement_publication_requires_independent_gates", old["methodology"])
        self.assertEqual(old["dossier_count"], 0)
        self.assertIs(validate_public_bundle(old), old)

    def test_opt_in_exact_original_and_opinion_without_finding(self):
        bundle = self.build_v3(IsolatedStatementSource())
        self.assertEqual(bundle["schema_version"], PUBLIC_STATEMENT_SCHEMA_VERSION)
        record = bundle["statements"][0]
        self.assertEqual(record["original_text"], QUOTE)
        self.assertEqual(record["locator"], {"start_char": START, "end_char": START + len(QUOTE)})
        self.assertIsNone(record["finding_id"])
        self.assertEqual(record["speech_act"], "OPINION")
        self.assertEqual(record["quote_sha256"], SHA(QUOTE))
        self.assertEqual(len(record["review_provenance"]), 5)
        self.assertNotIn("normalized_claim", str(bundle))
        self.assertNotIn(SOURCE, str(bundle))
        self.assertEqual(bundle["dataset_sha256"], projection_dataset_sha256(bundle))
        self.assertEqual(self.build_v3(IsolatedStatementSource()), bundle)
        with self.assertRaisesRegex(PublicSchemaValidationError, "explicit opt-in"):
            validate_public_bundle(bundle)
        self.assertIs(validate_public_bundle(bundle, allow_statement_v3=True), bundle)

    def test_opt_in_requires_separate_autonomous_review_receipts(self):
        source = IsolatedStatementSource()
        source.autonomous_publication_evidence = None
        self.assertEqual(
            self.build_v3(source)["statements"], [],
            "legacy gate approvals cannot substitute for two agent model reviews",
        )

    def test_autonomous_reviewer_and_challenge_holds_override_legacy_approvals(self):
        source = IsolatedStatementSource()
        original = source.autonomous_publication_evidence
        source.autonomous_publication_evidence = lambda a, b: replace(
            original(a, b), independent=replace(original(a, b).independent, model_id="model:1")
        )
        self.assertEqual(self.build_v3(source)["statements"], [])
        source.autonomous_publication_evidence = original
        source.current_statement_challenge_hold = lambda a, b: True
        self.assertEqual(self.build_v3(source)["statements"], [])

    def test_opt_in_requires_separate_source_and_decision_interfaces(self):
        class CandidateOnly:
            def projectable_findings(self):
                return []

            def projectable_public_statements(self):
                return [IsolatedStatementSource().row]

        with self.assertRaisesRegex(ValueError, "separate private source"):
            self.build_v3(CandidateOnly())

    def test_candidate_cannot_self_certify_source_text_or_span(self):
        for damage in ("altered_quote", "altered_source", "altered_locator", "unknown_key"):
            with self.subTest(damage=damage):
                source = IsolatedStatementSource()
                if damage == "altered_quote":
                    source.row["original_text"] = "costa 20 euro, non 10."
                elif damage == "altered_source":
                    source.source_text = SOURCE.replace("10 euro", "15 euro")
                elif damage == "altered_locator":
                    source.row["locator"]["start_char"] += 1
                else:
                    source.row["raw_transcript"] = "PRIVATE TRANSCRIPT BODY"
                bundle = self.build_v3(source)
                self.assertEqual(bundle["statements"], [])
                self.assertNotIn("PRIVATE TRANSCRIPT BODY", str(bundle))

    def test_locator_changed_during_attestation_cannot_publish_unreviewed_source_span(self):
        class MovingLocatorSource(IsolatedStatementSource):
            def statement_publication_attestations(self, statement_id, version_id):
                proofs = super().statement_publication_attestations(statement_id, version_id)
                # The independent reviews cover START, but the private mutable
                # row is updated before _sanitize_public_statement returns.
                self.row["locator"].update(start_char=0, end_char=len(QUOTE))
                return proofs

        source = MovingLocatorSource()
        self.assertNotEqual(source.source_text[:len(QUOTE)], QUOTE)
        self.assertEqual(self.build_v3(source)["statements"], [])

    def test_published_locator_is_independent_of_private_candidate_mutations(self):
        source = IsolatedStatementSource()
        built = self.build_v3(source)
        public_locator = copy.deepcopy(built["statements"][0]["locator"])
        public_fingerprint = built["dataset_sha256"]
        source.row["locator"].update(start_char=0, end_char=len(QUOTE))
        self.assertEqual(built["statements"][0]["locator"], public_locator)
        self.assertEqual(projection_dataset_sha256(built), public_fingerprint)

    def test_each_independent_gate_and_hash_binding_fail_closed(self):
        for name in ("rights", "attribution", "context", "wording", "publication"):
            for damage in ("status", "hash", "person"):
                with self.subTest(gate=name, damage=damage):
                    source = IsolatedStatementSource()
                    if damage == "status":
                        source.gates[name]["status"] = "HELD"
                    elif damage == "hash":
                        source.gates[name]["quote_sha256"] = "0" * 64
                    else:
                        source.gates[name]["person_id"] = "person:other"
                    self.assertEqual(self.build_v3(source)["statements"], [])

    def test_unresolved_person_id_cannot_be_published_by_matching_gate_claims(self):
        # Independent-looking approval references cannot turn an explicit
        # unresolved identity placeholder into an attributable public quote.
        for placeholder in (
            "UNKNOWN", "person:unknown", "person:unresolved", "person:unspecified",
            "person:none", "person:",
        ):
            with self.subTest(person_id=placeholder):
                source = IsolatedStatementSource()
                source.row["person_id"] = placeholder
                for gate in source.gates.values():
                    gate["person_id"] = placeholder
                public = self.build_v3(source)
                self.assertEqual(public["statements"], [])
                self.assertNotIn(placeholder, str(public))

    def test_rights_unknown_expired_invalid_scope_and_reused_review_event(self):
        for damage in ("rights_unknown", "expired", "no_expiry", "scope", "same_reviewer"):
            with self.subTest(damage=damage):
                source = IsolatedStatementSource()
                if damage == "rights_unknown":
                    source.gates["rights"]["status"] = "UNKNOWN"
                elif damage == "expired":
                    source.gates["rights"]["expires_at"] = "2026-01-01T00:00:00+00:00"
                elif damage == "no_expiry":
                    # An unbounded rights clearance is not an authorized
                    # perpetual license for public verbatim reproduction.
                    source.gates["rights"]["expires_at"] = None
                elif damage == "scope":
                    source.gates["rights"]["use_scope"] = "INTERNAL_ONLY"
                else:
                    source.gates["context"]["review_event_id"] = source.gates["rights"]["review_event_id"]
                self.assertEqual(self.build_v3(source)["statements"], [])

    def test_timed_requires_reviewed_verbatim_and_exact_speaker_segment(self):
        source = IsolatedStatementSource(source_kind="TIMED")
        self.assertEqual(len(self.build_v3(source)["statements"]), 1)
        source.gates["wording"]["method"] = "AUTOMATIC_ASR"
        self.assertEqual(self.build_v3(source)["statements"], [])
        source.gates["wording"]["method"] = "HUMAN_AUDIO_VERIFIED"
        source.gates["attribution"]["segment_id"] = "segment:another"
        self.assertEqual(self.build_v3(source)["statements"], [])

    def test_summary_and_translation_are_separate_reviewed_representations(self):
        source = IsolatedStatementSource()
        source.row["summary"] = {"text": "Dice che il costo è di dieci euro."}
        source.row["translation"] = {"text": "It costs ten euros, not twenty.", "language": "en", "source_language": "it"}
        for kind in ("summary", "translation"):
            source.gates[kind] = {
                "status": "APPROVED", "review_event_id": f"review:{kind}",
                "source_quote_sha256": SHA(QUOTE),
                "text_sha256": SHA(source.row[kind]["text"]),
            }
        result = self.build_v3(source)["statements"][0]
        self.assertEqual(result["original_text"], QUOTE)
        self.assertEqual(result["summary"]["wording_type"], "SUMMARY")
        self.assertEqual(result["translation"]["wording_type"], "TRANSLATION")
        self.assertEqual(result["translation"]["source_language"], "it")
        source.gates["translation"]["text_sha256"] = SHA("some other translation")
        self.assertEqual(self.build_v3(source)["statements"], [])

    def test_schema_rejects_false_quote_translation_or_verdict(self):
        statement = self.build_v3(IsolatedStatementSource())["statements"][0]
        for field, value in (
            ("original_text", "costa 20 euro"),
            ("endorsed", "yes"),
            ("finding_id", "finding:private"),
            ("raw_transcript", "PRIVATE"),
        ):
            with self.subTest(field=field):
                bad = copy.deepcopy(statement)
                bad[field] = value
                if field == "finding_id":
                    bundle = self.build_v3(IsolatedStatementSource())
                    bundle["statements"] = [bad]
                    bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
                    with self.assertRaises(PublicSchemaValidationError):
                        validate_public_bundle(bundle, allow_statement_v3=True)
                else:
                    with self.assertRaises(PublicSchemaValidationError):
                        validate_public_statement(bad)

    def test_public_v3_writer_is_disabled_before_consumer_migration(self):
        bundle = self.build_v3(IsolatedStatementSource())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "public"
            with self.assertRaisesRegex(ValueError, "DP-436"):
                write_public_bundle(root, bundle)
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
