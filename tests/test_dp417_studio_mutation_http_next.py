"""Real loopback HTTP -> independent reviewer receipt -> PostgreSQL CAS -> Studio history."""
from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from dichiarazioni_pubbliche.reviewer_identity_authority import (
    LocalFileReviewerIdentityAuthority, initialize_authority_root,
    provision_reviewer_credential,
)
from dichiarazioni_pubbliche.studio_discovery_triage_authority import issue_triage_attestation
from dichiarazioni_pubbliche.studio_discovery_triage_contract import make_triage_request
from dichiarazioni_pubbliche.studio_discovery_triage_store import StudioDiscoveryTriageStore
from dichiarazioni_pubbliche.studio_local_api import StudioLocalReaders, StudioLoopbackServer
from dichiarazioni_pubbliche.studio_local_mutation_api import StudioTriageMutationServer
from dichiarazioni_pubbliche.studio_operator_queues import StudioOperatorQueues


class AuthenticatedPrivateTriageHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_studio_discovery_triage_schema import DiscoveryTriageSchemaTests
        cls.pg = DiscoveryTriageSchemaTests
        cls.pg.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.pg.tearDownClass()

    def setUp(self):
        self.fixture = self.pg(
            "test_append_only_history_preserves_disposition"
        )
        self.fixture._testMethodName = self._testMethodName
        self.fixture.setUp()
        self.tmp = tempfile.TemporaryDirectory(prefix="dp417-operator-write-")
        root = Path(self.tmp.name) / "reviewer-private"
        initialize_authority_root(root)
        provision_reviewer_credential(
            root, credential_id="operator-1", actor_ref="operator:known",
            key_version="v1", secret_hex="ab" * 32,
        )
        self.authority = LocalFileReviewerIdentityAuthority(root)
        self.store = StudioDiscoveryTriageStore(database_url=self.pg.url)
        self.queue = StudioOperatorQueues(database_url=self.pg.url)
        self.token = "e" * 64
        self.server = StudioTriageMutationServer(
            0, StudioLocalReaders(None, None, None, queues=self.queue),
            self.token, store=self.store, authority=self.authority,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=4)
        self.tmp.cleanup()

    def body(self, **changes):
        result = {
            "collection_id": "collection:one",
            "hit_id": self.fixture.hit,
            "request_key": "once:" + self._testMethodName, "decision": "NEEDS_REVIEW",
            "expected_revision": 0, "actor_ref": "operator:known",
            "confirm_private_annotation": True,
        } | changes
        params = {k: result[k] for k in (
            "collection_id", "hit_id", "request_key", "decision",
            "expected_revision", "actor_ref"
        )}
        signed = issue_triage_attestation(
            self.authority, make_triage_request(**params), "operator-1"
        )
        return result | {"receipt_id": signed["receipt_id"]}

    def send(self, body, *, token=None, origin=None, duplicate=False, path="/v1/discovery/triage-annotate", server=None):
        active = server or self.server
        connection = http.client.HTTPConnection("127.0.0.1", active.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token is not False:
            headers["Authorization"] = "Bearer " + (token or self.token)
        if origin is not None:
            headers["Origin"] = origin
        raw = (body if isinstance(body, bytes) else json.dumps(body).encode())
        if duplicate:
            raw = raw[:-1] + b',"decision":"REJECTED"}'
        connection.request("POST", path, raw, headers=headers)
        response = connection.getresponse()
        status = response.status
        reply = json.loads(response.read())
        connection.close()
        return status, reply

    def test_auth_readonly_unchanged_then_signed_commit_replay_restart_readback(self):
        payload = self.body()
        with StudioLoopbackServer(
            0, StudioLocalReaders(None, None, None), self.token
        ) as readonly:
            thread = threading.Thread(target=readonly.serve_forever, daemon=True)
            thread.start()
            try:
                self.assertEqual(self.send(payload, server=readonly)[0], 404)
            finally:
                readonly.shutdown()
                thread.join(timeout=4)
        self.assertEqual(self.send(payload, token=False)[0], 401)
        self.assertEqual(self.send(payload, token="0"*64)[0], 401)
        self.assertEqual(self.send(payload, origin="https://foreign.invalid")[0], 403)
        self.assertEqual(self.send(payload, duplicate=True)[0], 422)
        created, record = self.send(payload)
        self.assertEqual(created, 200, record)
        self.assertEqual(record["data"]["result_code"], "CREATED")
        self.assertFalse(record["data"]["publication_authority"])
        self.assertFalse(record["data"]["triage_action_authorized"])
        for secret in ("operator:known", payload["receipt_id"], "ab"*32, "actor_ref"):
            self.assertNotIn(secret, json.dumps(record))
        replay, receipt = self.send(payload)
        self.assertEqual(replay, 200, receipt)
        self.assertEqual(receipt["data"]["result_code"], "REPLAY")
        self.assertEqual(
            self.pg.require_sql(
                "SELECT count(*) FROM research_discovery_triage_decision"
                f" WHERE hit_id='{self.fixture.hit}'"
            ), "1"
        )
        history = self.send(
            {"collection_id": "collection:one", "hit_id": self.fixture.hit},
            path="/v1/discovery/triage-history",
        )
        self.assertEqual(history[0], 200, history)
        self.assertEqual(history[1]["data"]["results"], [
            {"revision": 1, "decision": "NEEDS_REVIEW"}
        ])
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=4)
        self.server = StudioTriageMutationServer(
            0, StudioLocalReaders(None, None, None, queues=self.queue),
            self.token,
            store=StudioDiscoveryTriageStore(database_url=self.pg.url),
            authority=LocalFileReviewerIdentityAuthority(self.authority.root),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.assertEqual(self.send(payload)[1]["data"]["result_code"], "REPLAY")

    def test_conflicts_cross_collection_and_actor_revocation_are_not_approvals(self):
        first = self.body()
        first_result = self.send(first)
        self.assertEqual(first_result[0], 200, first_result)
        conflict = self.body(request_key="once:other")
        status, response = self.send(conflict)
        self.assertEqual(status, 409, response)
        self.assertEqual(response["data"]["result_code"], "REVISION_CONFLICT")
        foreign = self.body(collection_id="collection:two", request_key="once:wrong")
        self.assertEqual(self.send(foreign)[1]["data"]["result_code"], "SCOPE_NOT_FOUND")
        self.authority.revoke("operator-1")
        self.assertEqual(self.send(first)[0], 422)
        self.assertEqual(self.send(first | {"confirm_private_annotation": False})[0], 422)

    def test_separate_cli_issues_real_receipt_then_browser_http_writes_and_restart_reads(self):
        # Build an exact intent locally from current PG queue revision. Unlike
        # the server, the signed CLI deliberately does not connect to PG.
        args = self.body(request_key="cli:" + self._testMethodName)
        options = [
            sys.executable, "-m", "dichiarazioni_pubbliche.studio_triage_receipt_issue",
            "--authority-root", str(self.authority.root),
            "--credential-id", "operator-1",
            "--collection-id", args["collection_id"],
            "--hit-id", args["hit_id"],
            "--request-key", args["request_key"],
            "--decision", args["decision"],
            "--expected-revision", str(args["expected_revision"]),
            "--actor-ref", args["actor_ref"],
        ]
        env=os.environ.copy()
        env["PYTHONPATH"]=str(Path(__file__).resolve().parents[1]/"poc")
        refused=subprocess.run(options,env=env,capture_output=True,text=True,timeout=5)
        self.assertEqual(refused.returncode,2)
        self.assertNotIn("ab"*32,refused.stdout)
        command=subprocess.run(options+["--confirm-private-annotation-only"],
                               env=env,capture_output=True,text=True,timeout=5)
        self.assertEqual(command.returncode,0,command.stderr)
        signed=json.loads(command.stdout)
        self.assertFalse(signed["database_written"])
        self.assertFalse(signed["publication_authority"])
        self.assertEqual(
            self.pg.require_sql("SELECT count(*) FROM research_discovery_triage_decision"
                                f" WHERE hit_id='{self.fixture.hit}'"), "0"
        )
        payload=args|{"receipt_id":signed["receipt_id"]}
        response=self.send(payload)
        self.assertEqual(response[0],200,response)
        self.assertEqual(response[1]["data"]["result_code"],"CREATED")
        self.assertEqual(
            self.queue.inspect_discovery_triage(
                collection_id=args["collection_id"],hit_id=args["hit_id"]
            )["results"],[{"revision":1,"decision":"NEEDS_REVIEW"}]
        )


if __name__ == "__main__":
    unittest.main()
