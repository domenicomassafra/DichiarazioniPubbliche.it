import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.review_admin import (  # noqa: E402
    approve_relation_candidate,
    approve_person_role_interval,
    add_speaker_candidate,
    add_text_provenance_candidate,
    approve_evidence,
    approve_observation,
    approve_speaker_candidate,
    approve_text_provenance_candidate,
    deterministic_review_event_id,
    enqueue_reanalysis_trigger,
    enqueue_verification,
    publish_finding,
    publish_correction,
    publish_right_of_reply,
    record_correction,
    record_right_of_reply,
    register_person,
    register_organization,
)


class FakeStore:
    def __init__(self):
        self.events = []
        self.followups = []
        self.people = []
        self.speaker_candidates = []
        self.text_provenance_candidates = []
        self.replies = []
        self.corrections = []
        self.organizations = []
        self.role_intervals = []

    def approve_claim_evidence_with_review(self, **kwargs):
        self.events.append(
            {
                **kwargs,
                "entity_type": "CLAIM_EVIDENCE_CANDIDATE",
                "action": "APPROVED",
            }
        )
        return True

    def approve_evidence_observation_with_review(self, **kwargs):
        self.events.append(
            {
                **kwargs,
                "entity_type": "EVIDENCE_OBSERVATION",
                "action": "APPROVED",
            }
        )
        return True

    def claim_context(self, claim_id):
        return {
            "claim_id": claim_id,
            "content_id": "content:a",
            "statement_date": "2026-09-21",
        }

    def finding_context(self, finding_id):
        return {
            "finding_id": finding_id,
            "claim_id": "claim:a",
            "content_id": "content:a",
            "publication_status": "PUBLISH",
            "supersedes_id": None,
        }

    def enqueue_followup(self, **kwargs):
        self.followups.append(kwargs)
        return "job:test", True

    def register_public_person(self, **kwargs):
        self.people.append(kwargs)
        return True

    def register_organization(self, **kwargs):
        self.organizations.append(kwargs)
        return True

    def approve_person_role_interval_with_review(self, **kwargs):
        self.role_intervals.append(kwargs)
        return True

    def insert_speaker_identity_candidate(self, **kwargs):
        self.speaker_candidates.append(kwargs)
        return True

    def approve_speaker_identity_with_review(self, **kwargs):
        self.events.append(
            {
                **kwargs,
                "entity_type": "SPEAKER_IDENTITY_CANDIDATE",
                "action": "APPROVED",
            }
        )
        return True

    def insert_claim_text_provenance(self, **kwargs):
        self.text_provenance_candidates.append(kwargs)
        return True

    def approve_claim_text_provenance_with_review(self, **kwargs):
        self.events.append(
            {
                **kwargs,
                "entity_type": "CLAIM_TEXT_PROVENANCE",
                "action": "APPROVED",
            }
        )
        return True

    def publish_finding_with_review(self, **kwargs):
        self.events.append(
            {
                **kwargs,
                "entity_type": "FINDING",
                "action": "APPROVED",
            }
        )
        return True

    def insert_right_of_reply(self, **kwargs):
        self.replies.append(kwargs)
        return True

    def attach_reply_reanalysis_job(self, **kwargs):
        if not self.replies:
            return False
        self.replies[-1]["reanalysis_job_id"] = kwargs["job_id"]
        return True

    def publish_right_of_reply_with_review(self, **kwargs):
        self.events.append(
            {
                **kwargs,
                "entity_type": "RIGHT_OF_REPLY",
                "action": "APPROVED",
            }
        )
        return True

    def insert_correction(self, **kwargs):
        self.corrections.append(kwargs)
        return True

    def publish_correction_with_review(self, **kwargs):
        self.events.append(
            {
                **kwargs,
                "entity_type": "CORRECTION",
                "action": "APPROVED",
            }
        )
        return True


