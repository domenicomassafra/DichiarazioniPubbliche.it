"""Real PostgreSQL -> signed reviewer -> opt-in loopback -> immutable Candidate history."""
from __future__ import annotations

import dataclasses
import http.client
import json
import threading
import unittest

from dichiarazioni_pubbliche.studio_candidate_decision_store_pg import StudioCandidateDecisionStorePg
from dichiarazioni_pubbliche.studio_local_api import StudioLocalReaders, _StudioDecisionReader
from dichiarazioni_pubbliche.studio_local_mutation_api import StudioTriageMutationServer
from dichiarazioni_pubbliche.studio_discovery_triage_store import StudioDiscoveryTriageStore
from tests.test_dp418_persisted_decision_pg_next import PersistedDecisionPgTests


class CandidateSignedStudioWriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pg = PersistedDecisionPgTests
        cls.pg.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.pg.tearDownClass()

    def setUp(self):
        self.fixture = self.pg("test_actual_pg_receipt_restart_replay_and_missing_identity_hold")
        self.fixture.setUp()
        self.token = "a" * 64
        self.start_server()

    def start_server(self):
        self.server = StudioTriageMutationServer(
            0, StudioLocalReaders(
                None, None, None,
                decision_reader=_StudioDecisionReader(self.pg.pg.dsn),
            ), self.token,
            store=StudioDiscoveryTriageStore(database_url=self.pg.pg.dsn),
            authority=self.fixture.authority,
            candidate_store=StudioCandidateDecisionStorePg(self.pg.pg.dsn),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.stop_server()
        self.fixture.tearDown()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=4)

    def send(self, body, *, token=None, path="/v1/candidate/decision-annotate"):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token is not False:
            headers["Authorization"] = "Bearer " + (token or self.token)
        connection.request("POST", path, json.dumps(body).encode(), headers)
        response = connection.getresponse()
        code = response.status
        data = json.loads(response.read())
        connection.close()
        return code, data

    def signed(self, **changes):
        req = self.fixture.request(request_key="http:case:" + self._testMethodName)
        event, receipt = self.fixture.sign(req, "alice")
        data = dataclasses.asdict(req) | {
            "review_event": dataclasses.asdict(event),
            "authority_receipt_id": receipt,
            "credential_id": "alice",
            "confirm_private_decision": True,
        }
        return data | changes

    def test_signed_postgres_decision_http_replay_restart_and_no_public_authority(self):
        payload = self.signed()
        self.assertEqual(self.send(payload, token=False)[0], 401)
        self.assertEqual(self.send(payload, token="f"*64)[0], 401)
        first = self.send(payload)
        self.assertEqual(first[0], 200, first)
        self.assertEqual(first[1]["data"]["result_code"], "CREATED")
        self.assertFalse(first[1]["data"]["promotion_authority"])
        self.assertFalse(first[1]["data"]["publication_authority"])
        self.assertNotIn("reviewer:alice", json.dumps(first[1]))
        self.assertNotIn(payload["authority_receipt_id"], json.dumps(first[1]))
        self.stop_server()
        self.start_server()
        replay = self.send(payload)
        self.assertEqual(replay[0], 200, replay)
        self.assertEqual(replay[1]["data"]["result_code"], "REPLAY")
        self.assertEqual(self.fixture.pg_row_count(), 1)

    def test_tamper_revoke_and_foreign_scope_do_not_write(self):
        payload = self.signed()
        self.assertEqual(self.send(payload | {"decision":"REJECT"})[0], 422)
        self.assertEqual(self.send(payload | {"unknown":"anything"})[0], 422)
        self.assertEqual(self.send(payload | {"confirm_private_decision":False})[0], 422)
        self.assertEqual(self.fixture.pg_row_count(), 0)
        self.fixture.authority.revoke("alice")
        refused = self.send(payload)
        self.assertNotEqual(refused[0], 200, refused)
        self.assertEqual(self.fixture.pg_row_count(), 0)

    def test_missing_explicit_writer_is_unavailable(self):
        self.stop_server()
        self.server = StudioTriageMutationServer(
            0, StudioLocalReaders(None, None, None), self.token,
            store=StudioDiscoveryTriageStore(database_url=self.pg.pg.dsn),
            authority=self.fixture.authority,
        )
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.assertEqual(self.send(self.signed())[0],404)

    def test_source_revoked_after_signature_returns_explicit_held_with_no_forged_receipt(self):
        signed = self.signed()
        self.pg.pg._sql(
            "UPDATE content_capture SET rights_status='REVOKED' "
            "WHERE id='capture:review';"
        )
        response = self.send(signed)
        self.assertEqual(response[0], 409, response)
        self.assertEqual(response[1]["data"]["result_code"], "HELD_SOURCE")
        self.assertIsNone(response[1]["data"]["receipt_sha256"])
        self.assertEqual(self.fixture.pg_row_count(), 0)

    def test_revoked_after_committed_receipt_replay_never_echoes_old_receipt(self):
        """RED: immutable history exists, but current revoked write is HELD, not replay."""
        signed = self.signed()
        created_status, created = self.send(signed)
        self.assertEqual(created_status, 200, created)
        self.assertEqual(created["data"]["result_code"], "CREATED")
        original_sha = created["data"]["receipt_sha256"]
        self.assertEqual(self.send(signed)[1]["data"]["result_code"], "REPLAY")
        self.stop_server()
        self.pg.pg._sql(
            "UPDATE content_capture SET rights_status='REVOKED' "
            "WHERE id='capture:review';"
        )
        self.start_server()
        for _ in range(2):
            status, packet = self.send(signed)
            self.assertEqual(status, 409, packet)
            self.assertEqual(packet["data"]["result_code"], "HELD_SOURCE")
            self.assertIsNone(packet["data"]["receipt_sha256"])
            self.assertFalse(packet["data"]["promotion_authority"])
            self.assertNotIn(original_sha, json.dumps(packet))
        self.assertEqual(self.fixture.pg_row_count(), 1, "historic receipt stays immutable")
        self.assertEqual(
            self.server.candidate_store.read(signed["candidate_id"], signed["request_key"])[
                "receipt_sha256"
            ], original_sha, "private separate historic reader can inspect past intent"
        )

    def test_conflicting_idempotency_key_does_not_return_another_reviewers_receipt(self):
        signed = self.signed()
        status, created = self.send(signed)
        self.assertEqual(status, 200, created)
        original_sha = created["data"]["receipt_sha256"]
        conflict = self.fixture.request(
            request_key=signed["request_key"], decision="REJECT",
            expected_revision=1,
        )
        event, receipt = self.fixture.sign(conflict, "bob")
        forged = dataclasses.asdict(conflict) | {
            "review_event": dataclasses.asdict(event),
            "authority_receipt_id": receipt,
            "credential_id": "bob",
            "confirm_private_decision": True,
        }
        code, packet = self.send(forged)
        self.assertEqual(code, 409, packet)
        self.assertEqual(packet["data"]["result_code"], "IDEMPOTENCY_CONFLICT")
        self.assertIsNone(packet["data"]["receipt_sha256"])
        self.assertNotIn(original_sha, json.dumps(packet))
        self.assertEqual(self.fixture.pg_row_count(), 1)

    def test_single_opt_in_studio_pg_write_read_revoke_retry_exact_snapshot(self):
        """One real loopback server integrates authorized POST, readback and revocation."""
        signed = self.signed()
        read_scope = {k: signed[k] for k in (
            "candidate_id", "run_id", "capture_id", "passage_id", "request_key",
        )}
        code, absent = self.send(read_scope, path="/v1/candidate/decision-receipt")
        self.assertEqual(code, 422, absent)
        code, written = self.send(signed)
        self.assertEqual(code, 200, written)
        self.assertEqual(written["data"]["result_code"], "CREATED")
        first_sha = written["data"]["receipt_sha256"]
        code, current = self.send(read_scope, path="/v1/candidate/decision-receipt")
        self.assertEqual(code, 200, current)
        self.assertEqual(current["data"]["status"], "HISTORICAL_SOURCE_CURRENT")
        self.assertEqual(current["data"]["receipt_sha256"], first_sha)
        self.stop_server()
        self.pg.pg._sql(
            "UPDATE content_capture SET rights_status='REVOKED' "
            "WHERE id='capture:review';"
        )
        self.start_server()
        code, held = self.send(signed)
        self.assertEqual(code, 409, held)
        self.assertEqual(held["data"]["result_code"], "HELD_SOURCE")
        self.assertIsNone(held["data"]["receipt_sha256"])
        code, historical = self.send(read_scope, path="/v1/candidate/decision-receipt")
        self.assertEqual(code, 200, historical)
        self.assertEqual(historical["data"]["status"], "HISTORICAL_SOURCE_WITHDRAWN")
        self.assertEqual(historical["data"]["receipt_sha256"], first_sha)
        self.assertFalse(historical["data"]["review_authority"])
        self.assertFalse(historical["data"]["publication_authority"])
        self.assertEqual(self.fixture.pg_row_count(), 1)


if __name__ == "__main__":
    unittest.main()
