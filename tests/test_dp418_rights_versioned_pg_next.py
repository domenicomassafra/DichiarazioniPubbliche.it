"""DP-418 versioned source-rights withdrawal integration regression."""

import unittest

from tests.test_dp418_persisted_decision_pg_next import PersistedDecisionPgTests


class CandidateRegistryWithdrawalTests(unittest.TestCase):
    """A versioned rights withdrawal must veto both writes and signed replays."""

    def test_superseded_private_rights_block_a_signed_decision_replay(self):
        PersistedDecisionPgTests.setUpClass()
        fixture = PersistedDecisionPgTests(
            "test_actual_pg_receipt_restart_replay_and_missing_identity_hold"
        )
        try:
            fixture.setUp()
            try:
                rights = fixture.rights
                subject = fixture.rights_subject
                first = rights.read_current(subject)
                request = fixture.request(decision="REVIEW_CREATE")
                event, receipt = fixture.sign(request, "alice")
                kwargs = dict(authority=fixture.authority, review_event=event,
                              authority_receipt_id=receipt, credential_id="alice")
                self.assertEqual(fixture.store.record(request, **kwargs)["result_code"], "CREATED")
                rights.record_rights(
                    subject=subject, policy_version="dp418-fixture-v1",
                    rights_status="REVOKED", rights_receipt_ref="fixture:withdrawn",
                    permitted_uses=(), reviewed_at="2026-10-13T00:00:00Z",
                    expires_at="2026-11-23T00:00:00Z", reviewer_ref="fixture:reviewer",
                    supersedes_record_id=first.id,
                )
                # The cached Capture and Content statuses intentionally stay CLEARED.
                self.assertEqual(fixture.store.run(
                    "SELECT rights_status FROM content_capture WHERE id='capture:review';"
                ).strip(), "CLEARED")
                held = fixture.store.record(request, **kwargs)
                self.assertEqual(held["result_code"], "HELD_SOURCE")
                self.assertIsNone(held["receipt_sha256"])
                fresh = fixture.request(
                    request_key="request:after-revocation", actor="bob"
                )
                fresh_event, fresh_receipt = fixture.sign(fresh, "bob")
                denied = fixture.store.record(
                    fresh, authority=fixture.authority, review_event=fresh_event,
                    authority_receipt_id=fresh_receipt, credential_id="bob",
                )
                self.assertEqual(denied["result_code"], "HELD_SOURCE")
                self.assertIsNone(denied["receipt_sha256"])
                self.assertEqual(fixture.pg_row_count(), 1)
                from dichiarazioni_pubbliche.studio_local_api import _StudioDecisionReader
                readback = _StudioDecisionReader(fixture.pg.dsn).read_decision(
                    candidate_id=request.candidate_id, run_id=request.run_id,
                    passage_id=request.passage_id, capture_id=request.capture_id,
                    request_key=request.request_key,
                )
                self.assertEqual(readback["status"], "HISTORICAL_SOURCE_WITHDRAWN")
                self.assertFalse(readback["review_authority"])
            finally:
                fixture.tearDown()
        finally:
            PersistedDecisionPgTests.tearDownClass()



if __name__ == "__main__":
    unittest.main()
