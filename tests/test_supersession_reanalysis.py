import hashlib
import sys
import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.source_revalidation import (  # noqa: E402
    RevalidationDisposition,
    SourceSnapshot,
    evaluate_reobservation,
)
from dichiarazioni_pubbliche.supersession_reanalysis import (  # noqa: E402
    SUPERSESSION_TRIGGER_SOURCE_TYPE,
    SupersessionReanalysisError,
    build_reviewed_supersession_reanalysis_request,
)


SHA_A = hashlib.sha256(b"law version 1").hexdigest()
SHA_B = hashlib.sha256(b"law version 2").hexdigest()
NOW = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)


def snapshots():
    previous = SourceSnapshot(
        source_id="source:official:law:1",
        observed_at=NOW,
        availability="AVAILABLE",
        content_sha256=SHA_A,
        source_version="law-v1",
        etag='"law-v1"',
        canonical_url="https://example.test/law/1",
        rights_status="CLEARED",
    )
    current = replace(
        previous,
        observed_at=NOW.replace(hour=21),
        content_sha256=SHA_B,
        source_version="law-v2",
        supersedes_version="law-v1",
        etag='"law-v2"',
    )
    return previous, current


def supersession_decision(previous, current, *, load_bearing=True):
    return evaluate_reobservation(
        previous,
        current,
        as_of=date(2026, 10, 5),
        load_bearing_for_evidence=load_bearing,
    )


def build_request(**overrides):
    previous, current = snapshots()
    decision = supersession_decision(previous, current)
    values = dict(
        decision=decision,
        previous=previous,
        current=current,
        review_event_id="review:supersession:law-v1:law-v2",
        review_action="APPROVED",
        reviewed_entity_ref=decision.event_key,
        previous_valid_from="2024-01-01",
        previous_valid_until="2026-10-01",
        current_valid_from="2026-10-01",
        current_valid_until=None,
        affected_claim_ids=("claim:b", "claim:a", "claim:a"),
        affected_finding_ids=("finding:2", "finding:1", "finding:1"),
    )
    values.update(overrides)
    if "decision" in overrides and "reviewed_entity_ref" not in overrides:
        values["reviewed_entity_ref"] = values["decision"].event_key
    return build_reviewed_supersession_reanalysis_request(**values)


