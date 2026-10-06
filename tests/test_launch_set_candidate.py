import json
import sys
import unittest
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.launch_set_candidate import (  # noqa: E402
    LaunchSetCandidateError,
    build_launch_snapshot_candidate,
    build_rollback_receipt_candidate,
    validate_launch_set_candidate,
)


FIXTURE = ROOT / "tests" / "fixtures" / "launch-set-candidate-preflight-v1.json"


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def snapshot(manifest, *, config="d" * 64, projection="e" * 64):
    return build_launch_snapshot_candidate(
        manifest=manifest,
        candidate_commit="a" * 40,
        effective_config_sha256=config,
        policy_version="policy-v1",
        public_schema_version="public-v1",
        api_version="api-v1",
        public_projection_sha256=projection,
    )


class LaunchSetCandidateTests(unittest.TestCase):
    def test_three_family_candidate_is_mechanically_ready_but_never_launch_authorized(self):
        manifest = validate_launch_set_candidate(fixture()["three_family_candidate"])

        self.assertEqual(manifest.candidate_status, "READY_FOR_OWNER_REVIEW")
        self.assertEqual(manifest.included_source_families, ("family-a", "family-b", "family-c"))
        self.assertEqual(len(manifest.included_source_ids), 3)
        self.assertEqual(manifest.held_count, 1)
        self.assertEqual(manifest.omitted_count, 1)
        self.assertEqual(manifest.launch_state, "BLOCKED")
        self.assertFalse(manifest.launch_authorized)

    def test_all_held_is_valid_history_but_candidate_preflight_stays_blocked(self):
        manifest = validate_launch_set_candidate(fixture()["all_held"])

        self.assertEqual(manifest.candidate_status, "BLOCKED")
        self.assertIn("NO_INCLUDED_SOURCES", manifest.blockers)
        self.assertTrue(any(code.startswith("INCLUDED_SOURCE_FAMILY_MINIMUM_NOT_MET") for code in manifest.blockers))
        self.assertEqual(manifest.held_count, 3)
        self.assertFalse(manifest.launch_authorized)

    def test_blocked_provider_rights_or_privacy_cannot_be_included(self):
        base = fixture()["three_family_candidate"][0]
        for field in ("provider_state", "rights_state", "privacy_state"):
            with self.subTest(field=field):
                row = dict(base)
                row[field] = "BLOCKED"
                with self.assertRaisesRegex(LaunchSetCandidateError, "NOT_READY"):
                    validate_launch_set_candidate([row])

    def test_blocked_fixture_is_valid_only_as_explicit_held_candidate(self):
        blocked = fixture()["blocked"]
        manifest = validate_launch_set_candidate([blocked])

        self.assertEqual(manifest.rows[0].state.value, "HELD")
        self.assertEqual(manifest.rows[0].provider_state.value, "BLOCKED")
        self.assertEqual(manifest.candidate_status, "BLOCKED")
        included = dict(blocked)
        included["state"] = "INCLUDED"
        ready = fixture()["three_family_candidate"][0]
        for field in (
            "rights_decision_ref",
            "privacy_decision_ref",
            "policy_decision_ref",
            "discovery_path_id",
            "transcript_path_id",
            "speaker_path_id",
            "evidence_path_id",
            "health_owner",
            "disclosure_decision_ref",
            "config_sha256",
        ):
            included[field] = ready[field]
        with self.assertRaisesRegex(LaunchSetCandidateError, "NOT_READY"):
            validate_launch_set_candidate([included])

    def test_included_requires_every_reference_path_owner_and_config_hash(self):
        base = fixture()["three_family_candidate"][0]
        required = (
            "rights_decision_ref",
            "privacy_decision_ref",
            "policy_decision_ref",
            "discovery_path_id",
            "transcript_path_id",
            "speaker_path_id",
            "evidence_path_id",
            "provider_path_id",
            "health_owner",
            "disclosure_decision_ref",
            "config_sha256",
        )
        for field in required:
            with self.subTest(field=field):
                row = dict(base)
                row[field] = None
                with self.assertRaisesRegex(LaunchSetCandidateError, "REQUIRED"):
                    validate_launch_set_candidate([row])

    def test_duplicate_source_id_and_unknown_private_fields_fail_closed(self):
        base = fixture()["three_family_candidate"][0]
        with self.assertRaisesRegex(LaunchSetCandidateError, "SOURCE_ID_DUPLICATE"):
            validate_launch_set_candidate([base, base])
        private = dict(base)
        private["raw_transcript_body"] = "must never enter manifest"
        with self.assertRaisesRegex(LaunchSetCandidateError, "ROW_UNKNOWN_FIELDS"):
            validate_launch_set_candidate([private])

    def test_manifest_fingerprint_is_deterministic_and_order_independent(self):
        rows = fixture()["three_family_candidate"]
        first = validate_launch_set_candidate(rows)
        replay = validate_launch_set_candidate(list(reversed(rows)))

        self.assertEqual(first.manifest_sha256, replay.manifest_sha256)
        self.assertEqual(first.rows, replay.rows)

    def test_changed_source_config_changes_manifest_and_snapshot_hash(self):
        rows = fixture()["three_family_candidate"]
        first_manifest = validate_launch_set_candidate(rows)
        changed_rows = [dict(row) for row in rows]
        changed_rows[0]["config_sha256"] = "f" * 64
        changed_manifest = validate_launch_set_candidate(changed_rows)
        changed_source_rows = [dict(row) for row in rows]
        changed_source_rows[0]["source_id"] = "source:candidate:a:v2"
        changed_source_manifest = validate_launch_set_candidate(changed_source_rows)

        first_snapshot = snapshot(first_manifest)
        changed_source_snapshot = snapshot(changed_manifest)
        changed_source_id_snapshot = snapshot(changed_source_manifest)
        changed_global_config_snapshot = snapshot(first_manifest, config="1" * 64)
        self.assertNotEqual(first_manifest.manifest_sha256, changed_manifest.manifest_sha256)
        self.assertNotEqual(first_manifest.manifest_sha256, changed_source_manifest.manifest_sha256)
        self.assertNotEqual(first_snapshot.snapshot_sha256, changed_source_snapshot.snapshot_sha256)
        self.assertNotEqual(first_snapshot.snapshot_sha256, changed_source_id_snapshot.snapshot_sha256)
        self.assertNotEqual(first_snapshot.snapshot_sha256, changed_global_config_snapshot.snapshot_sha256)

    def test_two_included_families_remain_mechanically_blocked(self):
        rows = fixture()["three_family_candidate"][:2]
        manifest = validate_launch_set_candidate(rows)

        self.assertEqual(manifest.candidate_status, "BLOCKED")
        self.assertEqual(manifest.included_source_families, ("family-a", "family-b"))
        self.assertIn("INCLUDED_SOURCE_FAMILY_MINIMUM_NOT_MET:2:3", manifest.blockers)

    def test_snapshot_binds_required_versions_sources_projection_and_counts(self):
        manifest = validate_launch_set_candidate(fixture()["three_family_candidate"])
        candidate = snapshot(manifest)
        replay = snapshot(manifest)

        self.assertEqual(candidate, replay)
        self.assertEqual(candidate.source_ids, tuple(row.source_id for row in manifest.rows))
        self.assertEqual(candidate.included_source_ids, manifest.included_source_ids)
        self.assertEqual(candidate.held_count, 1)
        self.assertEqual(candidate.omitted_count, 1)
        self.assertEqual(candidate.launch_set_manifest_sha256, manifest.manifest_sha256)
        self.assertEqual(candidate.public_projection_sha256, "e" * 64)
        self.assertFalse(candidate.launch_authorized)
        self.assertEqual(candidate.launch_state, "BLOCKED")

    def test_snapshot_model_has_no_raw_body_credential_or_owner_approval_fields(self):
        manifest = validate_launch_set_candidate(fixture()["three_family_candidate"])
        payload = asdict(snapshot(manifest))
        serialized = json.dumps(payload, sort_keys=True).lower()

        for forbidden in (
            "raw_body",
            "transcript_body",
            "evidence_body",
            "credential",
            "secret",
            "password",
            "owner_approved",
            "approved_by_owner",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_rollback_receipt_is_deterministic_nonexecuted_and_non_authorizing(self):
        manifest = validate_launch_set_candidate(fixture()["three_family_candidate"])
        known_good = snapshot(manifest, projection="1" * 64)
        rejected = snapshot(manifest, config="2" * 64, projection="3" * 64)
        first = build_rollback_receipt_candidate(
            rejected_snapshot=rejected,
            restore_target_snapshot=known_good,
            rollback_id="rollback:fixture:1",
            reason_code="SNAPSHOT_REJECTED",
            actor_ref="operator:fixture",
        )
        replay = build_rollback_receipt_candidate(
            rejected_snapshot=rejected,
            restore_target_snapshot=known_good,
            rollback_id="rollback:fixture:1",
            reason_code="SNAPSHOT_REJECTED",
            actor_ref="operator:fixture",
        )

        self.assertEqual(first, replay)
        self.assertEqual(first.execution_state, "NOT_EXECUTED")
        self.assertFalse(first.launch_authorized)
        self.assertEqual(first.expected_projection_sha256, known_good.public_projection_sha256)


if __name__ == "__main__":
    unittest.main()
