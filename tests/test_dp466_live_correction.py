"""Public correction intake: request acknowledgment follows an effective HOLD."""

import http.client
import hashlib
import json
import contextlib
import io
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche.challenge_persistence import ChallengeHoldDisposition  # noqa: E402
from dichiarazioni_pubbliche.openapi import fictional_dossier  # noqa: E402
from dichiarazioni_pubbliche.live_correction_http import build_live_correction_server  # noqa: E402
from dichiarazioni_pubbliche.live_correction_cli import main as correction_main  # noqa: E402
from dichiarazioni_pubbliche.policy.challenge_workflow import ChallengeKind  # noqa: E402
from dichiarazioni_pubbliche.public_statement_authority import PublicStatementChallengeStore  # noqa: E402
from dp468_authority_support import MemoryPostgres  # noqa: E402
from tests.test_public_api import published_bundle, write_bundle  # noqa: E402
from tests.test_dp437_public_opinion_api import ReviewedSyntheticOpinions  # noqa: E402


class FakeLedger:
    def __init__(self):
        self.requests = {}
        self.hold = False
        self.available = True
        self.checked = []

    def current_hold_for_finding(self, finding_id):
        self.checked.append(finding_id)
        return SimpleNamespace(
            disposition=(
                ChallengeHoldDisposition.UNKNOWN if not self.available else
                ChallengeHoldDisposition.HOLD if self.hold else ChallengeHoldDisposition.CLEAR
            ),
            finding_id=finding_id,
            request_id="challenge-request:" + "a" * 64 if self.hold else None,
        )

    def challenged_findings(self):
        if not self.available:
            raise RuntimeError("CHALLENGE_LEDGER_UNAVAILABLE")
        return [item[1] for item in self.requests]

    def initiate_request(self, **values):
        key = (values["actor_ref"], values["target_finding_id"], values["reason"])
        created = key not in self.requests
        self.requests[key] = "challenge-request:" + "a" * 64
        self.hold = True
        return SimpleNamespace(request=SimpleNamespace(request_id=self.requests[key]), created=created)

    def replay_request(self, request_id):
        actor, finding, reason = next(iter(self.requests))
        source_ref = "public-correction:" + hashlib.sha256(
            json.dumps({"finding_id": finding, "reason": reason}, sort_keys=True).encode()
        ).hexdigest()
        return SimpleNamespace(
            request=SimpleNamespace(request_id=request_id, initiated_by_actor_ref=actor,
                                    target_finding_id=finding, source_request_ref=source_ref,
                                    kind=ChallengeKind.CORRECTION),
            blockers=(),
            current_state="PRIVATE_RECEIVED" if self.hold else "REJECTED",
        )


class LiveCorrectionHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "static").mkdir()
        (root / "static" / "index.html").write_text("published item", encoding="utf-8")
        (root / "static" / "correzioni").mkdir()
        (root / "static" / "correzioni" / "index.html").write_text("stale contested correction register", encoding="utf-8")
        for path in ("accedi", "privacy", "segnalazioni"):
            (root / "static" / path).mkdir()
            (root / "static" / path / "index.html").write_text("private contact link", encoding="utf-8")
        dossier = fictional_dossier()
        self.finding_id = dossier["finding_id"]
        projection = write_bundle(root / "projection.json", published_bundle([dossier]))
        self.ledger = FakeLedger()
        self.purges = []
        self.jobs = []
        self.purge_ok = True
        self.quota_ok = True

        def enqueue(finding_id, request_id):
            if not self.ledger.hold:
                raise RuntimeError("HOLD_MUST_PRECEDE_JOB")
            self.jobs.append((finding_id, request_id))
            return True

        def purge(finding_id):
            if not self.jobs:
                return False
            self.purges.append(finding_id)
            return self.purge_ok

        store = SimpleNamespace(path=root / "account.sqlite", get_session=lambda token, now: (
            ("oidc-public-subject", "private@example.invalid", "csrf-fixture") if token == "valid-session" else
            ("other-subject", "other@example.invalid", "csrf-fixture") if token == "other-session" else None
        ))
        service = SimpleNamespace(site_origin="https://dichiarazionipubbliche.it", store=store)
        self.server = build_live_correction_server(
            projection, host="127.0.0.1", port=0, static_dir=root / "static",
            account_service=service, correction_ledger=self.ledger,
            correction_enqueue=enqueue, correction_purge=purge,
            correction_reserve=lambda actor: self.quota_ok,
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, method, path, payload=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        default = {"Host": "dichiarazionipubbliche.it"}
        default.update(headers or {})
        if payload is not None:
            default["Content-Type"] = "application/json"
        conn.request(method, path, body=json.dumps(payload).encode() if payload is not None else None, headers=default)
        response = conn.getresponse()
        body = response.read()
        status = response.status
        response_headers = dict(response.getheaders())
        conn.close()
        return status, response_headers, json.loads(body) if body.startswith(b"{") else body

    def auth_headers(self):
        return {"Origin": "https://dichiarazionipubbliche.it", "Cookie": "__Host-dp-session=valid-session", "X-CSRF-Token": "csrf-fixture"}

    def test_authenticated_submission_holds_api_and_html_before_ack(self):
        status, headers, body = self.request(
            "POST", "/intake/corrections", {"finding_id": self.finding_id, "reason": "La frase è inesatta"},
            self.auth_headers(),
        )
        self.assertEqual(status, 202)
        self.assertEqual(body["state"], "HOLD")
        self.assertEqual(body["request_id"], "challenge-request:" + "a" * 64)
        self.assertEqual(headers["Cache-Control"], "no-store, private")
        self.assertEqual(len(self.jobs), 1)
        self.assertEqual(len(self.purges), 1)
        self.assertEqual(self.request("GET", "/api/v1/index.json")[0], 503)
        self.assertEqual(self.request("GET", "/")[0], 503)
        self.assertEqual(self.request("GET", "/correzioni/")[0], 503)
        self.assertEqual(self.request("GET", "/segnalazioni/")[0], 200)
        self.assertEqual(self.request("GET", "/accedi/")[0], 200)
        self.assertEqual(self.request("GET", "/privacy/")[0], 200)

        status, _, reply = self.request("GET", "/intake/corrections/challenge-request:" + "a" * 64, headers=self.auth_headers())
        self.assertEqual(status, 200)
        self.assertEqual(reply["state"], "HOLD")

    def test_purge_can_verify_hold_by_reading_the_same_live_listener(self):
        """The edge cache purge must re-enter the origin before POST returns 202."""
        observed = []

        def purge_with_origin_readback(_finding_id):
            connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=0.5)
            try:
                connection.request("GET", "/", headers={"Host": "dichiarazionipubbliche.it"})
                response = connection.getresponse()
                observed.append((response.status, response.getheader("Cache-Control")))
                response.read()
            finally:
                connection.close()
            return observed[-1][0] == 503 and "no-store" in observed[-1][1]

        self.server.RequestHandlerClass.correction_purge = staticmethod(purge_with_origin_readback)
        status, _, receipt = self.request(
            "POST", "/intake/corrections",
            {"finding_id": self.finding_id, "reason": "Correggere la citazione pubblicata"},
            self.auth_headers(),
        )
        self.assertEqual(status, 202)
        self.assertEqual(receipt["state"], "HOLD")
        self.assertEqual(observed, [(503, "no-store, private")])

    def test_unauthorized_invalid_and_duplicate_requests_are_rejected(self):
        item = {"finding_id": self.finding_id, "reason": "Inesattezza"}
        self.assertEqual(self.request("POST", "/intake/corrections", item)[0], 401)
        self.assertEqual(self.request("POST", "/intake/corrections", item, self.auth_headers() | {"Origin": "https://wrong.invalid"})[0], 403)
        self.assertEqual(self.request("POST", "/intake/corrections", item | {"is_approved": True}, self.auth_headers())[0], 400)
        self.assertEqual(self.request("POST", "/intake/corrections", item, self.auth_headers())[0], 202)
        status, _, replay = self.request("POST", "/intake/corrections", item, self.auth_headers())
        self.assertEqual(status, 202)
        self.assertEqual(replay["request_id"], "challenge-request:" + "a" * 64)
        self.assertEqual(len(self.purges), 2)
        self.assertEqual(len(self.ledger.requests), 1)
        other = self.auth_headers() | {"Cookie": "__Host-dp-session=other-session"}
        self.assertEqual(self.request("POST", "/intake/corrections", item, other)[0], 409)
        self.assertEqual(len(self.purges), 2)

    def test_absurd_content_length_is_rejected_without_creating_a_correction(self):
        status, _, response = self.request(
            "POST", "/intake/corrections",
            headers=self.auth_headers() | {
                "Content-Type": "application/json",
                "Content-Length": "9" * 5000,
            },
        )
        self.assertEqual(status, 413)
        self.assertEqual(response, {"error": "INVALID_CONTENT_LENGTH"})
        self.assertEqual(self.ledger.requests, {})
        self.assertEqual(self.jobs, [])

    def test_valid_content_length_with_leading_zeros_is_accepted(self):
        payload = {"finding_id": self.finding_id, "reason": "La frase è inesatta"}
        length = len(json.dumps(payload).encode())
        status, _, response = self.request(
            "POST", "/intake/corrections", payload,
            self.auth_headers() | {"Content-Length": "0000" + str(length)},
        )
        self.assertEqual(status, 202)
        self.assertEqual(response["state"], "HOLD")
        self.assertEqual(len(self.ledger.requests), 1)
        self.assertEqual(len(self.jobs), 1)

    def test_purge_failure_keeps_hold_and_refuses_success(self):
        self.purge_ok = False
        status, _, _ = self.request("POST", "/intake/corrections", {"finding_id": self.finding_id, "reason": "Errore"}, self.auth_headers())
        self.assertEqual(status, 503)
        self.assertTrue(self.ledger.hold)
        self.assertEqual(self.request("GET", "/")[0], 503)
        self.purge_ok = True
        status, _, receipt = self.request("POST", "/intake/corrections", {"finding_id": self.finding_id, "reason": "Errore"}, self.auth_headers())
        self.assertEqual(status, 202)
        self.assertEqual(receipt["state"], "HOLD")

    def test_quota_denial_cannot_create_hold_or_queue_work(self):
        self.quota_ok = False
        item = {"finding_id": self.finding_id, "reason": "Richiedo la correzione"}
        self.assertEqual(self.request("POST", "/intake/corrections", item, self.auth_headers())[0], 429)
        self.assertEqual(self.ledger.requests, {})
        self.assertEqual(self.jobs, [])
        self.assertEqual(self.request("GET", "/")[0], 200)

    def test_unavailable_ledger_never_serves_old_projection(self):
        self.ledger.available = False
        self.assertEqual(self.request("GET", "/api/v1/findings")[0], 503)
        self.assertEqual(self.request("GET", "/")[0], 503)

    def test_uncontested_read_requires_one_ledger_inventory_not_n_queries(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        self.assertEqual(self.ledger.checked, [])

    def test_removed_dossier_cannot_unfence_stale_static_html(self):
        item = {"finding_id": self.finding_id, "reason": "Richiedo una correzione"}
        self.assertEqual(self.request("POST", "/intake/corrections", item, self.auth_headers())[0], 202)
        projection = Path(self.temp.name) / "projection.json"
        write_bundle(projection, published_bundle([]))
        self.assertEqual(self.request("GET", "/")[0], 503)

    def test_opted_in_v3_read_and_correction_hold_share_one_listener(self):
        root = Path(self.temp.name)
        v3 = ReviewedSyntheticOpinions().build()
        candidate = root / "approved-v3.json"
        current = root / "current-v3-sha256"
        candidate.write_text(json.dumps(v3), encoding="utf-8")
        current.write_text(v3["dataset_sha256"] + "\n", encoding="ascii")
        handler = self.server.RequestHandlerClass
        private = build_live_correction_server(
            str(root / "projection.json"), host="127.0.0.1", port=0,
            static_dir=str(root / "static"), account_service=handler.account_service,
            correction_ledger=self.ledger,
            correction_enqueue=lambda *_: True,
            correction_purge=lambda *_: True,
            correction_reserve=lambda *_: True,
            statement_projection_path=candidate,
            statement_current_fingerprint_path=current,
            statement_challenge_store=PublicStatementChallengeStore(store=MemoryPostgres()),
        )
        thread = threading.Thread(target=private.serve_forever, daemon=True)
        thread.start()
        original_port = self.port
        self.port = private.server_port
        try:
            self.assertEqual(self.request("GET", "/api/v3/statements")[0], 200)
            self.assertEqual(self.request("HEAD", "/api/v3/opinions")[0], 200)
            self.assertEqual(self.request(
                "POST", "/intake/corrections",
                {"finding_id": self.finding_id, "reason": "Richiedo una correzione"},
                self.auth_headers(),
            )[0], 202)
            self.assertEqual(self.request("GET", "/api/v3/statements")[0], 503)
            self.assertEqual(self.request("GET", "/api/v1/index.json")[0], 503)
        finally:
            self.port = original_port
            private.shutdown()
            private.server_close()
            thread.join(timeout=5)

    def test_v3_cli_requires_both_release_controls(self):
        root = Path(self.temp.name)
        arguments = [
            "--projection-path", str(root / "projection.json"),
            "--static-dir", str(root / "static"),
            "--account-client-id", "test-client",
            "--account-client-secret-file", str(root / "private-secret"),
            "--account-db", str(root / "private-db"),
            "--account-site-origin", "https://dichiarazionipubbliche.it",
            "--correction-cloudflare-zone", "0" * 32,
            "--correction-cloudflare-token-file", str(root / "private-token"),
            "--v3-projection-path", str(root / "approved-v3.json"),
        ]
        with contextlib.redirect_stderr(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as error:
                correction_main(arguments)
        self.assertEqual(error.exception.code, 2)
        self.assertIn("both the approved projection", output.getvalue())


if __name__ == "__main__":
    unittest.main()
