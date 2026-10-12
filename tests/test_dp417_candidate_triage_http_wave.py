"""Actual authenticated Studio loopback and PostgreSQL candidate-queue path."""
from __future__ import annotations

import json

from tests.test_studio_auth_vertical_next import StudioAuthVerticalNextTests


class CandidateQueueHttpWaveTests(StudioAuthVerticalNextTests):
    def test_candidate_queue_requires_token_and_fences_pg_rights_revocation(self):
        path = "/v1/discovery/candidate-queue"
        body = {"collection_id": "collection:one", "limit": 1}
        self.assertEqual(self.request(path, body, auth=False)[0], 401)
        self.assertEqual(self.request(path, body, origin="https://evil.invalid")[0], 403)
        status, packet, headers = self.request(path, body)
        self.assertEqual(status, 200, packet)
        payload = packet["data"]
        self.assertEqual(payload["contract_version"], "studio-statement-candidate-queue-pg-v1")
        self.assertEqual(payload["rows"][0]["candidate_id"], "statement:vertical-a")
        self.assertEqual(payload["rows"][0]["passage_id"], "passage:vertical")
        self.assertEqual(payload["rows"][0]["capture_id"], "capture:one-new")
        self.assertFalse(payload["publication_authority"])
        self.assertFalse(payload["triage_action_authorized"])
        self.assertEqual(headers["Cache-Control"], "no-store, private")
        for secret in ("SECRET PRIVATE QUOTE", "SECRET NORMALIZED", "PRIVATE PASSPHRASE",
                       "https://private.example", "SECRET SOURCE"):
            self.assertNotIn(secret, json.dumps(packet))
        second = body | {
            "after_candidate_id": payload["next_after_candidate_id"],
            "expected_snapshot_sha256": payload["snapshot_sha256"],
        }
        self.assertEqual(self.request(path, second)[0], 200)
        self.assertEqual(self.request(path, second | {"publish": True})[0], 422)
        self.assertEqual(self.request(path, body | {
            "after_candidate_id": payload["next_after_candidate_id"]
        })[0], 422)
        self.pg.store.run(
            "UPDATE content_item SET rights_status='REVOKED' WHERE id='content:one'"
        )
        self.assertEqual(self.request(path, second)[0], 422)
        new_status, new_packet, _ = self.request(path, body)
        self.assertEqual(new_status, 200)
        self.assertIn("CONTENT_RIGHTS_REVOKED", new_packet["data"]["rows"][0]["blockers"])
        self.assertEqual(new_packet["data"]["rows"][0]["state"], "BLOCKED")