class ReviewAdminTests(unittest.TestCase):
    def test_relation_approval_refuses_without_store_acceptance(self):
        class RefusingStore:
            def approve_relation_candidate_with_review(self, **variables):
                return None

        with self.assertRaisesRegex(
            RuntimeError, "RELATION_APPROVAL_GUARD_REFUSED"
        ):
            approve_relation_candidate(
                RefusingStore(),
                relation_id="relation:a",
                actor_ref="reviewer",
                reason="checked both statements",
                trigger_reanalysis=False,
            )

    def test_relation_approval_triggers_reanalysis_on_both_endpoint_claims(self):
        from dichiarazioni_pubbliche.review_admin import approve_relation_candidate

        class CaptureStore:
            def __init__(self):
                self.approved = None
                self.triggers = []

            def approve_relation_candidate_with_review(self, **variables):
                self.approved = variables
                return {
                    "relation_id": "relation:a",
                    "subject_claim_id": "claim:a",
                    "object_claim_id": "claim:b",
                }

            def claim_context(self, claim_id):
                return {"content_id": f"content:{claim_id[-1]}"}

            def enqueue_followup(self, **variables):
                self.triggers.append(variables)
                return f"job:{variables['content_id']}", None

        store = CaptureStore()
        event_id = approve_relation_candidate(
            store,
            relation_id="relation:a",
            actor_ref="reviewer",
            reason="checked both statements",
        )
        self.assertTrue(event_id.startswith("review:"))
        self.assertEqual(store.approved["relation_id"], "relation:a")
        self.assertEqual(len(store.triggers), 2)
        claims = {
            trigger["payload"]["claim_id"] for trigger in store.triggers
        }
        self.assertEqual(claims, {"claim:a", "claim:b"})
        for trigger in store.triggers:
            self.assertEqual(
                trigger["payload"]["trigger_type"], "RELATION_APPROVED"
            )
            self.assertEqual(trigger["job_type"], "REGISTER_REANALYSIS")

    def test_relation_approval_is_not_publication(self):
        class CaptureStore:
            def __init__(self):
                self.calls = []

            def approve_relation_candidate_with_review(self, **variables):
                self.calls.append(variables)
                return {
                    "relation_id": "relation:a",
                    "subject_claim_id": "claim:a",
                    "object_claim_id": "claim:b",
                }

        store = CaptureStore()
        approve_relation_candidate(
            store,
            relation_id="relation:a",
            actor_ref="reviewer",
            reason=None,
            trigger_reanalysis=False,
        )
        self.assertEqual(len(store.calls), 1)
        self.assertNotIn("publication_status", store.calls[0])
        self.assertFalse(hasattr(store, "publish_finding_with_review"))

    def test_public_role_requires_organization_and_explicit_review(self):
        store = FakeStore()
        organization_id = register_organization(
            store,
            organization_id="org:a",
            canonical_name="Organization A",
            organization_type="PUBLIC_BODY",
            country_code="IT",
            canonical_url="https://example.test/org",
        )
        event_id = approve_person_role_interval(
            store,
            interval_id="role:a",
            person_id="person:a",
            organization_id=organization_id,
            role="Member",
            start_date="2026-01-01",
            end_date=None,
            is_public_role=True,
            source_ref={"url": "https://example.test/role"},
            actor_ref="reviewer",
            reason="source checked",
        )
        self.assertEqual(event_id, store.role_intervals[0]["event_id"])
        self.assertEqual(store.role_intervals[0]["actor_ref"], "reviewer")
        self.assertEqual(len(store.organizations), 1)
    def test_review_event_id_is_idempotent(self):
        kwargs = dict(
            entity_type="EVIDENCE_OBSERVATION",
            entity_id="observation:a",
            action="APPROVED",
            actor_ref="local-operator",
            reason="checked",
        )
        self.assertEqual(
            deterministic_review_event_id(**kwargs),
            deterministic_review_event_id(**kwargs),
        )

    def test_approvals_write_review_ledger(self):
        store = FakeStore()
        approve_evidence(
            store,
            claim_id="claim:a",
            evidence_id="evidence:a",
            retrieval_version="v1",
            actor_ref="reviewer",
            reason="source checked",
        )
        approve_observation(
            store,
            observation_id="observation:a",
            actor_ref="reviewer",
            reason="value checked",
        )
        self.assertEqual(len(store.events), 2)
        self.assertEqual(store.events[0]["action"], "APPROVED")
        self.assertEqual(store.events[1]["entity_type"], "EVIDENCE_OBSERVATION")

    def test_verification_and_reanalysis_are_queued_explicitly(self):
        store = FakeStore()
        enqueue_verification(
            store,
            claim_id="claim:a",
            verification_kind="numeric_exact",
            verification_rule={"metric": "m", "value": 10},
            statement_date=None,
        )
        enqueue_reanalysis_trigger(
            store,
            claim_id="claim:a",
            trigger_type="MANUAL_REVIEW",
            source_type="OPERATOR",
            source_id="review:1",
            source_hash=None,
        )
        self.assertEqual(store.followups[0]["job_type"], "VERIFY_CLAIM")
        self.assertEqual(store.followups[1]["job_type"], "REGISTER_REANALYSIS")

    def test_verification_refuses_statement_date_override(self):
        store = FakeStore()
        with self.assertRaisesRegex(
            RuntimeError,
            "VERIFICATION_STATEMENT_DATE_MISMATCH",
        ):
            enqueue_verification(
                store,
                claim_id="claim:a",
                verification_kind="numeric_exact",
                verification_rule={"metric": "m", "value": 10},
                statement_date="2026-09-22",
            )
        self.assertEqual(store.followups, [])

    def test_speaker_identity_requires_explicit_candidate_and_approval(self):
        store = FakeStore()
        register_person(
            store,
            person_id="person:a",
            canonical_name="Persona A",
            public_role="Public official",
            country_code="IT",
        )
        candidate_id = add_speaker_candidate(
            store,
            content_id="content:a",
            person_id="person:a",
            start_ms=0,
            end_ms=1000,
            attribution_method="MANUAL_REVIEW",
            speaker_label="Speaker 1",
            source_ref={"review": "manual"},
            confidence=1.0,
        )
        event_id = approve_speaker_candidate(
            store,
            candidate_id=candidate_id,
            actor_ref="reviewer",
            reason="source checked",
        )
        self.assertEqual(len(store.people), 1)
        self.assertEqual(len(store.speaker_candidates), 1)
        self.assertTrue(event_id.startswith("review:"))
        self.assertEqual(
            store.events[-1]["entity_type"],
            "SPEAKER_IDENTITY_CANDIDATE",
        )

    def test_text_provenance_requires_explicit_candidate_and_approval(self):
        store = FakeStore()
        candidate_id = add_text_provenance_candidate(
            store,
            claim_id="claim:a",
            content_id="content:a",
            person_id="person:a",
            selector_type="TEXT_QUOTE_HASH",
            quote_sha256="a" * 64,
            source_sha256="b" * 64,
            start_char=None,
            end_char=None,
            attribution_method="SOURCE_QUOTE",
            source_ref={"url": "https://example.test/article"},
        )
        event_id = approve_text_provenance_candidate(
            store,
            candidate_id=candidate_id,
            actor_ref="reviewer",
            reason="source quote checked",
        )
        self.assertEqual(len(store.text_provenance_candidates), 1)
        self.assertTrue(candidate_id.startswith("text-provenance:"))
        self.assertTrue(event_id.startswith("review:"))
        self.assertEqual(store.events[-1]["entity_type"], "CLAIM_TEXT_PROVENANCE")

    def test_finding_publication_is_explicit_review_action(self):
        store = FakeStore()
        event_id = publish_finding(
            store,
            finding_id="finding:a",
            actor_ref="reviewer",
            reason="publication gate checked",
        )
        self.assertTrue(event_id.startswith("review:"))
        self.assertEqual(store.events[-1]["entity_type"], "FINDING")
        self.assertEqual(store.events[-1]["action"], "APPROVED")

    def test_right_of_reply_is_private_and_enqueues_reanalysis_before_publication(self):
        store = FakeStore()
        reply_id = record_right_of_reply(
            store,
            finding_id="finding:a",
            submitter_name="Persona",
            submitter_role="Ruolo",
            body="Replica documentata.",
            evidence_urls=["https://example.test/reply-evidence"],
        )
        self.assertTrue(reply_id.startswith("reply:"))
        self.assertEqual(store.replies[0]["finding_id"], "finding:a")
        self.assertEqual(store.followups[0]["job_type"], "REGISTER_REANALYSIS")
        self.assertEqual(
            store.followups[0]["payload"]["trigger_type"],
            "RIGHT_OF_REPLY",
        )
        self.assertIn("reanalysis_job_id", store.replies[0])

        event_id = publish_right_of_reply(
            store,
            reply_id=reply_id,
            actor_ref="reviewer",
            reason="reply reviewed",
        )
        self.assertTrue(event_id.startswith("review:"))
        self.assertEqual(store.events[-1]["entity_type"], "RIGHT_OF_REPLY")

    def test_correction_requires_superseding_chain_and_explicit_publication(self):
        store = FakeStore()
        correction_id = record_correction(
            store,
            finding_id="finding:new",
            previous_finding_id="finding:old",
            reason="New approved evidence changed the result.",
            changed_fields={"assessment": ["SUPPORTED", "OUTDATED_DATA"]},
        )
        self.assertTrue(correction_id.startswith("correction:"))
        self.assertEqual(
            store.corrections[0]["previous_finding_id"],
            "finding:old",
        )
        self.assertEqual(store.followups[0]["job_type"], "REGISTER_REANALYSIS")
        self.assertEqual(
            store.followups[0]["payload"]["trigger_type"],
            "CORRECTION",
        )
        event_id = publish_correction(
            store,
            correction_id=correction_id,
            actor_ref="reviewer",
            reason="correction chain checked",
        )
        self.assertTrue(event_id.startswith("review:"))
        self.assertEqual(store.events[-1]["entity_type"], "CORRECTION")


if __name__ == "__main__":
    unittest.main()
