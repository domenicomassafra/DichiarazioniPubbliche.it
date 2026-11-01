"""DP-468 persistent authority and challenge ledgers fail closed on stale evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dichiarazioni_pubbliche.autonomous_publication import (
    AgentReview, AutonomousProofPacket, CHECKS, candidate_fingerprint,
)
from dichiarazioni_pubbliche.public_statement_authority import (
    PublicStatementAuthorityStore, PublicStatementChallengeStore,
)
from test_autonomous_publication import written_candidate


PRIMARY_MODEL = "antigravity/gemini-3.8-flash-tiered"
SECOND_MODEL = "antigravity/gemini-3.7-flash"
THIRD_MODEL = "antigravity/gemini-3.1-pro"


class MemoryPostgres:
    """Small SQL-contract fake: persists rows and returns PostgreSQL JSON shapes."""

    def __init__(self):
        self.authority_events = []
        self.challenge_requests = {}
        self.challenge_events = []
        self.wrong_return = False

    def run(self, sql, **values):
        if "INSERT INTO public_statement_authority_event" in sql:
            row = {
                "event_id": values["event_id"],
                "statement_id": values["statement_id"],
                "version_id": values["version_id"],
                "authority_kind": values["authority_kind"],
                "event_sequence": int(values["event_sequence"]),
                "previous_event_id": values["previous_event_id"] or None,
                "previous_integrity_sha256": values["previous_integrity_sha256"] or None,
                "decision_id": values["decision_id"],
                "review_event_id": values["review_event_id"],
                "status": values["status"],
                "binding": json.loads(values["binding"]),
                "payload": json.loads(values["payload"]),
                "review_evidence": json.loads(values["review_evidence"]),
                "reviewer_ref": values["reviewer_ref"],
                "reviewed_at": values["reviewed_at"],
                "expires_at": values["expires_at"] or None,
                "integrity_sha256": values["integrity_sha256"],
            }
            self.authority_events.append(row)
            return "wrong-event" if self.wrong_return else values["event_id"]

        if "FROM public_statement_authority_event" in sql:
            rows = [
                row for row in self.authority_events
                if row["statement_id"] == values["statement_id"]
                and row["version_id"] == values["version_id"]
            ]
            rows.sort(key=lambda row: (row["authority_kind"], row["event_sequence"]))
            return json.dumps(rows, ensure_ascii=False)

        if "INSERT INTO public_statement_challenge_request" in sql:
            row = {
                "request_id": values["request_id"],
                "statement_id": values["statement_id"],
                "version_id": values["version_id"],
                "intake_ref": values["intake_ref"],
                "requester_ref_sha256": values["requester_hash"],
                "reason_sha256": values["reason_hash"],
                "created_at": values["created_at"],
                "integrity_sha256": values["integrity"],
            }
            self.challenge_requests[row["request_id"]] = row
            return values["request_id"]

        if "INSERT INTO public_statement_challenge_event" in sql:
            row = {
                "event_id": values["event_id"],
                "request_id": values["request_id"],
                "event_sequence": int(values["sequence"]),
                "previous_event_id": values["previous_event_id"] or None,
                "previous_integrity_sha256": values["previous_integrity"] or None,
                "status": values["status"],
                "reason_code": values["reason_code"],
                "actor_ref": values["actor_ref"],
                "occurred_at": values["occurred_at"],
                "integrity_sha256": values["integrity"],
            }
            self.challenge_events.append(row)
            return values["event_id"]

        if "FROM public_statement_challenge_request r" in sql:
            rows = []
            for request in self.challenge_requests.values():
                if (request["statement_id"] != values["statement_id"]
                        or request["version_id"] != values["version_id"]):
                    continue
                events = sorted(
                    (row for row in self.challenge_events
                     if row["request_id"] == request["request_id"]),
                    key=lambda row: row["event_sequence"],
                )
                rows.append({**request, "events": events})
            return json.dumps(rows, ensure_ascii=False)

        if "FROM public_statement_challenge_request" in sql and "WHERE request_id" in sql:
            request = self.challenge_requests.get(values["request_id"])
            return json.dumps(request) if request is not None else ""

        if "FROM public_statement_challenge_event" in sql and "WHERE request_id" in sql:
            events = sorted(
                (row for row in self.challenge_events
                 if row["request_id"] == values["request_id"]),
                key=lambda row: row["event_sequence"],
            )
            return json.dumps(events, ensure_ascii=False)

        raise AssertionError(f"unhandled SQL: {sql[:120]}")


def fixture():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    quote = "La misura è stata approvata oggi."
    binding = {
        "statement_id": "statement:senato:1",
        "version_id": "version:senato:1",
        "content_id": "content:senato:1",
        "source_version": "a" * 64,
        "source_sha256": "b" * 64,
        "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
        "person_id": "person:senato:1",
        "speaker_name": "Senatore di prova",
        "statement_date": now.date().isoformat(),
        "span_start": 100,
        "span_end": 100 + len(quote),
        "source_url": "https://www.senato.it/leg/19/assemblea/resoconto.xml",
        "source_title": "Resoconto stenografico Senato",
    }
    item = replace(
        written_candidate(),
        record_id=binding["statement_id"],
        record_version_id=binding["version_id"],
        source_version=binding["source_version"],
        rights_attestation_sha256="c" * 64,
        source_url=binding["source_url"],
        source_kind="WRITTEN",
        snapshot_url="https://www.senato.it/leg/19/assemblea/resoconto.pdf",
        snapshot_sha256="d" * 64,
        source_text_sha256=binding["source_sha256"],
        captured_at=now.isoformat(),
        segment_start=binding["span_start"],
        segment_end=binding["span_end"],
        quote=quote,
        transcript_segment=quote,
        alignment_confidence=None,
        speaker_id=binding["person_id"],
        public_role_source_url="https://www.senato.it/leg/19/assemblea/",
        public_context_source_url="https://www.senato.it/leg/19/assemblea/",
        person_is_minor=False,
        sensitive_third_party_data=False,
        privacy_cleared=True,
        privacy_citation_url="https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        rights_cleared=True,
        rights_citation_url="https://creativecommons.org/licenses/by/4.0/legalcode",
        source_length_chars=1000,
        contains_editorial_judgment=False,
    )
    evidence = candidate_fingerprint(item)

    def review(agent, model, request):
        return AgentReview(
            agent, model, evidence, CHECKS, True,
            provider="omniroute", provider_request_id=request,
            returned_model=model, prompt_sha256=hashlib.sha256(
                (agent + request).encode("utf-8")
            ).hexdigest(),
            usage={"prompt_tokens": 120, "completion_tokens": 45},
        )

    packet = AutonomousProofPacket(
        item,
        review("agent:primary", PRIMARY_MODEL, "completion:primary"),
        review("agent:independent", SECOND_MODEL, "completion:independent"),
    )
    third = review("agent:nightly-audit", THIRD_MODEL, "completion:third-audit")
    return now, binding, packet, third


def disposition(role, review):
    return {
        "role": role,
        "agent_id": review.agent_id,
        "model_id": review.model_id,
        "provider": review.provider,
        "provider_request_id": review.provider_request_id,
        "returned_model": review.returned_model,
        "prompt_sha256": review.prompt_sha256,
        "usage": dict(review.usage),
        "accepted": review.accepted,
        "checked_stages": list(review.checked_stages),
        "evidence_sha256": review.evidence_sha256,
    }


class PublicStatementAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.now, self.binding, self.packet, self.third = fixture()
        self.db = MemoryPostgres()
        self.store = PublicStatementAuthorityStore(store=self.db)
        self.expiry = (self.now + timedelta(days=7)).isoformat()
        self.verify = lambda row: row.get("review_event_id", "").startswith("review:")

    def append(self, kind, payload, *, evidence=None, review_packet=None,
               review_event_id=None, status="APPROVED", expiry=None, verify=None):
        return self.store.append_event(
            binding=self.binding,
            authority_kind=kind,
            status=status,
            payload=payload,
            reviewer_ref=f"reviewer:{kind.lower()}",
            reviewed_at=self.now.isoformat(),
            review_event_id=review_event_id,
            review_evidence=evidence,
            review_packet=review_packet,
            expires_at=self.expiry if expiry is None and status == "APPROVED" else expiry,
            verify_authority_review=self.verify if verify is None else verify,
        )

    def append_all(self, *, release_dispositions=None):
        self.append("RIGHTS", {
            "use_scope": "PUBLIC_EXACT_EXCERPT",
            "policy_version": "dp468-public-quote-rights-v1",
            "jurisdiction": "IT",
            "license_id": "CC-BY-4.0",
            "terms_url": "https://creativecommons.org/licenses/by/4.0/legalcode",
            "terms_sha256": "e" * 64,
            "attribution_required": True,
            "attribution_text": "Fonte: Senato della Repubblica, resoconto stenografico.",
            "source_rights_ref": "rights-review:senato:exact-quote",
        }, evidence={"evidence_refs": ["evidence:rights"]},
           review_event_id="review:rights")
        self.append("PRIVACY", {
            "lawful_basis": "GDPR_ART_6_1_F",
            "special_category_data": True,
            "special_category_condition": "GDPR_ART_9_2_E",
            "manifestly_made_public_by_subject": True,
            "necessity_ref": "privacy:necessity",
            "balancing_ref": "privacy:balancing",
            "notice_receipt": "privacy:notice",
            "contact_channel_ref": "privacy:contact",
            "access_receipt": "privacy:access",
            "retention_policy_version": "dp468-public-statement-retention-v1",
            "purpose": "Public interest reporting of a source-bound public statement.",
            "data_minimization_ref": "privacy:minimization",
            "third_party_data_cleared": True,
        }, evidence={"evidence_refs": ["evidence:privacy"]},
           review_event_id="review:privacy")
        self.append("RETENTION", {
            "policy_version": "dp468-public-statement-retention-v1",
            "retention_class": "PUBLIC_HISTORICAL_STATEMENT",
            "source_capture_scope": "PRIVATE_ONLY",
            "deletion_trigger": "Source right revoked or correction/retraction upheld.",
            "review_due_at": (self.now + timedelta(days=90)).isoformat(),
        }, evidence={"evidence_refs": ["evidence:retention"]},
           review_event_id="review:retention")
        self.append("ATTRIBUTION", {
            "speaker_name": self.binding["speaker_name"],
            "official_person_uri": "https://www.senato.it/leg/19/assemblea/",
            "public_role_source_url": "https://www.senato.it/leg/19/assemblea/",
        }, review_packet=self.packet)
        self.append("CONTEXT", {
            "speech_act": "DIRECT_ASSERTION",
            "endorsed": True,
            "source_session_ref": "senato-session:2026-10-31",
        }, review_packet=self.packet)
        self.append("WORDING", {
            "method": "SOURCE_TEXT_VERIFIED",
            "language": "it",
            "source_kind": "WRITTEN",
        }, review_packet=self.packet)
        first, second = self.packet.primary, self.packet.independent
        evidence = {
            "evidence_refs": ["audit:nightly:2026-11-01"],
            "release_dispositions": release_dispositions or [
                disposition("PRIMARY_REVIEW", first),
                disposition("INDEPENDENT_REVIEW", second),
                disposition("THIRD_AUDIT", self.third),
            ],
        }
        self.append("PUBLICATION", {
            "automatic_authorization_ref": "owner-decision:2026-10-31-publication",
            "release_pin_id": "release-pin:dp468:first-batch",
            "readback_required": True,
        }, evidence=evidence, review_packet=self.packet,
           review_event_id="review:publication")

    def test_all_seven_current_authorities_require_two_reviews_and_third_audit(self):
        self.append_all()
        result = self.store.current_attestations(
            binding=self.binding, review_packet=self.packet,
            verify_authority_review=self.verify, now=self.now,
        )
        self.assertEqual(
            set(result),
            {"rights", "privacy", "retention", "attribution", "context", "wording", "publication"},
        )
        self.assertEqual(result["publication"]["release_pin_id"], "release-pin:dp468:first-batch")
        self.assertEqual(result["context"]["speech_act"], "DIRECT_ASSERTION")

    def test_missing_or_unverified_external_authority_never_projects(self):
        with self.assertRaisesRegex(ValueError, "DP468_EXTERNAL_AUTHORITY_REVIEW_INVALID"):
            self.append("RIGHTS", {
                "use_scope": "PUBLIC_EXACT_EXCERPT",
                "policy_version": "dp468-public-quote-rights-v1",
                "jurisdiction": "IT", "license_id": "CC-BY-4.0",
                "terms_url": "https://creativecommons.org/licenses/by/4.0/legalcode",
                "terms_sha256": "e" * 64, "attribution_required": True,
                "attribution_text": "Fonte: Senato.", "source_rights_ref": "rights:exact",
            }, evidence={"evidence_refs": ["evidence:rights"]},
               review_event_id="review:rights", verify=lambda _row: False)
        self.assertEqual(len(self.db.authority_events), 0)

    def test_local_model_claim_without_actual_provider_receipt_is_rejected(self):
        invalid = replace(
            self.packet.primary,
            provider=None, provider_request_id=None, returned_model=None,
            prompt_sha256=None, usage=None,
        )
        packet = replace(self.packet, primary=invalid)
        with self.assertRaisesRegex(ValueError, "DP468_MODEL_REVIEW_RECEIPT_INVALID"):
            self.append("ATTRIBUTION", {
                "speaker_name": self.binding["speaker_name"],
                "official_person_uri": "https://www.senato.it/leg/19/assemblea/",
                "public_role_source_url": "https://www.senato.it/leg/19/assemblea/",
            }, review_packet=packet)

    def test_publication_requires_three_distinct_authorized_model_dispositions(self):
        repeated = [
            disposition("PRIMARY_REVIEW", self.packet.primary),
            disposition("INDEPENDENT_REVIEW", self.packet.independent),
            disposition("THIRD_AUDIT", self.packet.primary),
        ]
        with self.assertRaisesRegex(ValueError, "DP468_RELEASE_DISPOSITIONS_NOT_INDEPENDENT"):
            self.append_all(release_dispositions=repeated)
        self.assertFalse(any(
            row["authority_kind"] == "PUBLICATION" for row in self.db.authority_events
        ))

    def test_expiry_and_current_source_binding_are_rechecked_on_every_read(self):
        self.append_all()
        expired = self.now + timedelta(days=8)
        self.assertIsNone(self.store.current_attestations(
            binding=self.binding, review_packet=self.packet,
            verify_authority_review=self.verify, now=expired,
        ))
        changed = {**self.binding, "quote_sha256": "f" * 64}
        self.assertIsNone(self.store.current_attestations(
            binding=changed, review_packet=self.packet,
            verify_authority_review=self.verify, now=self.now,
        ))

    def test_later_rights_revocation_invalidates_the_public_version(self):
        self.append_all()
        self.append(
            "RIGHTS", {"reason_code": "SOURCE_RIGHTS_REVOKED"},
            status="REVOKED", expiry=None,
        )
        self.assertIsNone(self.store.current_attestations(
            binding=self.binding, review_packet=self.packet,
            verify_authority_review=self.verify, now=self.now,
        ))

    def test_tampered_authority_event_hash_fails_closed(self):
        self.append_all()
        self.db.authority_events[0]["payload"]["license_id"] = "OTHER"
        self.assertIsNone(self.store.current_attestations(
            binding=self.binding, review_packet=self.packet,
            verify_authority_review=self.verify, now=self.now,
        ))

    def test_authority_insert_requires_exact_database_readback(self):
        self.db.wrong_return = True
        with self.assertRaisesRegex(ValueError, "DP468_AUTHORITY_EVENT_NOT_PERSISTED"):
            self.append("RIGHTS", {
                "use_scope": "PUBLIC_EXACT_EXCERPT",
                "policy_version": "dp468-public-quote-rights-v1",
                "jurisdiction": "IT", "license_id": "CC-BY-4.0",
                "terms_url": "https://creativecommons.org/licenses/by/4.0/legalcode",
                "terms_sha256": "e" * 64, "attribution_required": True,
                "attribution_text": "Fonte: Senato.", "source_rights_ref": "rights:exact",
            }, evidence={"evidence_refs": ["evidence:rights"]},
               review_event_id="review:rights")


class PublicStatementAuthorityMigrationTests(unittest.TestCase):
    def test_private_append_only_migration_has_required_constraints(self):
        root = Path(__file__).resolve().parents[1]
        migration = (root / "db/migrations/20261101-add-public-statement-authority-ledgers.sql").read_text()
        self.assertIn("CHECK (status <> 'APPROVED' OR expires_at IS NOT NULL)", migration)
        self.assertGreaterEqual(migration.count("previous_integrity_sha256 IS NOT NULL"), 2)
        self.assertIn("record_visibility text NOT NULL DEFAULT 'PRIVATE' CHECK (record_visibility = 'PRIVATE')", migration)
        self.assertIn("BEFORE UPDATE OR DELETE ON", migration)
        self.assertIn("BEFORE TRUNCATE ON", migration)
        self.assertIn("CHECK (event_sequence <> 1 OR status = 'OPEN')", migration)
        for table in (
            "public_statement_authority_event",
            "public_statement_challenge_request",
            "public_statement_challenge_event",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", migration)


if __name__ == "__main__":
    unittest.main()