class ReviewedSupersessionReanalysisTests(unittest.TestCase):
    def test_reviewed_load_bearing_supersession_emits_one_trigger_per_claim(self):
        request = build_request()

        self.assertEqual(request.affected_claim_ids, ("claim:a", "claim:b"))
        self.assertEqual(request.affected_finding_ids, ("finding:1", "finding:2"))
        self.assertEqual(request.previous.source_id, "source:official:law:1")
        self.assertEqual(request.previous.version_id, "law-v1")
        self.assertEqual(request.previous.content_sha256, SHA_A)
        self.assertEqual(request.previous.valid_from, "2024-01-01")
        self.assertEqual(request.previous.valid_until, "2026-10-01")
        self.assertEqual(request.current.version_id, "law-v2")
        self.assertEqual(request.current.content_sha256, SHA_B)
        self.assertEqual(request.current.valid_from, "2026-10-01")
        self.assertIsNone(request.current.valid_until)
        self.assertEqual(len(request.triggers), 2)
        self.assertEqual(len(request.reanalysis_job_ids), 2)
        self.assertEqual(
            tuple(trigger.claim_id for trigger in request.triggers),
            ("claim:a", "claim:b"),
        )
        for trigger in request.triggers:
            self.assertEqual(trigger.trigger_type, "MANUAL_REVIEW")
            self.assertEqual(trigger.source_type, SUPERSESSION_TRIGGER_SOURCE_TYPE)
            self.assertEqual(trigger.source_id, request.request_id)
            self.assertEqual(trigger.source_hash, SHA_B)

    def test_exact_replay_is_idempotent(self):
        self.assertEqual(build_request(), build_request())

    def test_fingerprint_binds_effective_dates_and_affected_finding_ids(self):
        baseline = build_request()
        later_cutover = build_request(
            previous_valid_until="2026-10-02",
            current_valid_from="2026-10-02",
        )
        different_finding = build_request(affected_finding_ids=("finding:3",))

        self.assertNotEqual(baseline.request_id, later_cutover.request_id)
        self.assertNotEqual(baseline.request_id, different_finding.request_id)
        self.assertNotEqual(
            tuple(trigger.trigger_id for trigger in baseline.triggers),
            tuple(trigger.trigger_id for trigger in later_cutover.triggers),
        )

    def test_fingerprint_binds_old_and_new_version_hashes(self):
        baseline = build_request()
        previous, current = snapshots()
        changed_previous = replace(
            previous,
            content_sha256=hashlib.sha256(b"law version 1 corrected").hexdigest(),
        )
        changed_previous_request = build_request(
            previous=changed_previous,
            current=current,
            decision=supersession_decision(changed_previous, current),
        )
        changed_current = replace(
            current,
            content_sha256=hashlib.sha256(b"law version 2 corrected").hexdigest(),
        )
        changed = build_request(
            previous=previous,
            current=changed_current,
            decision=supersession_decision(previous, changed_current),
        )

        self.assertNotEqual(baseline.request_id, changed_previous_request.request_id)
        self.assertNotEqual(baseline.request_id, changed.request_id)
        self.assertNotEqual(
            baseline.previous.content_sha256,
            changed_previous_request.previous.content_sha256,
        )
        self.assertNotEqual(baseline.current.content_sha256, changed.current.content_sha256)

    def test_fingerprint_binds_old_and_new_version_ids(self):
        previous, current = snapshots()
        baseline = build_request()
        changed_current = replace(
            current,
            source_version="law-v2-corrected",
        )
        changed = build_request(
            previous=previous,
            current=changed_current,
            decision=supersession_decision(previous, changed_current),
        )

        self.assertNotEqual(baseline.request_id, changed.request_id)
        self.assertNotEqual(baseline.current.version_id, changed.current.version_id)

    def test_unapproved_review_cannot_create_reanalysis_request(self):
        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "APPROVED_REVIEW_REQUIRED",
        ):
            build_request(review_action="PENDING")

    def test_review_must_target_exact_revalidation_event(self):
        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "REVIEW_TARGET_MISMATCH",
        ):
            build_request(reviewed_entity_ref="0" * 64)

    def test_non_load_bearing_supersession_cannot_create_reanalysis_request(self):
        previous, current = snapshots()
        decision = supersession_decision(previous, current, load_bearing=False)
        self.assertEqual(decision.disposition, RevalidationDisposition.REVIEW_REQUIRED)

        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "LOAD_BEARING_HOLD_REQUIRED",
        ):
            build_request(previous=previous, current=current, decision=decision)

    def test_material_change_without_direct_supersession_cannot_trigger(self):
        previous, current = snapshots()
        changed = replace(current, supersedes_version=None)
        decision = supersession_decision(previous, changed)
        self.assertNotIn("OFFICIAL_VERSION_SUPERSEDED", decision.material_change_codes)

        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "OFFICIAL_SUPERSESSION_REQUIRED",
        ):
            build_request(previous=previous, current=changed, decision=decision)

    def test_snapshot_decision_mismatch_fails_closed(self):
        previous, current = snapshots()
        decision = supersession_decision(previous, current)
        tampered_current = replace(current, canonical_url="https://example.test/law/renamed")

        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "CURRENT_SNAPSHOT_REF_MISMATCH",
        ):
            build_request(
                previous=previous,
                current=tampered_current,
                decision=decision,
            )

    def test_tampered_decision_event_key_fails_closed(self):
        previous, current = snapshots()
        decision = supersession_decision(previous, current)

        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "DECISION_EVENT_KEY_MISMATCH",
        ):
            build_request(
                previous=previous,
                current=current,
                decision=replace(decision, event_key="0" * 64),
            )

    def test_at_least_one_affected_claim_is_required(self):
        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "AFFECTED_CLAIM_ID_REQUIRED",
        ):
            build_request(affected_claim_ids=())

    def test_effective_intervals_fail_closed(self):
        with self.assertRaisesRegex(
            SupersessionReanalysisError,
            "PREVIOUS_EFFECTIVE_INTERVAL_INVALID",
        ):
            build_request(
                previous_valid_from="2026-10-01",
                previous_valid_until="2026-10-01",
            )


if __name__ == "__main__":
    unittest.main()
